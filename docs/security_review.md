# Revue de sécurité — OWASP Top 10 (2021)

- **Date** : 2026-08-05 (revue initiale, Phase 5) — mise à jour 2026-08-08 (Phase 7, intégration
  Breachsense/CTI — voir la section dédiée après A10 et ADR-013/ADR-014 pour le détail des décisions).
- **Périmètre** : plateforme RSSI as a Service (backend Django/DRF, frontend React, infrastructure
  Docker Compose + Caddy) à l'issue de la Phase 5 (durcissement), complété Phase 7 par le module de
  renseignement sur la menace (`apps.threat_intelligence`).
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

**Mesures ajoutées dans cette session (Phase 5)**
- Aucune nouvelle mesure de contrôle d'accès n'était nécessaire — le modèle défense-en-profondeur
  était déjà en place depuis les phases précédentes et a été revérifié ici sans régression détectée.

**Mesures ajoutées en Phase 7 (Breachsense/CTI)**
- Tous les nouveaux modèles (`BreachFinding`, `MonitoredAsset`, `BreachIntelligenceUsage`,
  `BreachScanJob`) héritent de `TenantScopedModel` et bénéficient donc des trois mêmes mécanismes de
  défense en profondeur que le reste de la plateforme — testé explicitement
  (`apps/threat_intelligence/tests/test_api.py::TestBreachFindingAPI::test_cannot_read_another_tenants_finding`
  et `test_findings_are_scoped_per_tenant_in_list`).
- Le back-office CTI (`ThreatIntelligenceAdminStatusView`, quota/pool/journal d'usage
  **plateforme entière**, volontairement pas tenant-scopé) est protégé par `permissions.IsAdminUser`
  (`is_staff`) plutôt que par `IsTenantMember` — vérifié qu'un utilisateur non-staff reçoit `403`
  (`test_api.py::TestAdminStatusAPI::test_non_staff_forbidden`). Le gate frontend (`StaffRoute.jsx`,
  lien conditionnel dans `Sidebar.jsx`) n'est qu'une commodité UX — la frontière réelle est côté API.
