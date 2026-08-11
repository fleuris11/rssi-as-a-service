# 013 — Intégration de Breachsense comme source de détection de compromissions

## Contexte

Le cadrage (`docs/cadrage_rssi_as_a_service.md` §3.2, roadmap V2) prévoyait la détection de
fuites de comptes via l'API **Have I Been Pwned (HIBP)**. Le prompt de mission Phase 7 remplace
explicitement ce choix par **Breachsense** (Cyber Threat Intelligence), palier **Essentials**.

> **Écart documenté avec le cadrage** : cette substitution n'est pas tranchée silencieusement.
> Elle est actée ici et rapportée dans `docs/journal.md` (session Phase 7). Justification :
> Breachsense expose, en plus d'une API de requête (comme HIBP), un **webhook de monitoring
> continu** et des catégories de fuite plus larges (identifiants volés par stealer malware,
> sessions/cookies compromis, identités non-humaines, mentions dark web, documents fuités,
> surface d'attaque) — pertinent pour la promesse produit « surveillance continue » du cadrage
> §1.3, alors que HIBP est une API de requête ponctuelle sans webhook temps réel. Le cadrage
> (§3.2) sera mis à jour en conséquence (Breachsense passe en « intégré », HIBP retiré de la
> roadmap V2).

Contraintes structurantes de la licence Breachsense Essentials (une licence unique, partagée par
toute la plateforme, pas par tenant) :
- **1000 requêtes `query`/mois** partagées entre tous les tenants ;
- **15 actifs monitorés maximum** (webhook temps réel), au total, tous tenants confondus ;
- **1 requête/seconde** soutenue, bursts de 5, sur la licence unique — tout appel HTTP vers
  Breachsense (requête ou gestion de compte) partage ce budget ;
- l'API renvoie des **secrets en clair** (mots de passe, tokens, cookies de session) dans les
  réponses — règle absolue : ne jamais les persister (voir ADR-014) ;
- clé lue depuis `BREACHSENSE_LICENSE_KEY` (variable d'environnement).

Ces contraintes sont **globales à la plateforme**, pas par tenant — à la différence du quota IA
(`AIUsageQuota`, par tenant). Toute conception qui traiterait le quota ou le pool de 15 slots
comme une ressource par tenant serait fausse et mènerait à un dépassement de licence.

## Options étudiées

**A. Appeler l'API Breachsense directement depuis les services concernés (monitoring,
notifications, ai_assistant).**
Rejeté : couple tout le code métier à un fournisseur commercial précis ; rend impossible un
changement de fournisseur ou l'ajout d'un second fournisseur CTI sans réécriture ; rend le mock
en CI plus fragile (surface de mock dispersée).

**B. Abstraction par interface de provider (inversion de dépendance), une seule implémentation
concrète Breachsense au départ.**
Retenu. Une interface `BreachIntelligenceProvider` (app `threat_intelligence`) définit le
contrat métier (`scan_domain`, `scan_email`, `register_monitored_asset`,
`unregister_monitored_asset`, `list_monitored_assets`, `get_remaining_quota`,
`send_test_alert`, `normalize_webhook_payload`). `BreachsenseProvider` l'implémente contre
l'API réelle. Le reste du code (services, tasks, vues) ne dépend que de l'interface — récupérée
via une factory `get_provider()` — jamais du SDK/client HTTP concret. Un `NullProvider`
(no-op) est retourné quand `BREACHSENSE_LICENSE_KEY` est absente (dev/CI sans licence),
et le back-office peut afficher un état « CTI non configuré » plutôt qu'une erreur 500.

**C. Pour le monitoring continu : privilégier le mode requête (polling périodique) plutôt que
le webhook, par simplicité d'implémentation.**
Rejeté : le quota de requêtes (1000/mois, partagé) est trop faible pour un polling périodique
réel (10 actifs × plusieurs endpoints × plusieurs fois par jour épuise le quota en quelques
jours). Le webhook Breachsense (notifications poussées, hors quota `query`) est donc le canal
**privilégié** pour la surveillance continue ; le mode requête est réservé au **scan de
diagnostic** ponctuel (déclenché à la déclaration d'un actif, ou manuellement avec garde-fous).

## Décision

1. **Abstraction provider** (option B) : app Django `threat_intelligence`, interface
   `BreachIntelligenceProvider` (ABC), implémentation `BreachsenseProvider`, fallback
   `NullProvider`. Aucun autre module n'importe le client HTTP Breachsense directement.

2. **Deux modes d'usage, budgets distincts** :
   - **Mode requête** (`run_breach_scan`) : consomme le quota `query` (1000/mois partagé).
     Déclenché automatiquement à la première déclaration d'un actif par un tenant (effet
     « waouh » de l'onboarding) via un signal Django `post_save` sur `monitoring.Asset` — ce
     choix garde `apps.monitoring` totalement ignorant de `threat_intelligence` (sens de
     dépendance correct : threat_intelligence → monitoring, jamais l'inverse). Déclenchable
     aussi manuellement (bouton), protégé par un **cooldown anti-abus par tenant**
     (`BREACHSENSE_SCAN_COOLDOWN_HOURS`, 24h par défaut) en plus du contrôle de quota.
   - **Mode webhook** (monitoring continu) : hors quota `query`, mais limité aux **15 slots**
     de la licence. L'inscription d'un actif au monitoring webhook (`register_monitored_asset`)
     est une **action explicite et distincte** de la déclaration de l'actif ou du scan initial —
     pas automatique — précisément parce que le pool de 15 slots est une ressource rare et
     partagée par toute la plateforme : l'automatiser sur chaque déclaration d'actif
     l'épuiserait en quelques tenants. Le service refuse proprement (message clair) quand les
     15 slots sont occupés.

3. **Throttling centralisé** : un token-bucket Redis (1 req/s, bursts de 5) sérialise **tous**
   les appels sortants vers Breachsense (requêtes de scan **et** appels de gestion de compte
   `/account`), quel que soit le worker Celery ou le processus qui les émet — la licence est
   unique, le throttle doit donc l'être aussi (clé Redis globale, pas par tenant). Les
   notifications entrantes du webhook ne passent pas par ce throttle (ce sont des requêtes
   *reçues*, pas émises).

4. **QuotaManager** : source de vérité = l'endpoint `/account?action=remaining` de Breachsense
   (mis en cache court, quelques minutes, pour éviter de consommer le quota rien que pour le
   consulter). Un budget de sécurité configurable (`BREACHSENSE_QUOTA_SAFETY_MARGIN`, 50 requêtes
   par défaut) fait refuser proprement toute nouvelle requête `query` sous ce seuil, avant même
   d'appeler l'API. Chaque requête consommée est journalisée (`BreachIntelligenceUsage`, par
   tenant, pour l'attribution et l'audit) même si le budget lui-même est global.

5. **Réutilisation du moteur d'alertes existant** (Phase 3, `apps.monitoring`) : ajout d'un
   type d'alerte `BREACH_COMPROMISE` à `monitoring.Alert.AlertType`, et d'une fonction publique
   `monitoring.services.open_or_update_alert(...)` (extraction de la logique déjà privée
   `_open_or_update_alert`) que `threat_intelligence.services` appelle — pas de duplication du
   moteur de dédoublonnage/escalade d'alertes. `BreachFinding.asset` est un FK obligatoire vers
   `monitoring.Asset` : une fuite est toujours rattachée à un actif **déclaré par le tenant**,
   dans la continuité du principe déjà posé par l'ADR-010 (« un actif n'est vérifié que s'il est
   déclaré »), étendu ici à « une fuite n'est rapportée que sur un actif déclaré ».

6. **Pattern job asynchrone** (réutilisation d'ADR-011) : `BreachScanJob` reprend le pattern
   POST-crée-un-job / GET-interroge-le-statut déjà utilisé par `apps.ai_assistant.AIJob`.
   Exécution exclusivement via Celery, file `monitoring` (le scan de fuites est un
   sous-domaine de la surveillance, pas de l'IA — la file `ai` reste réservée aux appels
   Anthropic).

7. **Sécurisation du webhook** : `POST /api/v1/webhooks/breachsense` est protégé par
   authentification HTTP Basic (identifiants dans `BREACHSENSE_WEBHOOK_USERNAME` /
   `BREACHSENSE_WEBHOOK_PASSWORD`, comparaison en temps constant), exempté de CSRF (endpoint
   externe, pas de session Django), et **ne** passe **pas** par le middleware de résolution de
   tenant habituel (pas de JWT, pas d'en-tête `X-Tenant-Id` côté Breachsense) : le tenant est
   résolu en interne via `MonitoredAsset` (recherche non-scopée, seul point du module autorisé
   à interroger `all_objects` sans tenant de contexte, comme le fait déjà
   `TenantScopingMiddleware` pour résoudre le tenant à partir du JWT). L'ingestion est
   idempotente (clé de dédoublonnage par tenant) : une même notification reçue deux fois ne
   crée pas de doublon.

## Conséquences

- Changer de fournisseur CTI (ou en ajouter un second) plus tard ne touche que le module
  `threat_intelligence.providers` — le reste de la plateforme (services, tasks, vues,
  frontend) ne connaît que l'interface abstraite.
- Le quota et le pool de 15 slots étant des ressources **globales**, tout futur ajustement de
  licence (palier supérieur) ne change que des constantes de configuration
  (`BREACHSENSE_QUOTA_SAFETY_MARGIN`, taille du pool), pas la logique.
- Le webhook réel ne sera testable en conditions réelles qu'au déploiement (URL publique
  requise côté Breachsense) — voir `docs/journal.md` pour le protocole de test avec payloads
  simulés utilisé en attendant, et le smoke test à réaliser manuellement avec la licence réelle.
- L'extension future « premium-marketplace » du palier supérieur Breachsense n'est pas
  implémentée (hors périmètre de la licence Essentials) — notée en commentaire dans le client
  HTTP et dans le cadrage (roadmap) comme extension future.
- Le cadrage §3.2 est mis à jour : Breachsense remplace HIBP dans la roadmap, qui passe de
  « architecturée, non développée » à « intégrée ».

## Amendement (Phase 8B) — séparation « fuite avérée » / « signal avant-coureur »

Le point 5 ci-dessus rattache tout `BreachFinding` à un actif déclaré, sans distinguer ce qui est
un **constat** (une donnée a fuité) de ce qui est un **signal** (l'exposition publique bouge). La
Phase 8A avait introduit cette distinction à l'affichage (carte « Signaux avant-coureurs ») tout en
laissant les mêmes findings dans la liste des compromissions — donc affichés deux fois, ce qui
diluait la distinction au lieu de la porter.

La Phase 8B tranche :

- **`services.list_findings` exclut désormais par défaut** les endpoints pré-incident (`radar`,
  `darkweb`, `asm`). La liste « Compromissions » ne montre plus que des fuites avérées.
- La carte « Signaux avant-coureurs » porte ses **propres actions** de traitement (mêmes
  transitions de statut, mêmes permissions que la liste) et un historique des signaux traités —
  c'était la condition pour pouvoir les retirer de la liste sans les rendre intraitables.
- Le paramètre `include_pre_incident=True` restitue la vue complète pour les usages qui raisonnent
  sur l'exposition d'un actif et non sur une liste : le fil d'exposition (ADR-016), le contexte de
  l'assistant IA et celui de la météo quotidienne. Ces trois appelants ont été explicitement mis à
  jour lors du changement — le défaut plus restrictif aurait sinon rétréci silencieusement ce que
  l'IA et la météo voient.

Le modèle de données est inchangé : c'est une décision de **présentation et de vocabulaire**, pas
de stockage. Un signal radar reste un `BreachFinding` rattaché à un actif déclaré, exactement comme
le prévoyait le point 5.
