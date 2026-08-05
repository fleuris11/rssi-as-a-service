# Revue de sécurité — OWASP Top 10 (2021)

- **Date** : 2026-08-05
- **Périmètre** : plateforme RSSI as a Service (backend Django/DRF, frontend React, infrastructure
  Docker Compose + Caddy) à l'issue de la Phase 5 (durcissement).
- **Méthode** : revue de code manuelle catégorie par catégorie, complétée par les scans automatisés
  de la CI (`pip-audit`, `npm audit`, Trivy — voir ADR-008) et par les tests end-to-end Playwright
  (parcours critiques + `@axe-core/playwright`). Chaque catégorie liste : la menace, les mesures déjà
  en place (avec référence de fichier), les mesures ajoutées lors de cette session, et les risques
  résiduels sciemment acceptés.

Ce document est vivant : il doit être mis à jour à chaque changement structurant touchant
l'authentification, l'isolation multi-tenant, la chaîne IA ou l'infrastructure.

---

## A01:2021 — Broken Access Control (contrôle d'accès défaillant)

**Menace.** Un tenant lit ou modifie les données d'un autre tenant ; un utilisateur avec un rôle
insuffisant (lecteur) effectue une action réservée aux administrateurs/contributeurs.

**Mesures en place**
- Isolation multi-tenant à trois niveaux (défense en profondeur) :
  1. `TenantScopingMiddleware` (`backend/apps/tenants/middleware.py:13`) résout le tenant courant à
     partir de l'en-tête `X-Tenant-Id` et de l'appartenance réelle de l'utilisateur
     (`Membership.all_objects...filter(tenant_id=..., user=...)`, non filtré par manager scopé — il
     doit voir toutes les adhésions pour valider l'accès) ; renvoie `403` sinon.
  2. `TenantScopedManager` (`backend/apps/tenants/managers.py:6`) : **fail-closed** — si aucun tenant
     n'est résolu dans le contexte (`contextvars`, `backend/apps/tenants/context.py`), le queryset
     par défaut renvoie `.none()` plutôt que toutes les lignes.
  3. Permissions DRF explicites sur chaque vue : `IsTenantMember`, `IsTenantAdmin`,
     `IsTenantMemberReadOnlyForReader` (`backend/apps/tenants/permissions.py`), `IsAIEnabled`
     (`backend/apps/ai_assistant/permissions.py:4`).
- Filet de sécurité global : `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`
  (`backend/config/settings.py:127-129`) — une vue qui oublierait de déclarer ses permissions reste
  au moins authentifiée, jamais publique par défaut.
- Suite de tests d'étanchéité dédiée : `backend/apps/tenants/tests/test_isolation.py` —
  `TestTenantScopedManagerFailsClosed`, `TestTenantScopingMiddlewareAttackScenarios` (en-tête vers un
  tenant étranger, tenant inexistant, en-tête malformé, adhésion révoquée), `TestTenantMemberListAPI`
  / `TestMyTenantListAPI`. Chaque app métier (`actions`, `ai_assistant`, `assessments`, `monitoring`)
  porte en plus ses propres assertions d'étanchéité dans `test_api.py` (CLAUDE.md règle 2 : « toute
  nouvelle ressource DOIT avoir un test d'étanchéité »).

**Mesures ajoutées dans cette session**
- Aucune nouvelle mesure de contrôle d'accès n'était nécessaire — le modèle défense-en-profondeur
  était déjà en place depuis les phases précédentes et a été revérifié ici sans régression détectée.

**Risques résiduels acceptés**
- La résolution du tenant dépend d'un en-tête HTTP (`X-Tenant-Id`) plutôt que d'être encodée dans le
  JWT lui-même. C'est un choix délibéré (un utilisateur multi-tenant change de contexte sans se
  reconnecter), mais cela signifie qu'un jeton d'accès volé reste exploitable pour n'importe quel
  tenant dont l'attaquant connaît l'ID **et** dont la victime est membre — l'attaquant ne peut pas
  élargir son accès à un tenant dont il n'est pas membre (vérifié par `_resolve_membership`), donc le
  risque se limite au périmètre déjà accessible à la victime.

---

## A02:2021 — Cryptographic Failures (défaillances cryptographiques)

**Menace.** Secrets en clair au repos ou en transit, hachage de mot de passe faible, clés de
chiffrement réutilisées entre usages sans rapport.