- Le webhook entrant (`POST /api/v1/webhooks/breachsense`) est le seul point d'entrée de toute la
  plateforme qui ne résout **pas** le tenant via `TenantScopingMiddleware`/`X-Tenant-Id` : Breachsense
  n'émet ni JWT ni en-tête tenant. Le tenant est résolu par une recherche dédiée et **non scopée**
  (`threat_intelligence.services.resolve_monitored_asset_by_provider_ref`, `all_objects`), le seul
  point du module explicitement autorisé à sortir du scoping ambiant — même logique de conception que
  `TenantScopingMiddleware._resolve_membership`, qui doit lui aussi interroger sans filtre pour
  *établir* le contexte avant de pouvoir le restreindre. Une notification pour un `ast`
  (référence d'actif) non reconnu est journalisée et ignorée, jamais associée au mauvais tenant par
  défaut (`test_services.py::TestWebhookIngestion::test_ingest_ignores_unmatched_asset_ref`).

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

**Mesures ajoutées en Phase 7 (Breachsense/CTI) — traitement le plus sensible de la plateforme à date**
- Contrairement aux secrets déjà couverts ci-dessus (mots de passe/TOTP appartenant à la plateforme
  elle-même, chiffrables), les secrets renvoyés par Breachsense (mots de passe, tokens, cookies de
  session) appartiennent à des tiers dont le compte a fuité — la décision (ADR-014) n'est **pas** de
  les chiffrer au repos comme un secret applicatif, mais de ne **jamais** les persister du tout :
  masquage récursif par nom de champ dès la normalisation
  (`threat_intelligence.providers.breachsense.normalizer.mask_payload`), avant toute écriture en base.
  Seule une forme tronquée non réversible (`secret_masked`, ex. `••••••23`) et un booléen
  (`secret_seen`) sont conservés.
  - **Test de propriété dédié** (pas une simple assertion unitaire) :
    `apps/threat_intelligence/tests/test_no_secret_persistence.py` génère des secrets connus pour
    chaque endpoint porteur de secret du palier Essentials, exécute le pipeline d'ingestion réel, puis
    interroge la ligne créée par SQL brut (pas l'ORM, pour ne pas pouvoir être trompé par une
    propriété Python qui ne reflèterait pas ce qui est réellement sur disque) et vérifie l'absence
    totale du secret d'origine. Ce test a intercepté une construction de payload de test erronée
    pendant l'écriture de la suite (voir `docs/journal.md`), confirmant qu'il exerce réellement
    l'invariant et ne passe pas trivialement.
- Aucun secret Breachsense ne transite par un `logger.*` (revue explicite de
  `threat_intelligence/services.py`, `tasks.py`, `providers/breachsense/*.py` — seuls des identifiants
  internes, endpoints, et compteurs sont journalisés) ni vers Sentry (absent du projet — voir A09) :
  le scrubbing est donc structurel (la donnée n'existe nulle part en clair après normalisation),
  pas un filtre appliqué après coup sur un flux qui la contiendrait encore.

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

**Mesures ajoutées en Phase 7 (Breachsense/CTI)**
- Non-persistance des secrets par conception (ADR-014, voir A02) plutôt que filtrage a posteriori.
- Provider CTI derrière une interface abstraite (ADR-013, `BreachIntelligenceProvider`) — aucun
  service métier n'importe le client HTTP Breachsense ou son SDK ; un changement de fournisseur ou un
  incident fournisseur reste cantonné à `providers/breachsense/`.
- Throttle Redis (token-bucket, script Lua atomique) sérialisant tous les appels sortants à 1 req/s —
  conçu pour qu'un `429` de la licence unique et partagée soit structurellement impossible en usage
  normal, pas seulement retenté après coup ; `QuotaManager` refuse toute nouvelle requête sous une
  marge de sécurité configurable avant même d'appeler l'API, pour ne jamais dépendre uniquement du
  throttle pour éviter un dépassement de licence.
- Anti-abus dédié sur le scan manuel (cooldown par tenant, `BREACHSENSE_SCAN_COOLDOWN_HOURS`) —
  distinct du rate limiting DRF générique, car ici la ressource protégée (le quota de licence) est
  partagée par toute la plateforme, pas par tenant : un seul tenant abusif pourrait épuiser le budget
  de tous les autres sans ce garde-fou spécifique.

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

**Mesures ajoutées en Phase 7 (Breachsense/CTI)**
- Le webhook (`BreachsenseWebhookView`) est explicitement exempté de CSRF (`@csrf_exempt`) — décision
  déclarée, pas un oubli : c'est un endpoint serveur-à-serveur sans session/cookie Django, la
  protection CSRF n'a pas de sens ici (elle protège contre des requêtes émises à l'insu d'un
  navigateur authentifié par cookie) ; testé qu'un client Django `enforce_csrf_checks=True` peut bien
  l'appeler (`test_webhook.py::test_no_csrf_token_required`).
- `BREACHSENSE_WEBHOOK_USERNAME`/`PASSWORD` (identifiants Basic Auth du webhook) suivent la même
  discipline que tout autre secret du projet : variables d'environnement uniquement,
  `backend/.env.example` ne contient que des placeholders vides.

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
    « RSC Mode CSRF Bypass Allows Action Execution Before 400 Response »). L'avis amont le précise
    explicitement : « This only affects your application if you are using the unstable RSC APIs » —
    cette application utilise un routage déclaratif classique `<Routes>/<Route>`, sans React Server
    Components ni action de données en mode framework, donc hors de portée de la vulnérabilité quelle
    que soit la version installée. Un correctif réel existe (`react-router@8.3.0`), mais la v8 a
    supprimé le paquet séparé `react-router-dom` dont dépend le projet — la migration implique de
    renommer la dépendance et tous les imports (`react-router-dom` → `react-router`) et de relire le
    guide de migration v7→v8, pas une simple montée de version. `npm audit fix` (sans `--force`) ne
    propose aucun correctif non cassant ; `--force` ne propose qu'un retour à la version 7.11.0 (7
    versions mineures en arrière), pas le vrai correctif. Migration v8 notée comme évolution possible
    hors urgence, pas comme correctif de sécurité immédiat (l'application n'est pas exposée).
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

**Mesures ajoutées en Phase 7 (Breachsense/CTI)**
- Le webhook Breachsense utilise HTTP Basic Auth — délibérément distinct de `JWTAuthentication` (ce
  n'est pas un utilisateur de la plateforme qui appelle, mais Breachsense lui-même, avec un secret
  partagé configuré des deux côtés). Comparaison en **temps constant**
  (`hmac.compare_digest`, `threat_intelligence/webhook_auth.py`) pour éviter une attaque par mesure de
  temps sur le nom d'utilisateur/mot de passe. Testé : absence d'en-tête `Authorization`, mauvais
  identifiants, et identifiants non configurés (`BREACHSENSE_WEBHOOK_USERNAME`/`PASSWORD` vides)
  renvoient tous `401` (`test_webhook.py::TestWebhookAuth`).

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

**Mesures ajoutées en Phase 7 (Breachsense/CTI)**
- Ingestion webhook idempotente au niveau base de données : `BreachFinding` porte une contrainte
  d'unicité `(tenant, dedup_hash)` — une notification redélivrée (comportement attendu d'un webhook,
  Breachsense pouvant retenter en cas de non-`200`) ne crée jamais de doublon, vérifié bout en bout
  (`test_webhook.py::test_redelivered_payload_is_idempotent`) plutôt que supposé.
- Tâche Celery (`run_breach_scan_task`) suit le même pattern retry/idempotence que le reste de la
  plateforme (garde sur le statut du job, cf. `apps.ai_assistant.tasks`) — testé y compris le cas
  « job déjà terminé » (redelivery no-op) et « échec définitif après épuisement des tentatives ».

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