**Mesures en place**
- Mots de passe utilisateurs hachés avec le hasher par défaut de Django 5.2
  (`PBKDF2PasswordHasher`, PBKDF2-SHA256, 1 000 000 itérations) — aucune surcharge
  `PASSWORD_HASHERS`, donc pas de régression vers un algorithme plus faible.
- `SECRET_KEY` chargé exclusivement depuis la variable d'environnement `DJANGO_SECRET_KEY`
  (`backend/config/settings.py:22`), sans valeur par défaut : échoue au démarrage plutôt que de
  tourner avec une clé prévisible.
- Deux clés Fernet **distinctes et non interchangeables** pour deux usages sans rapport (ADR-005,
  ADR-009) :
  - `AI_PSEUDONYMIZATION_KEY` chiffre la table de correspondance pseudonymisée avant tout appel IA
    (`backend/apps/ai_assistant/services.py:246`, `store_mapping`/`load_mapping` lignes 255-270).
  - `TOTP_ENCRYPTION_KEY` chiffre le secret TOTP au repos (`apps/accounts/services.py`).
  - Une compromission de l'une ne compromet pas l'autre — décision explicite plutôt qu'une clé
    unique partagée par commodité.
- TLS géré par Caddy (Let's Encrypt automatique, `deploy/Caddyfile`) devant toute la plateforme ;
  `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` forcés en production
  (`backend/config/settings_production.py:25-28`).
- Codes de récupération 2FA stockés hachés (`RecoveryCode.code_hash`), jamais en clair
  (`apps/accounts/models.py`).
- Clés d'API (Anthropic) et secrets ne transitent que par variables d'environnement,
  `backend/.env.example` ne contient que des placeholders vides — jamais de valeur réelle committée.

**Mesures ajoutées dans cette session**
- `TOTP_ENCRYPTION_KEY` (nouvelle clé dédiée, US-1.3) introduite précisément pour ne pas réutiliser
  `AI_PSEUDONYMIZATION_KEY` par facilité.
- Durant cette session, une clé API Anthropic réelle a été trouvée en clair dans
  `backend/.env.example` en modification locale non committée. Elle a été retirée avant tout commit
  et le développeur a été alerté pour rotation de la clé côté fournisseur par précaution — voir
  `docs/journal.md`. Aucune fuite via Git n'a eu lieu (vérifié via `git diff`/`git show`), mais
  l'incident souligne un point de vigilance opérationnel plutôt qu'une faille de conception.

**Risques résiduels acceptés**
- Pas de rotation automatisée des clés Fernet (`AI_PSEUDONYMIZATION_KEY`, `TOTP_ENCRYPTION_KEY`) : une
  rotation nécessiterait aujourd'hui une procédure manuelle (rechiffrement des secrets existants).
  Accepté pour le stade actuel du projet (MVP, faible volume de secrets stockés) ; à revoir si le
  volume de credentials 2FA/mappings pseudonymisés augmente significativement.

---

## A03:2021 — Injection

**Menace.** Injection SQL, injection de commande, XSS stocké/réfléchi.

**Mesures en place**
- ORM Django exclusivement : recherche exhaustive de `.raw(`, `.extra(`, `cursor.execute(` sur tout
  `backend/` (hors migrations/venv) — **aucune occurrence**. Pas de surface d'injection SQL.
- Aucune occurrence de `eval(`, `exec(`, `subprocess`, `os.system` dans le code applicatif — pas de
  surface d'injection de commande.
- Aucune occurrence de `mark_safe`/`|safe` côté Django, ni de `dangerouslySetInnerHTML` côté React —
  pas de contournement de l'échappement automatique des templates/JSX.
- Le contenu généré par l'IA (charte informatique) n'est jamais rendu comme HTML côté frontend : il
  est affiché dans un `<textarea>` (texte brut, jamais interprété) et exporté soit en Markdown brut,
  soit en PDF rendu **côté serveur** par WeasyPrint (ADR-012) à partir d'un Markdown converti en HTML
  minimal — ce HTML n'est jamais renvoyé au navigateur, seul le PDF final l'est.
- Entrées utilisateur validées par les serializers DRF avant tout traitement métier.

**Mesures ajoutées dans cette session**
- Aucune (le pipeline PDF, seule nouvelle surface de transformation HTML de cette session, a été
  conçu dès le départ pour ne jamais exposer le HTML intermédiaire au client — voir ADR-012).

**Risques résiduels acceptés**
- Le contenu markdown→HTML→PDF provient d'un contenu généré par IA puis relu/validé par un humain
  (US-4.1 : le tenant doit valider avant export) — un contenu malveillant injecté via un prompt
  détourné resterait cantonné au rendu PDF (jamais exécuté), le risque XSS classique ne s'applique
  donc pas à ce pipeline.

---

## A04:2021 — Insecure Design (conception non sécurisée)

**Menace.** Des choix d'architecture qui rendent une classe entière de vulnérabilités possible,
indépendamment de la qualité d'implémentation.

**Mesures en place**
- Pseudonymisation **avant** tout appel IA (ADR-005) : `collect_sensitive_values`
  (`apps/ai_assistant/services.py:175-201`) ne construit la correspondance qu'à partir de champs
  identifiants explicites (nom d'entreprise, membres, actifs) — jamais de champs agrégés/statistiques
  — conçu pour qu'aucune donnée réelle ne parte vers l'API tierce, pas seulement filtré a posteriori.
- Surveillance strictement passive sur actifs déclarés uniquement (ADR-010) : protection SSRF
  (`apps/monitoring/checks/ssrf.py`) validée à chaque résolution DNS, y compris à chaque saut de
  redirection HTTP — empêche qu'un actif « déclaré » serve de prétexte pour sonder un réseau interne.
- Confirmation de panne par 3 échecs consécutifs avant alerte (`CONSECUTIVE_FAILURES_FOR_DOWN`,
  `apps/monitoring/services.py`) — conception anti-faux-positifs plutôt que correctif après coup.
- Verrouillage progressif par compte **et** IP (`apps/accounts/services.py`, échelle
  `_LOCKOUT_LADDER`), stocké dans Redis avec des clés hashées SHA-256 — l'email/IP en clair
  n'apparaît jamais dans le cache.
- Messages d'erreur non énumérants par conception : le message d'échec de connexion est identique que
  l'email existe ou non (`apps/accounts/views.py`), de même pour l'inscription en doublon
  (`apps/accounts/serializers.py`).
- Défense en profondeur multi-tenant (voir A01) conçue comme trois mécanismes indépendants plutôt
  qu'un seul point de défaillance.

**Mesures ajoutées dans cette session**
- Verrouillage progressif compte+IP, messages non énumérants, et 2FA TOTP (voir A07) sont tous des
  décisions de conception introduites dans cette phase, pas de simples correctifs.

**Risques résiduels acceptés**
- Aucune limite de dépôt (rate limit) déclarée au niveau applicatif pour la déclaration d'actifs de
  surveillance (un tenant pourrait déclarer un grand nombre d'actifs) — mitigé indirectement par le
  rate limiting général par tenant (A07) mais pas par une limite métier dédiée ; accepté pour le
  stade MVP, à réévaluer si un abus est constaté en production.

---

## A05:2021 — Security Misconfiguration (mauvaise configuration)

**Menace.** `DEBUG=True` en production, hôtes autorisés permissifs, en-têtes de sécurité HTTP
absents, secrets committés.

**Mesures en place**
- `config/settings_production.py` séparé de `config/settings.py` (ADR non numéroté explicite via le
  docstring du module) : `DEBUG = False` forcé, `ALLOWED_HOSTS` sans valeur par défaut (échoue au
  démarrage si non défini plutôt que de retomber sur une valeur permissive), cookies de session/CSRF
  `Secure`, `HttpOnly` sur la session, HSTS (1 an, sous-domaines inclus, preload), `X-Frame-Options:
  DENY`, `Referrer-Policy: same-origin`, `SECURE_CONTENT_TYPE_NOSNIFF`.
- En-têtes de sécurité HTTP au niveau du reverse proxy (`deploy/Caddyfile`) : HSTS,
  `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, CSP, `Permissions-Policy`,
  suppression de l'en-tête `Server`.
- `CORS_ALLOWED_ORIGINS` explicite (jamais `CORS_ALLOW_ALL_ORIGINS=True`) ; `CORS_ALLOW_HEADERS`
  déclaré explicitement (voir « mesures ajoutées » ci-dessous).
- `.dockerignore` (racine et `backend/`) exclut `.env`, `node_modules`, `.git` de toute image Docker.
- `.env`/`backend/.env` gitignorés ; `backend/.env.example` ne contient que des placeholders vides.
- Build Docker multi-étage pour le frontend (`deploy/Dockerfile.caddy`) : l'image finale ne contient
  que les assets buildés, jamais les sources ni les `node_modules`.

**Mesures ajoutées dans cette session**
- L'intégralité de la configuration de production (`settings_production.py`, `deploy/Caddyfile`,
  `docker-compose.prod.yml`, `deploy/Dockerfile.caddy`) est nouvelle dans cette phase (Phase 5).
- **Correctif découvert par les tests E2E réels** (pas par une revue statique) : `CORS_ALLOW_HEADERS`
  n'incluait pas l'en-tête personnalisé `X-Tenant-Id` (`backend/apps/tenants/... client.js`
  l'envoie sur chaque requête scopée). Sans cet en-tête dans la liste blanche CORS,
  le navigateur bloque silencieusement côté client toute requête tenant-scopée après la
  toute première (aucune trace côté serveur, aucune erreur explicite côté client hors console réseau)
  — un bug de disponibilité fonctionnelle qui n'aurait jamais été détecté par les tests unitaires
  Django (le client de test Django n'applique pas les règles CORS du navigateur). Corrigé dans
  `backend/config/settings.py` (`CORS_ALLOW_HEADERS = [*default_headers, "x-tenant-id"]`) avec un
  test de non-régression dédié (`backend/config/tests/test_cors.py`).

**Risques résiduels acceptés**
- `SESSION_COOKIE_SAMESITE`/`CSRF_COOKIE_SAMESITE` ne sont pas surchargés (valeur par défaut Django
  `Lax`) : acceptable car l'API elle-même n'utilise que `JWTAuthentication`
  (`DEFAULT_AUTHENTICATION_CLASSES`, `backend/config/settings.py:124-126`) — aucune authentification
  par cookie de session pour l'API, donc pas de surface CSRF sur les endpoints métier. Seul
  `/admin/` (Django admin, session-based) reste concerné, protégé par `CsrfViewMiddleware`.
- Pas de `LOGGING` dict explicite (voir A09) — configuration de journalisation par défaut Django.

---

## A06:2021 — Vulnerable and Outdated Components (composants vulnérables)

**Menace.** Dépendance connue vulnérable, non détectée avant déploiement.

**Mesures en place (ajoutées dans cette session — n'existaient pas avant Phase 5)**
- **Backend** : `pip-audit -r requirements.txt --strict` en CI (`.github/workflows/ci.yml`, job
  `backend`). Exécuté localement pendant cette session : **aucune vulnérabilité connue** sur les
  dépendances actuelles (`backend/requirements.txt`, entièrement épinglées à une version exacte).
- **Frontend** : `npm audit --audit-level=high`, encapsulé dans
  `frontend/scripts/check-npm-audit.mjs` (exécuté via `npm run audit`, câblé en CI job `frontend`) —
  échoue la CI sur toute vulnérabilité `high`/`critical` **non explicitement acceptée**. `npm audit`
  n'offre aucun mécanisme natif d'acceptation de risque documentée ; ce script en est le plus petit
  équivalent : une liste blanche d'identifiants GHSA avec justification en commentaire.
  - **Risque accepté documenté** : `GHSA-qwww-vcr4-c8h2` (react-router / react-router-dom, CWE-352,
    « RSC Mode... Action Execution Before 400 Response »). Inapplicable à cette application : routage
    déclaratif classique `<Routes>/<Route>`, aucun React Server Components, aucune action de données
    en mode framework (le chemin de code vulnérable n'est simplement pas utilisé). Le seul correctif
    disponible est un downgrade « breaking change » vers une version antérieure elle-même vulnérable
    différemment — corriger créerait plus de risque que le statu quo documenté.
- **Image Docker** : scan Trivy (`aquasecurity/trivy-action`, job `container-scan`,
  `severity: HIGH,CRITICAL`, `ignore-unfixed: true`) sur l'image `backend/Dockerfile` buildée en CI.
  Exécuté localement pendant cette session sur l'image de production actuelle : **0 vulnérabilité
  HIGH/CRITICAL** détectée (packages système et packages Python, y compris les nouvelles dépendances
  WeasyPrint/pyotp/qrcode ajoutées cette phase).
- Toutes les dépendances Python sont épinglées à une version exacte (`==`) dans
  `backend/requirements.txt`/`requirements-dev.txt` — pas de plage de versions qui introduirait une
  dépendance non revue silencieusement.

**Risques résiduels acceptés**
- `ignore-unfixed: true` sur le scan Trivy signifie qu'une vulnérabilité HIGH/CRITICAL sans correctif
  disponible ne bloque pas la CI (elle ne pourrait de toute façon pas être corrigée immédiatement) —
  nécessite une revue manuelle périodique, pas seulement le signal CI automatisé (voir ADR-008).
- Les dépendances npm (hors le risque react-router documenté) ne sont pas toutes épinglées à une
  version exacte (usage de `^` dans `package.json`) — `package-lock.json` fige les versions
  installées, mais une mise à jour via `npm install` pourrait introduire une version non revue tant
  que `npm audit` reste vert.

---

## A07:2021 — Identification and Authentication Failures (authentification défaillante)

**Menace.** Force brute sur les identifiants, absence de MFA, jetons de session trop longs ou non
révocables, énumération de comptes.

**Mesures en place**
- JWT courts (15 min) + rotation des refresh tokens (7 jours, `ROTATE_REFRESH_TOKENS=True`,
  `BLACKLIST_AFTER_ROTATION=True`, `backend/config/settings.py:SIMPLE_JWT`) — chaque rafraîchissement
  invalide l'ancien refresh token (ADR-009).
- **2FA TOTP** (US-1.3) complète : enrôlement par QR code (`pyotp`+`qrcode`), secret chiffré au repos
  (clé Fernet dédiée), codes de récupération à usage unique hashés, vérification au login via un
  jeton de challenge opaque (`secrets.token_urlsafe`, TTL 5 minutes, usage unique — jamais un JWT),
  désactivation nécessitant confirmation du mot de passe (`apps/accounts/services.py`,
  `apps/accounts/views.py`). Frontend : `frontend/src/pages/TwoFactorSettingsPage.jsx`,
  flux de login à deux étapes dans `LoginPage.jsx`.
- Verrouillage progressif par compte **et** IP après échecs répétés (échelle
  `_LOCKOUT_LADDER = [(5, 60s), (10, 5min), (15, 15min), (20, 1h)]`,
  `apps/accounts/services.py:check_not_locked_out`/`record_failed_attempt`), backé par Redis, clés
  hashées SHA-256.
- Rate limiting DRF par IP sur les endpoints d'authentification (`AuthRateThrottle`, scope `auth`,
  10/min — `apps/accounts/throttling.py`) sur register/login/refresh ; par tenant sur l'API générale
  (`TenantRateThrottle`, 300/min) et les endpoints IA (`TenantAIRateThrottle`, 20/min, alignée sur les
  quotas IA) — `apps/tenants/throttling.py`. Réponses `429` propres, testées
  (`apps/accounts/tests/test_lockout.py`, `apps/tenants/tests/test_throttling.py`).
- Politique de mot de passe : longueur minimale 12 caractères (privilégiée à la complexité imposée,
  cadrage §6) + `CommonPasswordValidator` (rejette les mots de passe compromis courants) +
  `NumericPasswordValidator` (`backend/config/settings.py:85-93`).
- Messages d'erreur non énumérants : réponse identique pour un email inconnu ou un mot de passe
  incorrect ; message générique en cas de doublon à l'inscription (pas de « cet email existe déjà »
  exploitable) — testé dans `TestNonEnumeratingErrors`
  (`apps/accounts/tests/test_lockout.py`).

**Mesures ajoutées dans cette session**
- L'intégralité de cette catégorie (2FA, verrouillage progressif, rate limiting, non-énumération) a
  été introduite en Phase 5 — le socle Phase 1 ne fournissait que JWT + RBAC de base.

**Risques résiduels acceptés**
- La 2FA est optionnelle par tenant/utilisateur (US-1.3 ne l'impose pas globalement) — un compte qui
  ne l'active pas reste protégé uniquement par mot de passe + verrouillage progressif. Une politique
  d'entreprise imposant la 2FA à tous les membres d'un tenant est hors périmètre actuel (voir
  ADR-009).
- Un access token JWT compromis reste valide jusqu'à 15 minutes sans révocation immédiate côté
  serveur (limite structurelle des JWT, mitigée par la courte durée de vie).

---

## A08:2021 — Software and Data Integrity Failures (intégrité logicielle et des données)

**Menace.** Dépendances/CI compromises silencieusement, migrations destructrices, tâches
asynchrones non idempotentes provoquant une double exécution ou une perte de données.

**Mesures en place**
- CI obligatoire avant merge (trunk-based, branches courtes, PR avec CI verte — CLAUDE.md) : lint
  (`ruff`), vérification des migrations manquantes, suite de tests complète, désormais complétée par
  les audits de dépendances et le scan d'image (voir A06) et le job E2E (voir ci-dessous).
- Migrations Django rétro-compatibles (pattern expand/contract, CLAUDE.md) — jamais de perte de
  données lors d'un déploiement.
- Tâches Celery conçues idempotentes et retryables avec backoff (CLAUDE.md) ; un bug d'idempotence
  découvert et corrigé lors des tests réels de la Phase 4 (job de génération de document restant
  bloqué) illustre que cette exigence est vérifiée en pratique, pas seulement déclarée.
- **Tests end-to-end Playwright** (nouveaux cette session, `frontend/e2e/`) exécutés contre la vraie
  stack `docker-compose` (pas de mocks du backend, sauf l'API IA pour le parcours de génération de
  charte — volontairement, pour rester gratuit et déterministe) : couvrent les 3 parcours critiques
  (inscription→diagnostic→plan d'action ; déclaration d'actif→check simulé→alerte visible ;
  génération de charte→relecture→validation), plus un balayage d'accessibilité sur les pages
  principales restantes (`frontend/e2e/d-accessibility-sweep.spec.js`). Intégrés en CI (job `e2e`
  dédié) — toute régression d'intégration réelle (pas seulement unitaire) est désormais détectée
  avant merge.
- Le check simulé du parcours (b) passe par une commande de gestion Django dédiée
  (`simulate_check_failure`, `backend/apps/monitoring/management/commands/`) qui réutilise le vrai
  moteur d'alerte (`apps.monitoring.services.simulate_check_result`/`evaluate_alerts`) plutôt que de
  contourner la logique métier — le test valide donc le vrai pipeline d'alerte, pas une simulation
  parallèle divergente.

**Mesures ajoutées dans cette session**
- Le job CI `e2e` et son intégration à la stack `docker-compose` sont entièrement nouveaux, de même
  que le scan Trivy de l'image (voir A06) et l'audit de dépendances.

**Risques résiduels acceptés**
- Aucun mécanisme de signature/vérification d'intégrité des images Docker en production (ex. cosign)
  — accepté pour le stade actuel (déploiement manuel via SSH, pas de registre d'images tiers).

---

## A09:2021 — Security Logging and Monitoring Failures (journalisation insuffisante)

**Menace.** Une intrusion ou un abus n'est jamais détecté faute de traces, ou les traces elles-mêmes
exposent des données personnelles.

**Mesures en place**
- Aucune donnée personnelle (email, IP, domaine réel) constatée dans les appels de journalisation
  existants — vérifié explicitement lors de cette revue : les 3 fichiers utilisant `logging`
  (`apps/ai_assistant/services.py`, `apps/ai_assistant/tasks.py`, `apps/monitoring/tasks.py`) ne
  journalisent que des identifiants internes (`tenant.id`, `document.id`, `job.id`, `asset_id`) —
  conforme à l'exigence CLAUDE.md « ne jamais stocker de données personnelles dans les logs ».
- Journalisation d'usage IA détaillée à des fins d'audit et de transparence (US-4.3) :
  `AIUsageLog` (tenant, cas d'usage, tokens, coût estimé) — stockée en base, pas dans les logs
  applicatifs, et déjà pseudonymisée en amont par construction (le contenu réel n'y est jamais écrit).
- Tests de non-régression sur le pipeline d'alerte de surveillance (`test_services.py`) garantissant
  qu'une panne réelle (3 échecs consécutifs) produit toujours une `Alert` traçable en base.

**Risques résiduels acceptés (gap identifié, non corrigé dans cette session)**
- **Aucun `LOGGING` Django explicite** (confirmé : ni `settings.py` ni `settings_production.py` ne
  définissent de dict `LOGGING`) — la configuration par défaut de Django s'applique (sortie console
  uniquement, pas de rotation de fichiers, pas d'agrégation centralisée, pas d'alerting sur erreurs
  serveur en production). C'est le principal gap de cette catégorie : en l'état, un incident de
  sécurité (tentative d'intrusion, abus détecté par le rate limiting) ne génère qu'une ligne de
  console potentiellement non conservée, jamais une alerte active pour l'opérateur.
- **Aucun outil de suivi d'erreurs/APM** (Sentry ou équivalent) n'est intégré — confirmé absent de
  `requirements.txt` et de `settings.py`.
- **Recommandation pour Phase 6 (production)** : configurer un `LOGGING` dict envoyant au minimum les
  échecs d'authentification répétés (verrouillages déclenchés) et les erreurs serveur 5xx vers une
  destination persistante, et évaluer l'intégration d'un outil de suivi d'erreurs — en respectant la
  même contrainte que le reste du projet (CLAUDE.md : jamais de donnée personnelle envoyée à un
  service de suivi d'erreurs tiers).

---

## A10:2021 — Server-Side Request Forgery (SSRF)

**Menace.** Le serveur de surveillance est manipulé pour effectuer une requête vers une ressource
interne (métadonnées cloud, réseau privé) sous couvert d'un actif « déclaré » légitime.

**Mesures en place** (détaillées dans ADR-010, « Vérifications passives uniquement »)
- Toute résolution DNS est validée contre les plages d'IP privées/loopback/link-local/réservées/
  multicast/non spécifiées avant l'ouverture de toute connexion —
  `apps/monitoring/checks/ssrf.py:resolve_safe_host`/`validate_url`.
- Cette validation s'applique à **chaque saut de redirection HTTP suivi**, pas seulement à l'URL de
  départ — empêche un attaquant de déclarer un actif public qui redirige (302) vers une adresse
  interne.
- Schémas autorisés restreints à `http`/`https` (`ALLOWED_SCHEMES`, `ssrf.py:15`).
- Un actif n'est vérifié que s'il a été explicitement déclaré par le tenant avec attestation de
  propriété (`Asset.ownership_confirmed`, contrôlé par le serializer à la création) — CLAUDE.md règle
  4.
- Vérifications strictement passives (GET HTTP standard, lecture TLS côté client, requêtes DNS
  publiques) — jamais de scan de port ni de tentative d'exploitation, éliminant une classe entière de
  risques juridiques et de faux-SSRF (ADR-010).
- Tests dédiés : `apps/monitoring/tests/test_ssrf.py`.

**Mesures ajoutées dans cette session**
- Aucune (le garde-fou SSRF existait depuis la Phase 3 — revérifié sans régression, y compris via le
  parcours E2E (b) qui exerce le pipeline d'alerte réel autour de ce module).

**Risques résiduels acceptés**
- La résolution DNS est effectuée une fois au moment du check (« TOCTOU » — time-of-check to
  time-of-use classique des protections SSRF basées sur la résolution DNS) : un DNS rebinding entre
  la validation et la connexion effective reste théoriquement possible. Accepté comme limite connue
  et documentée plutôt que traité par un correctif complexe (résolution manuelle + connexion sur IP
  figée), disproportionné pour la surface de risque réelle (checks passifs, pas d'action destructive
  possible même en cas de succès de l'attaque).

---

## Synthèse

| Catégorie | État |
|---|---|
| A01 Broken Access Control | Couvert — défense en profondeur (middleware + manager fail-closed + permissions), testé |
| A02 Cryptographic Failures | Couvert — hachage par défaut robuste, clés Fernet séparées par usage |
| A03 Injection | Couvert — aucune surface trouvée (ORM, pas de `mark_safe`/`dangerouslySetInnerHTML`) |
| A04 Insecure Design | Couvert — pseudonymisation, SSRF, anti-faux-positifs conçus en amont |
| A05 Security Misconfiguration | Couvert — settings de prod séparés, en-têtes Caddy ; 1 bug CORS réel trouvé et corrigé cette session |
| A06 Vulnerable Components | Couvert — pip-audit/npm audit/Trivy ajoutés cette session, 0 vulnérabilité HIGH/CRITICAL actuellement |
| A07 Auth Failures | Couvert — 2FA, verrouillage progressif, rate limiting, non-énumération, tous ajoutés cette session |
| A08 Software/Data Integrity | Couvert — CI stricte, migrations expand/contract, tâches idempotentes, E2E réels ajoutés cette session |
| A09 Logging/Monitoring | **Gap identifié** — pas de `LOGGING` dict ni d'outil de suivi d'erreurs ; recommandé pour Phase 6 |
| A10 SSRF | Couvert — garde-fou dédié, testé, limite TOCTOU documentée et acceptée |