**Mesures ajoutées en Phase 7 (Breachsense/CTI)**
- Ce gap préexistant (pas de `LOGGING` dict, pas de Sentry) s'applique tel quel au nouveau module —
  revérifié qu'aucun des fichiers `threat_intelligence/*.py` n'écrit de secret, d'email, ou de domaine
  réel dans un `logger.*` (seuls des identifiants internes et des compteurs de requêtes). C'est
  d'autant plus important ici que ce module manipule les données les plus sensibles de la
  plateforme (voir A02) : la recommandation Phase 6 ci-dessus (LOGGING dict + outil de suivi
  d'erreurs) reste valable et gagne en urgence pour ce module en particulier, une fois en production.

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

**Mesures ajoutées en Phase 7 (Breachsense/CTI)**
- Pas de nouvelle surface SSRF : contrairement aux checks de `apps.monitoring`, les appels sortants
  du client Breachsense (`BreachsenseClient`) ciblent exclusivement `BREACHSENSE_BASE_URL` (une
  constante de configuration, jamais dérivée d'une entrée utilisateur) — le domaine/URL déclaré par
  le tenant n'est jamais utilisé pour construire une requête HTTP arbitraire, seulement transmis comme
  **paramètre** (`domain=`/`email=`) d'une requête vers l'API Breachsense fixe. Le webhook, lui, est
  entrant (Breachsense appelle la plateforme, jamais l'inverse) — sans surface SSRF par construction.

---

## Phase 7 — Renseignement sur la menace (Breachsense) : synthèse des nouveaux flux et RGPD

Cette section rassemble, en un seul endroit, les flux de données introduits par
`apps.threat_intelligence` (détaillés catégorie par catégorie ci-dessus et dans ADR-013/ADR-014) —
demandé explicitement pour cette phase en plus des ajouts dispersés dans le corps du document.

### Nouveaux flux de données

1. **Requête sortante (scan)** : `threat_intelligence.services.execute_scan` → `BreachsenseClient` →
   API Breachsense (domaine/email du tenant en paramètre de requête, jamais de PII supplémentaire) →
   réponse potentiellement porteuse de secrets → **masquage immédiat** (`normalizer.py`) → persistance
   du seul résultat masqué (`BreachFinding`). Consomme le quota `query` partagé (throttlé, quotaté).
2. **Notification entrante (webhook)** : Breachsense → `POST /api/v1/webhooks/breachsense` (Basic
   Auth) → résolution du tenant via `MonitoredAsset.provider_ref` → même pipeline de normalisation/
   masquage que le scan → `BreachFinding` + `Alert`. Hors quota `query`, limité au pool de 15 slots.
3. **Sortie vers l'IA (pseudonymisée)** : `BreachFinding` (jamais `raw_data`, jamais un secret) →
   `build_assistant_context`/`build_weather_context` → pipeline de pseudonymisation existant (ADR-005)
   → API Claude. Aucun nouveau point d'appel IA (réutilise Haiku déjà routé pour l'assistant/la
   météo — sobriété, cadrage §8).
4. **Sortie vers le tenant (frontend)** : `BreachFindingSerializer` exclut explicitement `raw_data` —
   le tenant voit l'identifiant masqué/en clair (selon qu'il s'agit ou non de son propre email pro),
   le type de fuite, la gravité, et un indicateur `secret_seen` — jamais `raw_data`.

### RGPD

- **Personnes concernées** : les membres du tenant (si l'identifiant fuité est leur email
  professionnel) et, incidemment, des tiers (clients, partenaires) dont l'identifiant apparaît dans
  une fuite liée à un actif du tenant.
- **Base légale** : exécution du contrat pour les données concernant le tenant et ses membres (le
  tenant a explicitement déclaré l'actif et sollicité sa surveillance) ; intérêt légitime strictement
  minimisé (identifiant masqué uniquement, jamais conservé en clair) pour les données concernant des
  tiers non-utilisateurs de la plateforme — voir ADR-014 §4/§6 pour le détail de l'arbitrage.
- **Non-conservation des secrets** : absolue, par construction (ADR-014, voir A02 ci-dessus) — aucune
  fonctionnalité de la plateforme ne permet d'afficher un secret en clair à qui que ce soit.
- **Durée de rétention** : alignée sur la politique déjà en vigueur pour les résultats de check bruts
  (cadrage §7, 90 jours) pour les `BreachFinding` non traités ; un finding marqué traité/ignoré est
  conservé à des fins d'audit de conformité, au même titre qu'une action du plan d'action. La **purge
  automatique planifiée** des findings non traités de plus de 90 jours n'est **pas** implémentée dans
  cette phase (reste-à-faire explicite, voir `docs/journal.md`) — livraison du flux d'ingestion et de
  l'affichage d'abord, purge planifiée ensuite.
- **Transparence** : le tenant voit, sans appel supplémentaire, l'état du quota et le cooldown avant
  de déclencher un scan (`GET /api/v1/threat-intelligence/status/`), dans le même esprit de
  transparence que l'encart « données transmises » de la Phase 4 pour l'IA.

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
| A09 Logging/Monitoring | **Gap identifié** — pas de `LOGGING` dict ni d'outil de suivi d'erreurs ; recommandé pour Phase 6 (plus critique désormais avec le CTI) |
| A10 SSRF | Couvert — garde-fou dédié, testé, limite TOCTOU documentée et acceptée |
| **Phase 7 — Breachsense/CTI** | Couvert — non-stockage des secrets par conception et testé par propriété (ADR-014), étanchéité tenant testée sur tous les nouveaux endpoints, webhook en Basic Auth temps constant + idempotent, throttle/quota anti-429 et anti-dépassement de licence, aucune nouvelle surface SSRF |
