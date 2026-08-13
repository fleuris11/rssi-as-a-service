# Journal de bord

Ce journal consigne, à la fin de chaque session de travail, ce qui a été fait, les décisions
prises, les difficultés rencontrées et leurs solutions, et ce qu'il reste à faire. Il alimente
directement les dossiers de certification (RNCP38822) — factuel et précis.

---

## 2026-08-04 — Phase 1 : socle du projet

### Contexte
Première session de développement effective, après cadrage (`docs/cadrage_rssi_as_a_service.md`).
Dépôt GitHub `fleuris11/rssi-as-a-service` créé, vide. Objectif de la session : un environnement
de dev complet et une base saine (structure monorepo, auth JWT, multi-tenancy, RBAC, tests, CI,
documentation), sans toucher à l'IA ni à la surveillance (phases suivantes).

### Réalisé

**Structure & outillage**
- Monorepo initialisé : `backend/`, `frontend/`, `docs/`, `docs/adr/`, `.github/workflows/`.
- `.gitignore` / `.gitattributes` (fin de ligne LF forcée, cohérence Windows → conteneurs Linux).
- Dépôt Git initialisé, remote `origin` pointée vers le dépôt GitHub fourni.

**Backend (Django 5.2 + DRF)**
- Squelette du projet : `config/` (settings environment-driven via `django-environ`, urls, wsgi,
  asgi) + `apps/` (`accounts`, `tenants`, `platform_admin`).
- `apps.accounts` : modèle `User` personnalisé (email comme identifiant, UUID en clé primaire),
  manager dédié, endpoints `register/`, `token/`, `token/refresh/`, `token/blacklist/`, `me/`.
- `apps.tenants` : modèles `Tenant` et `Membership` (rôles `admin` / `contributor` / `reader`,
  contrainte d'unicité tenant+utilisateur) ; `TenantScopedModel` (base abstraite réutilisable pour
  toute future ressource métier tenant-scopée) ; `TenantScopedManager` qui **échoue fermé** :
  sans tenant résolu dans le contexte de la requête, retourne un queryset vide plutôt que
  toutes les lignes ; `TenantScopingMiddleware` qui authentifie via JWT, résout le tenant depuis
  l'en-tête `X-Tenant-Id` et l'appartenance de l'utilisateur, expose `request.tenant` /
  `request.membership`, et positionne un `contextvars.ContextVar` le temps de la requête ;
  permissions DRF `IsTenantMember` / `IsTenantAdmin` ; endpoints `GET /api/v1/tenants/` (mes
  entreprises) et `GET /api/v1/tenants/members/` (membres de l'entreprise sélectionnée).
- `apps.platform_admin` : scaffoldée (structure d'app, aucune fonctionnalité) — le back-office
  superviseur (US-1.4) est prévu dans une session ultérieure.
- JWT (`djangorestframework-simplejwt`) : accès 15 min, refresh 7 jours, **rotation +
  blacklist des refresh tokens à chaque utilisation** (app `token_blacklist` activée).
- Mots de passe : validateurs Django avec longueur minimale 12 (priorité longueur > complexité,
  conforme au cadrage §6) ; vérification contre une liste de mots de passe compromis (API type
  HIBP) non implémentée — hors périmètre de cette session, à faire en durcissement (Phase 5).
- Cache Redis configuré (`django.core.cache.backends.redis.RedisCache`), pas encore utilisé
  fonctionnellement (arrivera avec le rate limiting / Celery en phases suivantes).
- `drf-spectacular` pour le schéma OpenAPI (`/api/v1/schema/swagger-ui/`), pagination DRF
  systématique, endpoint `/healthz`.
- Tests `pytest` + `pytest-django` : 25 tests, 97 % de couverture sur `apps/`. Comprend
  notamment les **tests d'étanchéité multi-tenant** exigés par CLAUDE.md
  (`apps/tenants/tests/test_isolation.py`) : le manager scopé ne renvoie rien hors contexte,
  ne renvoie que les lignes du tenant courant une fois le contexte positionné, l'API rejette une
  requête sans en-tête `X-Tenant-Id` (403) et une tentative d'accès à un tenant tiers (403).
- `ruff` configuré (`backend/pyproject.toml`) : `ruff check` et `ruff format --check` passent.

**Frontend (React 18 + Vite + Tailwind)**
- Scaffold via `npm create vite` puis réaligné sur la stack imposée : React fixé en 18.x (le
  scaffold par défaut proposait React 19), remplacement d'`oxlint` (lint par défaut du template
  Vite actuel) par **ESLint** (`eslint.config.js`, flat config) conformément à CLAUDE.md,
  ajout de Tailwind CSS v4 (plugin Vite officiel `@tailwindcss/vite`, zero-config).
  Assets de démo Vite/React retirés, page d'accueil remplacée par un placeholder minimal.
- `npm run lint` et `npm run build` passent.

**Infrastructure**
- `docker-compose.yml` à la racine : `postgres` (16-alpine), `redis` (7-alpine), `web` (build
  `backend/Dockerfile`, montage du code en volume pour le rechargement à chaud en dev).
  `worker`/`beat` (Celery) volontairement absents — prévus en Phase 3, comme demandé.
- `backend/Dockerfile` : image `python:3.12-slim`, dépendances via `psycopg[binary]` (pas de
  compilation nécessaire), utilisateur non-root, `entrypoint.sh` invoqué via `sh` (et non par
  bit exécutable) pour rester fonctionnel même quand le bind-mount de dev écrase les
  permissions du fichier — point d'attention identifié en environnement de développement
  Windows. L'entrypoint attend la disponibilité de Postgres puis applique les migrations avant
  de lancer la commande.
- CI GitHub Actions (`.github/workflows/ci.yml`) : job `backend` (services Postgres + Redis,
  `ruff check` + `ruff format --check`, contrôle de migrations manquantes, `pytest --cov`) et
  job `frontend` (`eslint`, `vite build`).
- `README.md` : instructions de démarrage (Docker en priorité, mode sans Docker en option),
  description des endpoints d'authentification/tenants disponibles.

### Difficultés rencontrées et solutions
- **Python 3.12 absent du poste de dev** (seul 3.13 disponible via `py launcher`) : le
  virtualenv local utilise donc 3.13, mais l'image Docker (source de vérité pour la CI et la
  prod) reste bien épinglée sur `python:3.12-slim`, conformément à CLAUDE.md.
- **Port 5432 déjà occupé** par un conteneur Postgres d'un autre projet sur la même machine :
  le service `postgres` du projet est exposé sur le port hôte **5433** (le port interne au
  réseau Docker, utilisé par le conteneur `web`, reste 5432, donc aucun changement applicatif).
  Documenté dans le README et les fichiers `.env.example`.
- **`ruff` (règle `DJ012`, style Django)** signalait à tort un mauvais ordre entre le manager
  personnalisé `TenantScopedManager` et le manager `all_objects` : l'heuristique de la règle ne
  reconnaît pas un manager personnalisé déclaré en premier suivi de `models.Manager()`. Résolu
  en déclarant `all_objects` avant `objects` et en fixant explicitement
  `Meta.default_manager_name = "objects"` pour garantir que le manager scopé reste bien le
  manager par défaut malgré l'ordre de déclaration.
- **`no-unused-vars` d'ESLint ne reconnaissait pas les identifiants utilisés uniquement en JSX**
  (`StrictMode`, `App` dans `main.jsx`) : `eslint-plugin-react-hooks` seul ne suffit pas, il
  faut `eslint-plugin-react` (et sa règle `jsx-uses-vars`) pour que le linter comprenne qu'un
  composant utilisé en JSX n'est pas « inutilisé ». Ajouté à la configuration.
- **Hachage des mots de passe lent en tests** (PBKDF2, ~100 s pour la suite complète car chaque
  test crée un ou plusieurs utilisateurs) : un hasher rapide (`MD5PasswordHasher`) est activé
  automatiquement pour les tests via une fixture `autouse` dans `conftest.py`, ramenant la
  suite à ~2 s. Sans impact en dehors des tests (le hasher de production reste celui par défaut
  de Django, PBKDF2).

### Décisions prises (hors ADR formel — voir « reste à faire »)
- Authentification par email (pas de `username` séparé) : cohérent avec un SaaS B2B où
  l'identifiant naturel de connexion est l'email professionnel.
- `Tenant` et `User` utilisent des clés primaires UUID (évite l'énumération d'identifiants
  séquentiels, cohérent avec l'usage de `X-Tenant-Id` côté API).
- La sélection du tenant actif se fait via un en-tête `X-Tenant-Id` plutôt que par un token
  JWT par-tenant : un utilisateur peut appartenir à plusieurs entreprises, l'en-tête permet de
  changer de contexte sans réémettre de token.

### Reste à faire (sessions suivantes)
- Rédiger en version complète les ADR 001 à 005 (actuellement seulement résumés dans le tableau
  du cadrage §5) — action listée dans les prochaines étapes immédiates du cadrage (§14).
- 2FA TOTP (US-1.3, priorité « Should ») et verrouillage progressif après échecs
  d'authentification — non demandés pour cette session, à traiter en durcissement (Phase 5) ou
  plus tôt si le calendrier le permet.
- Vérification des mots de passe contre une liste de mots de passe compromis (HIBP ou
  équivalent).
- Rate limiting (Redis est configuré comme cache mais pas encore utilisé pour throttling DRF).
- Back-office `platform_admin` (supervision des tenants, quotas, état de la plateforme —
  US-1.4) : app scaffoldée cette session, contenu à construire.
- Endpoint d'invitation de collaborateurs (US-1.2) : le modèle `Membership` et la permission
  `IsTenantAdmin` sont prêts, il manque le flux d'invitation par email (dépend de l'app
  `notifications`, Phase 3).
- Phase 2 (diagnostic ANSSI, scoring, plan d'action) à démarrer selon le phasage du cadrage.

---

## 2026-08-04 — Vérification et durcissement du socle avant revue externe

### Contexte
Session de vérification/durcissement demandée avant une revue externe du socle livré en Phase 1 —
aucune nouvelle fonctionnalité, uniquement audit, tests supplémentaires et documentation. Le
travail de la session précédente a d'abord été poussé sur `origin/main` (`git push -u origin
main`), le dépôt distant était vide jusque-là.

### Vérifications effectuées

**Sécurité du multi-tenancy (priorité absolue)**
Audit de `TenantScopingMiddleware` : le flux implémenté en Phase 1 était déjà conforme à
l'exigence — JWT → utilisateur authentifié (`JWTAuthentication().authenticate()`) → recherche
d'une `Membership` entre cet utilisateur et le `tenant_id` demandé (`Membership.all_objects`,
seul point autorisé à interroger sans filtre tenant puisqu'il sert justement à le résoudre) →
403 et **aucun** contexte de tenant positionné si cette `Membership` n'existe pas. L'en-tête
`X-Tenant-Id` n'est donc jamais fait confiance seul : un en-tête sans JWT valide, ou un JWT valide
sans `Membership` correspondante, ne débloque jamais l'accès. Aucune correction de code n'a donc
été nécessaire sur ce point ; l'effort a porté sur le **renforcement des tests** pour le prouver
explicitement, scénario par scénario, dans `apps/tenants/tests/test_isolation.py` (nouvelle
classe `TestTenantScopingMiddlewareAttackScenarios`, testée contre `GET /api/v1/auth/me/` — un
endpoint qui n'a *pas* sa propre permission `IsTenantMember` — spécifiquement pour prouver que le
403 vient bien du middleware et non d'une vérification de vue) :
- **(a)** en-tête pointant vers un tenant dont l'utilisateur n'est pas membre → 403 ;
- **(b)** en-tête absent → la requête passe (le middleware n'exige pas de tenant par lui-même)
  mais sans contexte de tenant, donc toute ressource tenant-scopée reste vide (couvert par
  ailleurs par `TestTenantScopedManagerFailsClosed` et
  `TestTenantMemberListAPI.test_requires_tenant_header`) ;
- **(c)** en-tête syntaxiquement valide (UUID) mais pointant vers un tenant inexistant → 403 ;
  ajout d'un test bonus (en-tête malformé, pas un UUID) confirmant un 403 propre plutôt qu'une
  erreur 500 ;
- **(d)** `Membership` révoquée (supprimée) entre l'émission du JWT et la requête → 403, même si
  le token reste valide. *Point de vigilance documenté* : le modèle `Membership` ne porte pas
  aujourd'hui de champ de désactivation « douce » (`is_active`) distinct de la suppression — seule
  la suppression de la ligne est testée, car ajouter un tel champ constituerait une nouvelle
  fonctionnalité hors du périmètre strict de cette session. À évaluer pour une session dédiée si le
  besoin de révoquer un accès sans perdre l'historique (qui a été membre, quand) se confirme.

Suite complète : 30 tests passent (contre 25 avant cette session), couverture inchangée à 97 % sur
`apps/`.

**Cohérence CI/prod**
Vérifié : `.github/workflows/ci.yml` épingle déjà `python-version: "3.12"` via
`actions/setup-python@v5` pour le job `backend`, cohérent avec `backend/Dockerfile`
(`FROM python:3.12-slim`). La CI ne dépend jamais de la version de Python installée sur un poste
de développeur. Aucune correction nécessaire.

**Hygiène du dépôt**
- Recherche sur l'historique Git complet (`git log --all`, noms de fichiers et contenu des diffs)
  : aucun fichier `.env` réel, clé privée, ou secret n'a jamais été commité — seuls
  `.env.example` et `backend/.env.example` (valeurs placeholder uniquement, ex. `change-me`)
  apparaissent dans l'historique.
- `.gitignore` renforcé : plusieurs règles étaient limitées à `backend/` ou `frontend/` alors
  qu'une couverture globale est plus sûre en défense en profondeur (`backend/venv/` →  `venv/` et
  `.venv/` sans préfixe de chemin, `frontend/node_modules/` → `node_modules/` global,
  `db.sqlite3`/`db.sqlite3-journal` littéraux → `*.sqlite3`/`*.sqlite3-journal` en motif). Vérifié
  qu'aucun fichier suivi par Git n'était affecté par ce changement (`git status` vide après
  modification).
- `.env.example` (racine et `backend/`) confirmés présents, documentés en commentaires, sans
  valeur réelle.

### Documentation produite
Rédaction des ADR 001 à 005 en version complète (`docs/adr/`), au format Contexte → Options
étudiées → Décision → Conséquences, conformément au registre résumé du cadrage §5 :
- **001** — Monolithe modulaire Django (vs microservices / monolithe non structuré).
- **002** — Multi-tenancy par schéma partagé + `tenant_id` (vs base par tenant / schéma par
  tenant), documentant l'implémentation réelle de `TenantScopedManager` et
  `TenantScopingMiddleware` livrée en Phase 1.
- **003** — Celery + Redis pour l'asynchrone (vs cron/scripts / appels synchrones / RQ).
- **004** — API Claude, routage Haiku/Sonnet par cas d'usage (vs modèle unique haut de gamme / LLM
  auto-hébergé).
- **005** — Pseudonymisation réversible avant tout appel IA (vs contexte brut / anonymisation
  irréversible).

### Difficultés rencontrées et solutions
Aucune anomalie de sécurité trouvée dans le middleware existant — la principale difficulté de la
session a été de choisir comment traiter l'écart entre le scénario demandé « membership
supprimée/désactivée » et l'absence de champ de désactivation dans le modèle actuel : plutôt que
d'ajouter ce champ (ce qu'interdisait le périmètre de la session) ou d'ignorer silencieusement une
partie du scénario demandé, le choix a été de tester ce qui est réellement modélisé aujourd'hui (la
suppression) et de documenter explicitement l'écart ci-dessus et dans le résumé transmis à
l'issue de la session.

### Reste à faire (sessions suivantes)
- Évaluer l'ajout d'un champ de désactivation « douce » sur `Membership` (révoquer l'accès à un
  tenant sans perdre l'historique d'appartenance) si le besoin se confirme — actuellement, seule la
  suppression de la ligne retire l'accès.
- Les éléments déjà listés en fin de session précédente restent d'actualité (2FA TOTP, liste de
  mots de passe compromis, rate limiting, back-office `platform_admin`, invitation de
  collaborateurs, Phase 2).

---

## 2026-08-04 — Nettoyage de l'historique Git (attribution des commits)

### Contexte
Les commits des deux sessions précédentes portaient tous un footer `Co-Authored-By: Claude Sonnet
5 <noreply@anthropic.com>` (ajout automatique de l'outil utilisé pour développer). Demande de
s'assurer que l'historique du dépôt reflète uniquement l'auteur humain du projet.

### Actions effectuées
1. **`.claude/settings.json`** (nouveau fichier, suivi par Git) : `"includeCoAuthoredBy": false`
   pour que les futurs commits générés via l'outil n'ajoutent plus ce footer.
2. **Identité Git** : `git config --local user.name`/`user.email` n'étaient pas positionnés
   explicitement (seul `user.email` existait dans le `.gitconfig` global) ; les 7 commits déjà
   créés portaient malgré tout la bonne identité (`Fleuris EGBOOU
   <fleurismeweegboou5@gmail.com>`, cohérente avec le compte GitHub `fleuris11`), probablement
   injectée par l'outil au moment du commit. Fixé explicitement en config locale du dépôt pour ne
   plus dépendre de ce comportement implicite.
3. **Réécriture de l'historique** : `git filter-repo` n'était pas installé et son installation via
   pip a échoué dans cet environnement ; utilisé `git filter-branch` à la place (`--env-filter`
   pour forcer auteur et committeur sur les 7 commits, `--msg-filter` — un petit script Python
   dédié, `sys.stdout.reconfigure(newline="\n")` nécessaire pour éviter que Python n'introduise des
   CRLF parasites sur Windows — pour retirer la ligne `Co-Authored-By`). Vérifié après coup que le
   contenu (arbre des fichiers) de chaque commit est resté strictement identique — seuls les
   métadonnées (auteur, committeur, message) ont changé — puis nettoyé la référence de sauvegarde
   `refs/original/` laissée par `filter-branch` et exécuté un `git gc --prune=now`.
4. **Force-push** : `git push --force-with-lease origin main`. Vérifié après coup par un
   `git fetch` que `origin/main` correspond exactement à l'historique réécrit et ne contient plus
   aucune occurrence de « Co-Authored-By ».

### Résultat vérifié
```
git log --format='%h %an %ae %s'
afe6f6a Fleuris EGBOOU fleurismeweegboou5@gmail.com docs: ADR 001-005 and journal entry for the hardening session
86d04a1 Fleuris EGBOOU fleurismeweegboou5@gmail.com test(tenants): harden tenant-isolation coverage and gitignore
a951e07 Fleuris EGBOOU fleurismeweegboou5@gmail.com docs: README with local dev instructions and Phase 1 journal entry
e9b3608 Fleuris EGBOOU fleurismeweegboou5@gmail.com build: docker-compose (web, postgres, redis) and CI pipeline
fdbf040 Fleuris EGBOOU fleurismeweegboou5@gmail.com feat(frontend): React 18 + Vite + Tailwind scaffold
f7e2cff Fleuris EGBOOU fleurismeweegboou5@gmail.com feat(backend): Django 5 + DRF skeleton with JWT auth and multi-tenancy
26f8dca Fleuris EGBOOU fleurismeweegboou5@gmail.com chore: initialize monorepo structure
```
Les 7 SHA ont changé (réécriture d'historique attendue) ; tout collaborateur ou clone existant du
dépôt devra re-cloner ou réaligner sa branche locale (`git fetch && git reset --hard origin/main`)
après cette opération.

### Point de vigilance
Le dépôt distant étant repassé de 7 commits « anciens SHA » à 7 commits « nouveaux SHA » par force
push, toute référence externe à un ancien SHA (ex. lien direct vers un commit dans une discussion)
serait cassée. Sans conséquence ici : dépôt encore au stade socle, aucune PR ni référence externe
connue à ce jour.

---

## 2026-08-04 — Phase 2 : diagnostic de maturité et plan d'action

### Contexte
Parcours diagnostic complet demandé, de bout en bout : questionnaire ANSSI → score/radar →
plan d'action priorisé, conformément au cadrage §3.1 (modules M2, M3) et §4. IA, monitoring et
notifications explicitement exclus de cette session.

### Réalisé

**Référentiel ANSSI (`backend/data/anssi_hygiene.json`)**
- Les 42 mesures du guide d'hygiène informatique ANSSI, réparties en 10 domaines fidèles à la
  structure du guide (sensibiliser & former, connaître le SI, authentifier & contrôler les
  accès, sécuriser les postes/le réseau/l'administration, gérer le nomadisme, maintenir à jour,
  superviser/auditer/réagir, pour aller plus loin). Pour chaque mesure : intitulé officiel,
  reformulation en question simple pour un dirigeant non technique, niveau (`standard` /
  `renforce`), effort estimé et impact estimé (`low`/`medium`/`high`).
  Intitulés officiels et structure fidèles à ma connaissance du guide ANSSI ; niveau/effort/impact
  sont un jugement produit assumé (voir pondération plus bas), **à faire valider par un expert
  métier avant mise en production réelle** — ce n'est pas une donnée réglementaire, c'est une
  classification interne au produit.

**App `assessments`**
- Modèles : `Referential` / `Domain` / `Measure` (catalogue partagé, non tenant-scopé — chargé une
  fois via une commande, lu seul par l'API) ; `Assessment` / `Answer` (`TenantScopedModel`,
  comme `Membership` en Phase 1).
- Commande `manage.py load_anssi_referential` : charge/`update_or_create` idempotent depuis le
  JSON, `--file` pour pointer un fichier alternatif (utile en test).
- Moteur de scoring (`assessments/services.py`) : score pondéré par mesure — poids 1.0 pour une
  mesure `standard`, 0.5 pour une mesure `renforce` (désirable mais non bloquante pour un score de
  maturité visant des TPE/PME) — valeur oui=1/partiel=0.5/non=0, N/A et mesures non répondues
  exclues du dénominateur (jamais un score de 0 trompeur : `None` si rien n'est calculable — cas
  « tout N/A » et « évaluation vide » couverts explicitement par les tests). Score global et par
  domaine ; `compute_scores` accepte un jeu de réponses hypothétique (`measure_values`), c'est le
  point d'extension utilisé par le plan d'action pour le score projeté.
- Cycle de vie : `start_or_resume_assessment` (une seule évaluation « en cours » par tenant à la
  fois), sauvegarde de progression par upsert (`submit_answer`), `complete_assessment` exige que
  **toutes** les mesures aient une réponse (y compris N/A) avant de clôturer, et fige alors
  `score_global` (snapshot immuable — l'historique ne doit pas bouger si le référentiel évolue
  plus tard). Historique = simplement la liste des évaluations du tenant, triée par date.

**App `actions`**
- Modèle `ActionItem` (`TenantScopedModel`) référence `assessments.Assessment`/`Measure` par
  chaîne (`"assessments.Assessment"`) plutôt que par import direct — la relation FK est un besoin
  de schéma, la référence différée de Django est l'outil prévu pour ça sans coupler ce module aux
  internes de l'app assessments (l'import direct de modèle reste interdit par CLAUDE.md).
- `generate_action_plan` : un item `à faire` par mesure en écart (non/partiel) à la complétion
  d'une évaluation — idempotent (`get_or_create`), déclenché par la vue de complétion
  (orchestration dans la vue, comme le veut CLAUDE.md, pas de dépendance de service
  assessments → actions).
- Priorité = ratio impact/effort (`{low:1, medium:2, high:3}` de chaque côté) — un écart à fort
  impact/faible effort (quick win) remonte en tête de liste, un écart à faible impact/fort effort
  redescend.
- Score projeté (`compute_projected_score`) : réponses réelles de l'évaluation, sauf les mesures
  dont l'action associée est `fait`, comptées à 100 % — recalculé à chaque changement de statut.
- Assignation validée contre l'appartenance au tenant (réutilise `tenants.services.get_membership`)
  plutôt que d'accepter n'importe quel utilisateur de la plateforme.

**API REST** (tout sous `/api/v1/`, tenant-scopé, permission `IsTenantMemberReadOnlyForReader`
ajoutée dans `apps.tenants.permissions` — nouvelle permission partagée, le rôle lecteur est
maintenant réellement lecture seule sur ces ressources, pas seulement sur la gestion des membres) :
- `assessments/referential/`, `start/`, `current/`, liste (historique), détail (avec progression
  et réponses, pour pré-remplir le questionnaire à la reprise), `answers/<measure_id>/` (PUT,
  upsert), `complete/`, `scores/`.
- `actions/` (liste kanban, filtrable par `assessment`/`status`), `actions/<id>/` (PATCH statut/
  assignation/note), `actions/projected-score/`.

**Frontend (React + Vite + Tailwind, Recharts pour le radar)**
- Pas d'écran d'authentification n'existait avant cette session (Phase 1 = squelette seul) :
  ajout du strict nécessaire pour dérouler le parcours de bout en bout — connexion, inscription,
  client API axios (intercepteurs JWT + refresh automatique avec rotation, en-tête `X-Tenant-Id`),
  contexte d'authentification, routes protégées.
- Page questionnaire (`/diagnostic`) : domaines/mesures du référentiel actif, reformulation en
  langage simple affichée, barre de progression globale et par domaine, réponse = sauvegarde
  automatique (PUT immédiat par mesure), bouton de complétion activé seulement à 100 %.
- Page résultats (`/resultats`, `/resultats/:id`) : score global, radar Recharts par domaine
  (un seul hue, pas de dégradé arc-en-ciel, tooltip, table de détail en complément accessible du
  graphique — conforme au guide interne de dataviz du projet), historique des scores.
- Page plan d'action (`/plan-action`) : kanban à 3 colonnes par boutons de changement de statut
  (alternative explicitement acceptée au drag & drop), assignation par menu déroulant (limité aux
  membres du tenant), score projeté affiché en tête et recalculé à chaque changement de statut.

**Tests (backend)**
- 90 tests au total (35 nouveaux pour cette session), 97 % de couverture sur `apps/`.
- Scoring : cas limites explicitement testés — tout N/A, évaluation vide, aucune mesure, pondération
  standard/renforcé, N/A exclu du dénominateur, override `measure_values` pour le score projeté.
- Cycle de vie : reprise d'évaluation, upsert de réponse, rejet hors référentiel, complétion
  incomplète, complétion à deux reprises, historique trié.
- Commande `load_anssi_referential` : structure attendue (10 domaines/42 mesures), idempotence,
  fichier manquant.
- Génération du plan : gaps uniquement, idempotence, absence de gap.
- Étanchéité tenant sur **toutes** les nouvelles ressources : évaluation d'un autre tenant (404),
  historique scopé, items du plan d'action d'un autre tenant (404 au PATCH), liste d'actions scopée.
- Rôle lecteur : lecture seule vérifiée sur le questionnaire et sur le plan d'action.

### Difficultés rencontrées et solutions
- **Mismatch de mot de passe dans les nouveaux tests API** : les fixtures `user_factory`
  utilisent par défaut `Str0ng!Passw0rd123` (root `conftest.py`, Phase 1), mes premiers tests
  d'API assessments/actions utilisaient un autre mot de passe par défaut dans leur propre
  helper `_login` → 401 partout. Corrigé en alignant le défaut sur celui de `user_factory`.
- **`update_or_create` sur un manager tenant-scopé fail-closed** : `Answer.objects` (scopé) aurait
  fait échouer la recherche préalable de `update_or_create` hors contexte de requête (`.none()` →
  toujours `DoesNotExist` → toujours une création, jamais une mise à jour). Résolu en faisant
  systématiquement passer `assessments/services.py` et `actions/services.py` par `all_objects` +
  filtre `tenant=` explicite plutôt que par le manager scopé ambient — plus verbeux mais correct
  indépendamment du contexte d'appel (documenté en tête de chaque module de services).
- **`npm audit` signale `react-router-dom` (CVE contournement CSRF en mode RSC)** : la plage
  vulnérable couvre jusqu'à la dernière version publiée (7.18.2), aucun correctif n'existe encore
  au-dessus ; la faille concerne le mode RSC/framework, que cette SPA purement client (`BrowserRouter`)
  n'utilise pas. Choix assumé de garder 7.18.2 plutôt que revenir à 7.11.0, à surveiller via
  Dependabot/CI (scan prévu, cadrage §10) jusqu'à publication d'un correctif dans la plage utilisée.
- **Pas d'écran de connexion existant** : le parcours « bout en bout » demandé est impossible à
  démontrer sans authentification fonctionnelle côté frontend. Ajout du strict nécessaire
  (connexion/inscription/contexte tenant) plutôt que le périmètre complet de gestion de compte,
  pour rester concentré sur M2/M3.

### Vérification de bout en bout
Suite automatisée (90 tests, 97 % de couverture) + parcours HTTP complet rejoué manuellement avec
`curl` en reproduisant exactement les appels du frontend (inscription → connexion → référentiel →
démarrage → 42 réponses → progression → complétion → scores → plan généré → changement de statut →
score projeté → liste des membres pour l'assignation) : chaque réponse JSON vérifiée conforme à ce
qu'attendent les composants React. Serveur de dev Vite démarré et testé (200 sur `/`) ; `npm run
build` et `ruff`/`pytest` verts.

### Reste à faire (sessions suivantes)
- Faire valider par un expert métier la classification niveau/effort/impact des 42 mesures
  (jugement produit assumé cette session, pas une donnée ANSSI officielle).
- Champ de désactivation « douce » sur `Membership` (identifié en session précédente, toujours
  pertinent maintenant que l'assignation d'actions dépend de l'appartenance active à un tenant).
- Fractionner le bundle frontend (Recharts fait dépasser 500 kB minifié) — budget de performance
  frontend (cadrage §8, Green IT) à traiter en Phase 5 (durcissement).
- Écrans de gestion de compte (mot de passe oublié, invitation de collaborateurs) — non couverts,
  hors périmètre M2/M3 de cette session.
- Phase 3 (surveillance + météo cyber) à démarrer selon le phasage du cadrage.

---

## 2026-08-04 — Alignement du référentiel ANSSI sur la source officielle

### Contexte
Vérification demandée du contenu de `backend/data/anssi_hygiene.json` face au texte réel du guide
ANSSI, avant toute utilisation du référentiel comme pièce de certification. Le constat est sévère :
**le JSON produit en Phase 2 avait été reconstitué de mémoire, pas depuis le document source**, et
comportait des écarts massifs (mesures inventées, mesures officielles omises, mauvais domaines,
mauvaise numérotation). Détail complet dans le nouveau rapport
`docs/verification_referentiel_anssi.md` — cette entrée en résume les grandes lignes.

### Réalisé

**Récupération de la source**
- Téléchargement du PDF officiel depuis `messervices.cyber.gouv.fr/documents-guides/
  guide_hygiene_informatique_anssi.pdf` (trouvé via recherche web, l'URL n'était pas connue à
  l'avance) — confirmé PDF valide (en-tête `%PDF-1.4`, 72 pages) et cohérent avec la page officielle
  `cyber.gouv.fr/publications/guide-dhygiene-informatique`. Sauvegardé dans
  `docs/sources/anssi_guide_hygiene_informatique.pdf` (4,8 Mo, suivi par Git).
- Métadonnées confirmées : version 2.0, septembre 2017 (première édition janvier 2013), Licence
  Ouverte/Open Licence (Etalab v1).
- `pypdf` (absent de l'environnement) installé pour extraire le texte page par page — `pdftoppm`/
  poppler, normalement utilisé par l'outil de lecture de PDF, n'était pas disponible non plus.

**Comparaison mesure par mesure**
- La source la plus fiable s'est révélée être l'annexe « Outil de suivi » du guide (pages 62-67) :
  un tableau récapitulatif propre des 42 mesures, numéro par numéro, domaine par domaine — utilisé
  comme référence canonique pour la numérotation et les intitulés exacts, recoupé avec le corps du
  texte de chaque mesure (une par page).
- Écarts trouvés (détail dans le rapport) : 9 mesures inventées (dont un domaine entier
  « Pour aller plus loin » quasi totalement fabriqué — 6 mesures inventées contre 2 mesures
  officielles réelles), plusieurs mesures officielles complètement absentes (notamment 4 des 8
  mesures du domaine « Sécuriser le réseau »), des mesures rattachées au mauvais domaine (le
  référent SSI classé en « Pour aller plus loin » au lieu de « Superviser, auditer, réagir »), et
  des intitulés déformés (une mesure de chiffrement de mesure 31 confondue avec la mesure 18).
- Classification standard/renforcé entièrement refaite : la session précédente avait classé environ
  22 mesures « renforcé » par jugement produit non vérifié. Le texte réel montre que la plupart des
  mesures ont un socle standard *et* un complément renforcé optionnel (pas un choix binaire), et que
  seules **3 mesures (38, 41, 42)** sont présentées sans aucun socle standard. `official.level` du
  référentiel a été corrigé en conséquence ; la nuance « complément renforcé optionnel » pour les
  mesures qui en ont un n'est pas capturée par le modèle actuel (une seule question par mesure) —
  documenté comme simplification assumée plutôt que passé sous silence.

**Restructuration du schéma**
- Chaque mesure du JSON sépare maintenant trois couches : `official` (numéro, intitulé exact,
  domaine, niveau — reproduit du PDF), `simplified` (`question`, reformulation dirigeant — couche
  produit), `product_rating` (`effort`, `impact`, `disclaimer: true` — jugement produit explicitement
  marqué comme non issu de l'ANSSI).
- Bloc `meta` ajouté (source, URL officielle, URL du PDF, copie locale, version, date de
  publication, licence, date de vérification, référence du rapport).
- Modèle `Measure` : `code` (« H1 »…) remplacé par `number` (entier, unique, 1-42 — la numérotation
  officielle elle-même) ; ajout de `effort_impact_disclaimer` (booléen, remonté par l'API) pour que
  le caractère « jugement produit, pas donnée ANSSI » des estimations d'effort/impact reste visible
  jusqu'au frontend. Migration `assessments/0002_...` : le défaut à vide sur le nouveau champ unique
  ne fonctionne que sur une table `measure` vide — sans conséquence ici, aucune donnée réelle
  n'existe encore pour ce référentiel (les enregistrements de test de la session précédente ont été
  supprimés en réinitialisant la base de développement locale, `docker compose down -v`).
- `load_anssi_referential` mis à jour pour le nouveau schéma, avec une vérification supplémentaire :
  la commande rejette maintenant explicitement (au lieu de charger silencieusement) toute mesure
  dont `official.domain` ne correspond pas au domaine JSON dans lequel elle est imbriquée.

**Tests**
- Nouveau fichier `apps/assessments/tests/test_referential_integrity.py` (13 tests) : 42 mesures,
  numéros uniques et continus de 1 à 42, 10 domaines, présence des trois couches et de leurs champs
  obligatoires, cohérence domaine ↔ mesure, bloc `meta` complet (y compris l'existence effective du
  PDF référencé), et un test de non-régression verrouillant `{38, 41, 42}` comme seules mesures sans
  socle standard — plus une vérification miroir après chargement en base (détecte un bug du loader,
  pas seulement une erreur du JSON).
- Test ajouté sur `load_anssi_referential` pour le rejet en cas d'incohérence domaine/mesure.
- Tous les tests existants mis à jour (`code=` → `number=`, `order_by("code")` →
  `order_by("number")`) dans les fixtures partagées et les suites assessments/actions.
- 104 tests au total (13 nouveaux), 97 % de couverture. `ruff check`/`ruff format --check` verts,
  `makemigrations --check` vert, build et lint frontend verts (aucun changement frontend requis :
  les champs renommés n'étaient pas consommés côté React).

### Difficultés rencontrées et solutions
- **Outils de lecture de PDF absents** (`pdftoppm`/poppler-utils pour le rendu image, aucune
  bibliothèque Python d'extraction de texte) : `pypdf` installé à la volée ; suffisant pour de
  l'extraction de texte simple sur ce document (pas de mise en page complexe nécessitant l'OCR).
- **Repérer quelles mesures ont un palier « renforcé »** : le texte extrait ne contient le marqueur
  qu'une vingtaine de fois sur 42 mesures, avec un artefact d'extraction (« RENFOR cé » avec un
  espace parasite) qui a nécessité une recherche par préfixe plutôt qu'une correspondance exacte.
  La numérotation précise mesure-par-mesure a été confirmée en lisant le contenu de chaque page
  dans l'ordre plutôt qu'en se fiant à un comptage global.
- **Base de développement locale contenant déjà des données du référentiel incorrect** (créées lors
  des tests de bout en bout de la session Phase 2) : plutôt que d'écrire une migration complexe de
  préservation de données pour un contenu qu'on sait faux, la base locale a été réinitialisée
  (`docker compose down -v`). Choix documenté dans le commentaire de la migration : n'est sûr que
  tant qu'aucune donnée réelle n'existe pour ce référentiel.

### Vérification de bout en bout
Après rechargement du référentiel corrigé, `GET /api/v1/assessments/referential/` revérifié
manuellement : 10 domaines, 42 mesures, domaine « Pour aller plus loin » ramené à ses 2 mesures
officielles réelles (analyse de risques formelle ; produits/services qualifiés ANSSI).

### Reste à faire (sessions suivantes)
- Les éléments déjà listés en fin de session Phase 2 restent d'actualité (validation experte de
  `simplified`/`product_rating`, champ de désactivation `Membership`, code-splitting frontend,
  écrans de gestion de compte, Phase 3).
- La nuance « complément renforcé optionnel » pour les 19 mesures qui en ont un (au-delà des 3
  mesures 38/41/42 sans socle standard) n'est pas modélisée — actuellement documentée comme
  simplification assumée dans `docs/verification_referentiel_anssi.md`. À revisiter si le produit a
  un jour besoin de distinguer les deux paliers dans le score plutôt qu'un système de poids unique.

---

## 2026-08-05 — Phase 3 : surveillance continue et météo cyber

### Contexte
Mission Phase 3 du cadrage (§3.1 module M5, §4.4, règles de sécurité §4 point 4) : infrastructure
Celery/Beat, surveillance passive d'actifs (disponibilité, certificat SSL, en-têtes de sécurité,
SPF/DMARC), moteur d'alertes anti-faux-positifs, et météo cyber quotidienne par email. Consigne
explicite de cette session : la météo est un template déterministe (texte construit en code),
aucun appel à l'API Anthropic — l'enrichissement IA est réservé à la Phase 4 via le pipeline de
pseudonymisation déjà en place (ADR 004/005).

### Réalisé

**Infrastructure asynchrone**
- Celery 5.6 + Redis (base logique `/1`, séparée du cache Django sur `/0`) ; app Celery dans
  `config/celery.py`, planification statique (`beat_schedule`) plutôt que le scheduler DB de
  django-celery-beat — cohérent avec ADR 003 (pas de nouvel ADR nécessaire, décision déjà actée).
  Files dédiées `monitoring` et `emails` via `CELERY_TASK_ROUTES`, `ACKS_LATE` + prefetch=1 pour
  la fiabilité des tâches longues (checks réseau).
- Services `worker` et `beat` ajoutés à `docker-compose.yml`, chacun avec son healthcheck
  (`celery inspect ping` pour le worker, fraîcheur du fichier de planification pour beat) et un
  endpoint `GET /healthz/worker` côté Django basé sur un heartbeat en cache Redis.
- Toutes les tâches sont idempotentes et retryables : `run_single_check` ne relance que sur
  exception inattendue (les échecs réseau sont capturés *dans* les checks et jamais levés au
  niveau tâche), `send_weather_email`/`send_realtime_alert_email` s'appuient sur `EmailLog` pour
  ne jamais renvoyer deux fois le même email le même jour.

**App `monitoring`**
- Modèles `Asset` (type site web / domaine email, attestation de propriété obligatoire cochée à la
  création — refusée sinon), `CheckResult` (statut OK/WARNING/CRITICAL mappé 1:1 sur ☀️/⚠️/🔴,
  détails JSON, latence), `Alert` (type, sévérité, ouverte/résolue, contrainte unique partielle en
  base empêchant deux alertes ouvertes du même type sur le même actif).
- Quatre checks passifs, chacun dans son propre module testable sous `checks/` : disponibilité HTTP
  (GET + timeout), certificat SSL (validité, émetteur, échéance), en-têtes de sécurité (HSTS, CSP,
  X-Frame-Options, X-Content-Type-Options, avec recommandation française par en-tête manquant),
  SPF/DMARC (lecture DNS TXT via `dnspython`, DKIM explicitement hors périmètre).
- **Protection SSRF systématique** (`checks/ssrf.py`, `checks/http_client.py`) : toute résolution
  DNS est validée contre les plages privées/loopback/link-local/réservées/multicast avant tout
  appel réseau, y compris à **chaque saut de redirection HTTP** (redirections suivies manuellement,
  jamais via `allow_redirects=True`, pour pouvoir revalider l'IP cible à chaque étape).
- Moteur d'alertes : confirmation DOWN après 3 échecs consécutifs (anti faux positifs, cadrage
  §pièges connus), seuils d'expiration SSL à 30/14/7 jours avec suivi des seuils déjà notifiés
  (pas de spam de notification), résolution automatique au retour au vert, pas de doublon d'alerte
  ouverte (garanti au niveau base, pas seulement applicatif).
- API : CRUD des actifs, historique des checks, tableau de bord agrégé (dernier statut par type de
  check, disponibilité 24h, alertes ouvertes), liste des alertes ouvertes du tenant.

**App `notifications`**
- Préférences par tenant (heure d'envoi de la météo, activation temps réel des alertes), journal
  d'envoi (`EmailLog`) servant de clé d'idempotence quotidienne.
- Backend email configurable par variable d'environnement (console en développement, SMTP en
  production), templates texte + HTML légers, sans ressource externe, lisibles en 20 secondes,
  avec lien vers le tableau de bord.
- Agrégation météo : mood global (☀️/⚠️/🔴) calculé à partir du pire statut de check et de la
  sévérité des alertes ouvertes du tenant, envoyée à l'heure choisie (bucket de 15 minutes,
  correspondant à la fréquence de la tâche planifiée) aux administrateurs du tenant uniquement.

**Frontend**
- Page Surveillance (`/surveillance`) : formulaire de déclaration d'actif avec case d'attestation
  de propriété obligatoire (soumission désactivée tant qu'elle n'est pas cochée), cartes par actif
  avec badges de statut colorés, historique de disponibilité (points colorés), alertes ouvertes en
  français, actions suspendre/réactiver/supprimer.
- Page Préférences (`/preferences`) : bascule météo + sélecteur d'heure, bascule alertes temps réel.

**Tests et vérification**
- 212 tests (108 nouveaux pour `monitoring`/`notifications`), 97 % de couverture globale. Tests
  réseau entièrement mockés ; tests SSRF explicites et hors ligne (IP littérales privées/loopback/
  link-local refusées, y compris via redirection) ; moteur de confirmation à 3 échecs ; agrégation
  météo ; étanchéité multi-tenant sur chaque nouvelle ressource (`Asset`, `CheckResult`, `Alert`,
  `NotificationPreferences`). `ruff check`/`ruff format --check` verts, `makemigrations --check`
  vert, lint et build frontend verts.
- Vérification de bout en bout en conditions réelles (hors CI, réseau réel) : trois actifs créés
  via l'API (`http://10.0.0.5/` comme cible SSRF, `https://example.com` comme site réel,
  `example.com` comme domaine email réel), les 4 checks exécutés directement via
  `apps.monitoring.services.run_check()`. Résultats : cible SSRF refusée avant tout appel réseau
  (`requests.get` jamais invoqué, check enregistré CRITICAL avec message de refus explicite) ;
  `example.com` : 200 OK, certificat réel (émetteur « SSL Corporation », ~83 jours de validité),
  4 en-têtes de sécurité manquants détectés, SPF (`v=spf1 -all`) et DMARC (`v=DMARC1;p=reject...`)
  lus et parsés correctement. Moteur d'alertes vérifié en direct : alerte `security_headers`
  ouverte correctement, alerte `down` correctement **retenue** après un seul résultat CRITICAL
  (règle des 3 échecs consécutifs fonctionnant comme prévu).
- Stack complète (`web`, `worker`, `beat`, `postgres`, `redis`) démarrée via `docker compose up`,
  les 5 services confirmés `healthy`. Email météo renvoyé avec succès à l'intérieur du conteneur
  Linux (voir difficultés ci-dessous pour le contexte de cette vérification ciblée), confirmant
  l'absence de régression liée à l'encodage.

### Difficultés rencontrées et solutions
- **`UnicodeEncodeError` sur l'emoji 🔴 lors d'un test manuel de l'email météo via
  `manage.py shell` en local (hors Docker)** : le backend email console de Django écrit sur
  `sys.stdout`, encodé en cp1252 dans ce terminal Windows, qui ne sait pas rendre l'emoji. Diagnostic :
  limitation locale du terminal Windows, pas un bug applicatif — le backend SMTP (utilisé en
  production) n'écrit jamais sur un terminal, et Linux (environnement Docker/VPS de production) est
  par défaut en UTF-8. Décision : ne pas modifier `settings.py` pour ce problème d'ergonomie de
  développement ponctuel ; vérifié explicitement que l'envoi fonctionne sans erreur à l'intérieur du
  conteneur `web` (Linux) — confirmé, documenté ici comme limitation observée plutôt que corrigée.
- **Test de confirmation santé Docker interrompu par un `sleep` chaîné bloqué par l'outillage** :
  contourné avec une boucle d'attente conditionnelle (`until ... ; do sleep 3; done`) plutôt qu'un
  délai fixe — les 5 services sont passés à `healthy` en environ 3 minutes (le temps que
  `beat`/`worker` complètent leur première itération de healthcheck).
- **Volume Postgres local contenant les données du smoke-test manuel** (tenant, actifs, résultats de
  check créés pendant la vérification) : réinitialisé (`docker compose down -v`) après vérification,
  suivant le même principe que la session précédente — aucune donnée réelle n'existe encore pour ce
  module, la réinitialisation est sans risque.

### Reste à faire (sessions suivantes)
- Les éléments déjà listés en fin de session précédente restent d'actualité (validation experte du
  référentiel simplifié, champ de désactivation `Membership`, code-splitting frontend — le bundle
  dépasse toujours 500 kB minifié, écrans de gestion de compte).
- Phase 4 (IA documentaire + assistant) : enrichissement de la météo cyber par l'IA (formulations
  plus riches, recommandations priorisées) via le pipeline de pseudonymisation existant — non traité
  cette session par consigne explicite.
- La nuance entre « pas encore de donnée » et « check en erreur » n'est pas distinguée dans les
  badges du tableau de bord frontend (`StatusBadge` affiche simplement « — » dans les deux cas) —
  suffisant pour cette phase, à revisiter si l'ambiguïté gêne l'usage réel.

---

## 2026-08-05 — Phase 4 : IA documentaire et assistant contextuel

### Contexte
Session consacrée au module différenciant du produit (cadrage §3.1 M4) : pipeline IA centralisé
avec pseudonymisation systématique (CLAUDE.md règle d'architecture n°3, ADR-004/005), génération de
la charte informatique (US-4.1), assistant contextuel (US-4.2), transparence et contrôle utilisateur
(US-4.3), et intégration optionnelle à la météo cyber (cas d'usage 3, laissé de côté en Phase 3).
La rigueur privacy passait avant tout, conformément à la consigne de mission.

### Réalisé

**Nouvelle app `ai_assistant` — pipeline central**
- `services.py` : point d'entrée unique vers l'API Anthropic (aucun autre module n'importe le SDK).
  Pipeline en cinq étapes pour chaque cas d'usage : construction du contexte minimal (jamais de PII
  brute — secteur, effectif, scores agrégés) → pseudonymisation (placeholders stables `{{COMPANY}}`,
  `{{MEMBER_n}}`, `{{EMAIL_n}}`, `{{DOMAIN_n}}`, `{{URL_n}}`, table de correspondance chiffrée Fernet,
  TTL glissant) → appel `call_claude()` (seul point d'appel SDK du projet) → ré-injection des valeurs
  réelles dans la réponse → journalisation (`AIUsageLog` : tenant, cas d'usage, modèle, tokens,
  coût estimé, durée).
- Routage modèle (ADR-004, précisé pour l'assistant — nouveau cas d'usage, décision documentée dans
  le code du point d'entrée comme demandé par l'ADR) : `claude-sonnet-5` pour la génération
  documentaire longue (charte), `claude-haiku-4-5` pour l'assistant (réponses courtes ancrées sur un
  contexte déjà calculé) et la météo enrichie — cohérent avec la sobriété Green IT du cadrage §8.
- Quotas mensuels (`AIUsageQuota`, un enregistrement par tenant et par mois, limite configurable via
  `AI_DEFAULT_MONTHLY_TOKEN_LIMIT`) vérifiés avant tout déclenchement de job, consommation
  incrémentée après chaque appel réel (pas une simple estimation a priori).
- `ai_enabled` (nouveau champ sur `Tenant`) : coupe-circuit vérifié par la permission DRF
  `IsAIEnabled` sur tous les endpoints IA sauf le réglage lui-même (qui doit rester joignable pour
  réactiver) ; réglable par un administrateur d'entreprise uniquement.
- Prompts système versionnés en français (`prompts.py`, suffixe `_V1`), un par cas d'usage, avec
  consigne explicite pour l'assistant de recommander un professionnel (juridique, réponse à
  incident) pour ce qui dépasse le périmètre de l'outil.

**Pattern job asynchrone (US US-4.1/4.2, CLAUDE.md règle n°3)** — voir ADR-011 pour le détail des
options écartées : `POST` crée immédiatement la ressource (`GeneratedDocument` ou `Message`
utilisateur) et un `AIJob` (statut `pending`), déclenche la tâche Celery correspondante sur la
**nouvelle file `ai`**, répond `202`. `GET /api/v1/ai/jobs/{id}/` permet au frontend de sonder le
statut. Aucun appel IA ne s'exécute dans le cycle requête/réponse HTTP. La météo enrichie (cas
d'usage 3) déroge délibérément à ce pattern — appel direct synchrone dans la tâche Celery existante
`send_weather_email_for_tenant` (file `emails`), toujours via `ai_assistant/services.py` mais sans
job dédié : arbitrage documenté dans l'ADR-011, dicté par l'exigence « la météo part toujours ».

**Cas d'usage 1 — Charte informatique (US-4.1)**
- `GeneratedDocument` (type, statut `generating`/`draft`/`validated`/`failed`, contenu markdown,
  version incrémentée à chaque régénération). Parcours complet : génération → relecture/édition
  (`PATCH`, bloqué une fois validé) → validation (`POST .../validate/`) → export markdown
  (`GET .../export/`, téléchargement `.md`). **Export PDF non traité cette session** (voir reste à
  faire) — le markdown suffit pour ce jalon.

**Cas d'usage 2 — Assistant contextuel (US-4.2)**
- `Conversation` / `Message` (rôles `user`/`assistant`), fenêtre d'historique transmise à l'API
  limitée à 20 messages. Contexte (scores, écarts principaux, alertes ouvertes) pseudonymisé et
  injecté dans le prompt système à chaque tour plutôt qu'en tours de conversation factices — plus
  simple et évite toute ambiguïté sur ce qui est « conversation réelle ». Streaming non implémenté
  (explicitement non requis par le cadrage pour cette phase).

**Transparence et contrôle (US-4.3)**
- `GET /api/v1/ai/preview/charter/` et `/preview/assistant/` : renvoient exactement le contexte
  pseudonymisé qui serait transmis, sans appel API ni persistance de table de correspondance —
  vérifié manuellement en conditions réelles (voir Tests ci-dessous).
- `GET/PATCH /api/v1/ai/settings/` : état `ai_enabled` + quota courant visible.

**Météo enrichie (cas d'usage 3)**
- `NotificationPreferences.weather_enrichment_enabled` (nouveau champ, défaut `false`). Si activé :
  `apps.notifications.services._maybe_enrich_weather_summary` appelle
  `ai_assistant.services.enrich_weather_summary`, qui capture **toute** exception (IA désactivée,
  quota dépassé, erreur réseau/API) et renvoie `None` — le template déterministe de la Phase 3 reste
  alors le contenu envoyé. Templates email (texte + HTML) mis à jour pour afficher le résumé enrichi
  s'il existe.

**Frontend**
- Page Documents (`/documents`) : bandeau réglages IA (activer/désactiver, quota), encart de
  prévisualisation, génération, liste de documents, éditeur (édition/validation/export).
- Page Assistant (`/assistant`) : encart de prévisualisation, fil de conversation, saisie, sondage
  du job pendant la réflexion de l'assistant.
- Sondage de job factorisé (`usePolling`, intervalle 2 s, arrêt sur statut terminal) — dupliqué à
  l'identique entre les deux pages plutôt que d'introduire un module partagé pour deux usages très
  proches mais non identiques (pas d'over-engineering pour ce volume de code).
- Case à cocher « météo enrichie » ajoutée à la page Préférences.
- Export : blob téléchargé via `apiClient` (pas un lien `<a href>` brut) car l'endpoint exige le
  JWT porté par l'intercepteur axios.

**Infrastructure**
- `docker-compose.yml` : le worker consomme désormais aussi la file `ai`.
- `requirements.txt` : `anthropic==0.120.2`, `cryptography==50.0.0`.
- Variables d'environnement (`.env.example`) : `ANTHROPIC_API_KEY`, `AI_PSEUDONYMIZATION_KEY`,
  `AI_PSEUDONYMIZATION_TTL_HOURS`, `AI_DEFAULT_MONTHLY_TOKEN_LIMIT`.

**Documentation**
- ADR-011 (nouveau) : pattern job asynchrone, options écartées (blocage HTTP, WebSocket/SSE),
  arbitrage météo enrichie.
- ADR-005 complété : schéma des placeholders, stabilité par conversation, chiffrement Fernet,
  emplacement du test de propriété — sans remettre en cause la décision d'origine.

### Tests et vérification
- 288 tests backend (72 nouveaux pour `ai_assistant`, dont 2 tests de régression ajoutés après le
  correctif décrit ci-dessous, +4 pour `notifications`), 95 % de couverture sur
  `ai_assistant`/`notifications` (`tasks.py` moins couvert — chemins
  d'épuisement des tentatives Celery non testés unitairement, cohérent avec la profondeur de test
  déjà acceptée pour `apps.monitoring.tasks`, compensé par la vérification en conditions réelles
  ci-dessous). SDK Anthropic entièrement mocké dans les tests unitaires/API. `ruff check`/
  `ruff format --check` et `makemigrations --check` verts ; build et lint frontend verts.
- **Test de propriété de non-fuite** (ADR-005) : `test_pseudonymization.py`, quatre scénarios de
  raison sociale/noms/emails avec caractères spéciaux (accents, apostrophes, parenthèses, `. * + [ ]`),
  pour les trois cas d'usage — construit le payload exact envoyé au SDK mocké et vérifie l'absence de
  toute valeur réelle.
- Étanchéité multi-tenant vérifiée sur chaque nouvelle ressource (`GeneratedDocument`, `Conversation`,
  `Message`, `AIJob`) ; `ai_enabled=false` → 403 sur tous les endpoints IA sauf le réglage lui-même ;
  quota dépassé → refus propre (`429`) sans effet de bord ; fallback météo vérifié explicitement
  (désactivé, IA désactivée, quota dépassé, erreur API → `None`, email envoyé quand même).
- **Vérification de bout en bout en conditions réelles** (hors CI, stack complète : Postgres, Redis,
  `runserver`, worker Celery sur la file `ai`) : inscription + création de tenant réelles, appel des
  endpoints de prévisualisation — la réponse HTTP réelle contient bien `{{COMPANY}}` à la place de la
  raison sociale, confirmant la pseudonymisation en dehors du cadre mocké des tests. Génération de
  document déclenchée via l'API réelle sans `ANTHROPIC_API_KEY`/`AI_PSEUDONYMIZATION_KEY` configurées
  (aucune clé réelle disponible dans cet environnement) : le job progresse correctement `pending` →
  `running`, retente sur échec, puis atteint un statut terminal — ce test a mis en évidence un bug
  réel (voir ci-dessous), corrigé et re-vérifié avec succès après correction.

### Difficultés rencontrées et solutions
- **Bug réel découvert par le test en conditions réelles, absent des tests unitaires/mockés** : le
  garde-fou d'idempotence des tâches Celery (`generate_document_task` / `generate_assistant_reply_task`)
  rejetait tout job dont le statut n'était pas `pending`. Or la première tentative appelle
  `mark_job_running` (statut → `running`) *avant* l'échec qui déclenche la nouvelle tentative Celery ;
  la tentative suivante voyait donc un statut `running`, était traitée comme « déjà géré » par le
  garde-fou, et s'arrêtait silencieusement sans jamais appeler `mark_job_failed` — le job restait
  bloqué indéfiniment en `running`, un job zombie invisible pour l'utilisateur (le frontend aurait
  sondé sans fin). Racine : le garde-fou visait à empêcher un double traitement d'un job déjà
  *terminé* (`done`/`failed`), mais excluait à tort `running`, qui est précisément l'état normal
  d'une tentative retentée. Corrigé (`job.status in (DONE, FAILED)` au lieu de
  `job.status != PENDING`) ; deux tests de régression ajoutés (statut `running` simulé manuellement,
  job correctement repris jusqu'à un statut terminal) ; re-vérifié en conditions réelles après
  correction — le job atteint désormais `failed` avec `error_message` renseigné et `finished_at`
  horodaté, comme attendu. Ce bug n'aurait pas été détecté par la suite pytest seule (qui appelle
  chaque tâche une seule fois, sans simuler l'état intermédiaire d'une vraie redélivraison Celery) —
  confirme l'intérêt de la vérification en conditions réelles au-delà des tests mockés pour ce type
  de logique d'orchestration asynchrone.
- **Choix de routage modèle pour l'assistant conversationnel** : ni CLAUDE.md ni le cadrage ne
  tranchent explicitement Haiku/Sonnet pour ce cas d'usage (introduit en Phase 4) ; ADR-004 anticipe
  ce point (« décision de routage ... à documenter dans le code du point d'entrée »). Arbitrage :
  Haiku par défaut, conforme à la sobriété Green IT et à la nature des réponses (synthèses courtes
  ancrées sur un contexte déjà calculé côté serveur, pas de génération longue), documenté dans
  `services.py` et l'ADR-005 complété — révisable si la qualité perçue en usage réel le justifie.
- **Numérotation des ADR** : seuls les ADR 001 à 005 existent en fichiers complets (006 à 010 restent
  résumés uniquement dans le tableau du cadrage §5, jamais rédigés en version longue). L'ADR créé
  cette session porte le numéro 011 conformément à la consigne de mission, créant un écart de
  numérotation (006-010 absents du dossier `docs/adr/`) — signalé ici plutôt que « corrigé »
  silencieusement en renumérotant.

### Reste à faire (sessions suivantes)
- Export PDF de la charte informatique (actuellement markdown uniquement — noté comme reste à faire
  dans la mission elle-même).
- Vérification de bout en bout du chemin de succès complet (appel réel à l'API Anthropic) : non
  réalisable dans cet environnement sans clé API réelle ; à faire en préproduction avant mise en
  production, avec un budget de tokens de test limité (Green IT).
- Éléments déjà listés en fin de session précédente toujours d'actualité (validation experte du
  référentiel simplifié, champ de désactivation `Membership`, code-splitting frontend, écrans de
  gestion de compte).
- Rédaction en version complète des ADR 006 à 010 (actuellement seulement résumés dans le tableau du
  cadrage) — pas traité cette session, hors périmètre de la mission Phase 4.

## 2026-08-05 — Phase 5 : durcissement sécurité, qualité et accessibilité

### Contexte
Mission Phase 5 (cadrage §6, §9, phase 5 du §11) : consolidation pure, aucune nouvelle
fonctionnalité produit. Dix chantiers demandés : revue OWASP Top 10 documentée, rate limiting,
2FA TOTP (US-1.3), durcissement de l'authentification (verrouillage progressif, politique de mot
de passe, messages non énumérants), en-têtes/configuration de production (Caddy, settings Django
séparés), chaîne d'approvisionnement (pip-audit/npm audit/Trivy en CI), tests end-to-end
Playwright sur les 3 parcours critiques, accessibilité RGAA de base avec axe-core, export PDF de
la charte (reste-à-faire de Phase 4), et rédaction complète des ADR 006 à 010 (dette documentaire
identifiée en fin de Phase 4).

### Réalisé

**Authentification et rate limiting**
- 2FA TOTP complète (`apps/accounts/services.py`, `apps/accounts/models.py`) : enrôlement par QR
  code (`pyotp`+`qrcode`), secret chiffré au repos avec une clé Fernet dédiée
  (`TOTP_ENCRYPTION_KEY`, distincte de `AI_PSEUDONYMIZATION_KEY` — une compromission de l'une ne
  compromet pas l'autre), codes de récupération à usage unique hashés, vérification au login via
  un jeton de challenge opaque (`secrets.token_urlsafe`, TTL 5 minutes, usage unique — jamais un
  JWT), désactivation nécessitant confirmation du mot de passe. Frontend :
  `TwoFactorSettingsPage.jsx` (enrôlement/désactivation), `LoginPage.jsx` réécrit en flux à deux
  étapes.
- Verrouillage progressif par compte **et** IP (`_LOCKOUT_LADDER`, Redis via le cache Django, clés
  hashées SHA-256 — email/IP jamais en clair dans Redis), messages d'erreur non énumérants
  (identiques pour mot de passe incorrect et email inconnu, message générique à l'inscription en
  doublon).
- Throttling DRF : `AuthRateThrottle` (10/min par IP, register/login/refresh),
  `TenantRateThrottle` (300/min par tenant, API générale), `TenantAIRateThrottle` (20/min,
  endpoints IA — alignée sur les quotas). Réponses 429 propres, testées.
- Politique de mot de passe : longueur ≥ 12 (privilégiée à la complexité imposée, cadrage §6) +
  `CommonPasswordValidator` (liste de mots de passe compromis courants) +
  `NumericPasswordValidator`.

**Infrastructure de production**
- `backend/config/settings_production.py` (nouveau) : overlay séparé de `settings.py`
  (`DEBUG=False`, `ALLOWED_HOSTS` sans défaut permissif, cookies sécurisés, HSTS, en-têtes
  restants gérés côté Caddy).
- `deploy/Caddyfile` : reverse proxy avec TLS automatique (Let's Encrypt), HSTS,
  `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, CSP, `Permissions-Policy`.
- `deploy/Dockerfile.caddy` (build multi-étage : `node:22-alpine` pour le frontend puis
  `caddy:2-alpine` final — l'image de production ne contient jamais les sources/`node_modules`),
  `docker-compose.prod.yml` (postgres/redis sans port hôte exposé, service `caddy` ajouté).
- `.dockerignore` (racine et `backend/`).

**Chaîne d'approvisionnement (CI)**
- `pip-audit -r requirements.txt --strict` (job `backend`) : 0 vulnérabilité actuellement.
- `npm run audit` → `frontend/scripts/check-npm-audit.mjs`, liste blanche documentée pour
  `GHSA-qwww-vcr4-c8h2` (react-router, CWE-352 — chemin de code non utilisé par cette application,
  aucun correctif disponible autre qu'un downgrade cassant vers une version différemment
  vulnérable).
- Scan Trivy de l'image backend (job `container-scan`, `severity: HIGH,CRITICAL`,
  `ignore-unfixed: true`) : 0 vulnérabilité actuellement, vérifié localement avant intégration CI.

**Tests end-to-end Playwright**
- `frontend/e2e/` : 3 specs pour les parcours critiques (inscription→diagnostic complet→plan
  d'action ; déclaration d'actif→check simulé→alerte visible ; génération de charte IA (API
  mockée)→relecture→validation) contre la vraie stack `docker-compose`, plus un balayage
  d'accessibilité (`@axe-core/playwright`) sur les pages principales non couvertes par les 3
  parcours (Résultats à vide, Assistant, Préférences, Sécurité, pages publiques).
- Le check simulé du parcours (b) passe par une nouvelle commande de gestion Django
  (`simulate_check_failure`) qui réutilise le vrai moteur d'alerte
  (`apps.monitoring.services.simulate_check_result`, nouvelle fonction de service) plutôt que de
  contourner la logique métier.
- Job CI dédié (`e2e`) : monte la stack `docker-compose` complète (env générés à la volée, jamais
  committés), attend `/healthz`, exécute la suite Playwright, publie le rapport HTML en artefact.

**Accessibilité**
- Correction de deux violations `color-contrast` réelles détectées par axe-core (pas visibles à
  l'œil sans mesure) : badges de statut à texte blanc sur fond `-500` (ratio ~2.1-2.5:1, sous le
  seuil AA 4.5:1) remontés en `-600`/`-700` dans `DocumentsPage.jsx` et `SurveillancePage.jsx` ;
  texte secondaire `text-slate-400` (ratio ~2.56:1 sur blanc) remonté en `text-slate-500` sur 6
  pages ; badges `ActionPlanPage.jsx` sur fond `slate-100` remontés de `slate-500` (4.34:1, sous le
  seuil) à `slate-600`.
- Une violation `label` critique corrigée : le `<textarea>` de relecture de document
  (`DocumentsPage.jsx`) et le champ de saisie de l'assistant (`AssistantPage.jsx`) n'avaient pas de
  nom accessible — `aria-label` ajouté aux deux.
- Vérification : tous les `onClick` de l'application sont portés par de vrais éléments `<button>`
  (aucun pattern `<div onClick>` trouvé) — navigation clavier native garantie sans JavaScript
  supplémentaire.

**Export PDF de la charte (US-4.1, reste-à-faire de Phase 4)**
- `render_document_pdf()` (`apps/ai_assistant/services.py`) : markdown validé → HTML minimal
  (`markdown` avec extensions `extra`/`sane_lists`) → PDF via WeasyPrint, feuille de style dédiée.
  Endpoint `GET /api/v1/ai/documents/<id>/export/pdf/`, mêmes permissions/quota que le reste du
  module. ADR-012 (nouveau) documente la décision et son alternative écartée (service tiers de
  conversion).
- Dépendance système (Pango/Cairo/GDK-Pixbuf) ajoutée à `backend/Dockerfile` et à
  `.github/workflows/ci.yml` — absente de `python:3.12-slim`, ne peut pas être testée sur un poste
  Windows nu (voir Difficultés).

**Revue de sécurité et documentation**
- `docs/security_review.md` (nouveau) : revue complète des 10 catégories OWASP Top 10 (2021), avec
  référence de fichier pour chaque mesure en place, ce qui a été ajouté cette session, et les
  risques résiduels sciemment acceptés.
- ADR 006 à 012 rédigés en version complète (`docs/adr/`) : 006 (PostgreSQL seul, pgvector V2),
  007 (Docker Compose + Caddy), 008 (pipeline GitHub Actions), 009 (JWT/RBAC/2FA), 010
  (vérifications passives sur actifs déclarés), 012 (export PDF WeasyPrint) — comblant la dette
  documentaire identifiée en fin de Phase 4 (seuls 001-005 et 011 existaient).
- README mis à jour : état du projet (Phase 5), structure du dépôt complète (toutes les apps),
  instructions Celery/référentiel ANSSI, section Tests étendue (audits, E2E), nouvelle section
  Sécurité résumant les mesures en place avec liens vers `security_review.md` et les ADR.

### Tests et vérification
- Suite backend complète : 323 tests passent (4 désélectionnés localement — export PDF, qui
  nécessite les bibliothèques système WeasyPrint absentes de Windows ; vérifiés séparément dans le
  conteneur Docker : 2/2 passent). `ruff check`/`ruff format --check` verts.
- `pip-audit`, `npm run audit`, scan Trivy de l'image backend : exécutés localement pendant cette
  session, tous verts (0 vulnérabilité HIGH/CRITICAL non acceptée).
- Suite Playwright complète (5 specs, `frontend/e2e/`) : verte contre la stack `docker-compose`
  réelle après correction du bug CORS (voir Difficultés) et des deux violations d'accessibilité.
- `npm run lint` et `npm run build` (frontend) verts.

### Difficultés rencontrées et solutions
- **Bug CORS réel découvert par les tests E2E, invisible aux tests unitaires Django** : l'en-tête
  personnalisé `X-Tenant-Id` (envoyé par `frontend/src/api/client.js` sur toute requête
  tenant-scopée) n'était pas dans la liste blanche `CORS_ALLOW_HEADERS` de `django-cors-headers`.
  Conséquence : le navigateur bloquait silencieusement côté client toute requête tenant-scopée dès
  qu'un tenant était résolu (aucune trace côté serveur, la requête ne quittait jamais le
  navigateur) — seules les routes ne nécessitant pas cet en-tête (register/login/me) continuaient
  de fonctionner. Le client de test Django n'applique jamais les règles CORS d'un vrai navigateur,
  donc ce bug ne pouvait être détecté que par un test s'exécutant dans un vrai Chromium — exactement
  ce que ce chantier E2E a permis. Corrigé (`CORS_ALLOW_HEADERS = [*default_headers,
  "x-tenant-id"]`, `backend/config/settings.py`) avec un test de non-régression dédié.
- **Gap de journalisation identifié par la revue OWASP (A09) et corrigé dans la foulée** : aucun
  `LOGGING` Django explicite n'existait (config par défaut, sortie console non structurée, aucun
  logger de sécurité actif) — la mission demande explicitement de corriger ce que la revue révèle,
  pas seulement de le documenter. Ajout d'un `LOGGING` dict minimal (console uniquement, pas de
  service tiers — cohérent avec la sobriété du projet et l'interdiction CLAUDE.md d'envoyer des
  données personnelles à un service externe) activant les loggers `django.security` et
  `django.request`, et un événement explicite journalisé à chaque déclenchement de verrouillage
  progressif (identifiant haché uniquement, jamais l'email/IP en clair — même règle que les clés de
  cache Redis).
- **Clé API Anthropic trouvée en clair dans `backend/.env.example`** (modification locale non
  committée, découverte en éditant ce fichier pour y ajouter `TOTP_ENCRYPTION_KEY`) : retirée
  immédiatement et remplacée par un placeholder vide avant tout commit ; vérifié via `git
  diff`/`git show` qu'aucune fuite n'avait eu lieu côté dépôt. Développeur alerté pour rotation de
  la clé côté fournisseur par précaution, l'origine exacte de cette valeur en clair localement
  restant inconnue. Documenté dans `docs/security_review.md` (A02) comme point de vigilance
  opérationnel plutôt que comme faille de conception.
- **Bug Docker découvert lors de la vérification de l'export PDF** : `libgdk-pixbuf2.0-0` (nom de
  paquet utilisé initialement dans `backend/Dockerfile`) n'existe plus sous ce nom — Debian
  "trixie" (base actuelle de `python:3.12-slim`) l'a renommé `libgdk-pixbuf-2.0-0` (tiret
  supplémentaire). Diagnostiqué via `apt-cache search` dans un conteneur `python:3.12-slim` propre,
  corrigé, rebuild vérifié.
- **Piège DRF sur le throttling en tests** : `SimpleRateThrottle.THROTTLE_RATES` est un attribut de
  classe capturé une fois à l'import depuis `api_settings.DEFAULT_THROTTLE_RATES` — les surcharges
  via le fixture `settings` de pytest-django ne s'y répercutent pas (le signal `setting_changed` ne
  fait que vider le cache de `api_settings`, sans réassigner l'attribut déjà lié). Résolu par un
  fixture dédié mutant directement le dict partagé en place, avec restauration en teardown.

### Reste à faire (sessions suivantes)
- Journalisation de production : le `LOGGING` dict ajouté cette session reste minimal (console
  uniquement) ; `docs/security_review.md` (A09) recommande, pour la Phase 6, une destination
  persistante pour les échecs d'authentification répétés et les erreurs serveur 5xx, et l'évaluation
  d'un outil de suivi d'erreurs (en respectant l'interdiction d'y envoyer des données personnelles).
- Déploiement effectif sur `rssiasservice.online` (Phase 6) : la stack de production
  (`docker-compose.prod.yml`, Caddy, settings durcis) est prête mais n'a pas encore été déployée
  sur le VPS cible ; runbook de déploiement et de sauvegarde restant à rédiger.
- Politique de 2FA imposée au niveau tenant (actuellement optionnelle par utilisateur) — hors
  périmètre de l'US-1.3 telle que cadrée, notée dans ADR-009 comme évolution possible.
- Rotation automatisée des clés Fernet (`AI_PSEUDONYMIZATION_KEY`, `TOTP_ENCRYPTION_KEY`) —
  actuellement manuelle, acceptable au volume actuel de secrets stockés (voir
  `docs/security_review.md`, A02).

## 2026-08-07 — Refonte complète de l'interface

### Contexte
Mission : transformer le prototype fonctionnel (Phases 1-5) en produit SaaS au niveau du marché
(référence de qualité perçue : Vanta, Drata, Linear), pour un public de dirigeants de PME non
techniques. Contrainte absolue : aucune régression fonctionnelle — tous les tests (unitaires,
e2e Playwright, axe-core) devaient rester verts à la fin. Aucune nouvelle fonctionnalité produit
hors dashboard (composé à partir des endpoints existants, sans ajout backend). Périmètre : système
de design, nouveau layout applicatif (sidebar), nouvelle page Tableau de bord, refonte de toutes
les pages existantes, états/micro-interactions, vérification visuelle réelle, mise à jour des
tests e2e, documentation.

### Réalisé

**Système de design (`frontend/src/index.css`, Tailwind v4 `@theme`)**
- **Palette** : une couleur de marque signature — bleu nuit profond (H215, désaturé) plutôt que le
  slate/blue par défaut de Tailwind — utilisée pour la sidebar, le panneau de marque des écrans
  d'authentification et les liens/focus. Une couleur d'accent chaleureuse (ambre/or, H36) réservée
  **exclusivement** au CTA principal de chaque écran et aux états actifs/sélectionnés — jamais pour
  de grandes surfaces, pour qu'elle garde sa valeur de signal. Une échelle neutre « ink » teintée de
  la même teinte que la marque plutôt que le gris Tailwind générique, pour que toute la palette
  se lise comme un système cohérent. Un fond d'application légèrement teinté (`--color-canvas`,
  `#f6f8fa`) plutôt que blanc/gris pur. Couleurs sémantiques ok/warning/critical avec deux variantes
  chacune (« -strong » pour badges à texte blanc, « -subtle » pour badges à fond clair/texte foncé),
  toutes deux vérifiées ≥ 4,5:1 par calcul (formule de luminance relative WCAG) avant intégration.
- **Typographie** : Inter (interface, poids 400/500/600/700) chargée via `@fontsource`, subsets
  latin/latin-ext uniquement (l'app est exclusivement en français — inutile de livrer les glyphes
  cyrilliques/grecs/vietnamiens, cohérent avec la sobriété Green IT). Fraunces (titrage, un serif
  moderne légèrement éditorial, poids 500 italique/600/700) pour tous les `<h1>`/titres de page et
  le nombre héros du score — c'est ce qui évite le rendu « template admin Tailwind » : un public non
  technique lit un titre en serif comme « posé », pas comme un outil froid.
- **Radii** (sm/md/lg/xl) et **deux niveaux d'ombre** seulement (`--shadow-soft` pour le repos,
  `--shadow-elevated` pour modales/popovers), teintées de la couleur de marque plutôt que noir pur.
- **Icônes** : `lucide-react`, un seul set cohérent dans toute l'application (aucun mélange
  d'emoji/icônes ad hoc).
- **Primitives** (`frontend/src/components/ui/`) : Button (primary/secondary/ghost/danger, état
  loading avec spinner), Card, Badge (variantes sémantiques + option `dot`), EmptyState,
  Skeleton/SkeletonText/SkeletonCard, Modal (gestion du focus, Echap, restauration du focus au
  ferme), Toast (provider global + `useToast()`, actions « Réessayer »), Tabs, Tooltip,
  SegmentedControl (non listé dans la mission mais nécessaire pour les réponses du diagnostic —
  `role="radiogroup"`/`role="radio"`, plus correct sémantiquement que les boutons plats de la
  version précédente). Toutes les pages consomment ces primitives — plus aucun style Tailwind ad hoc
  dupliqué pour bouton/carte/badge.

**Layout applicatif** (`AppLayout.jsx`, `Sidebar.jsx`, `Topbar.jsx`)
- Sidebar fixe fond marine sombre : wordmark, navigation à icônes (Tableau de bord, Diagnostic,
  Plan d'action, Surveillance, Documents, Assistant), bas de sidebar avec tenant courant
  (avatar-initiales), Préférences, Sécurité, Déconnexion.
- Responsive à trois états : desktop (lg+, sidebar complète), tablette (md-lg, rail à icônes
  seules), mobile (drawer en overlay déclenché par un bouton hamburger dans la topbar). Les trois
  variantes de sidebar (rail icône, rail complet, drawer) sont montées avec `hidden`/`lg:hidden`
  plutôt qu'un positionnement absolu — un élément `display:none` est retiré de l'arbre
  d'accessibilité, donc aucune ambiguïté de lien dupliqué pour les lecteurs d'écran ni pour les
  sélecteurs `getByRole` des tests.
- Topbar fine : titre de la page courante (source unique `frontend/src/config/navigation.js`
  partagée avec la sidebar). **Bug corrigé pendant la vérification** : ce titre était initialement
  un `<h1>`, entrant en conflit avec le `<h1>` propre à chaque page — deux titres de niveau 1
  identiques sur un même document, un vrai défaut d'accessibilité (pas seulement un souci de test).
  Redescendu en `<p>` : la topbar est une étiquette de localisation persistante, pas un second titre
  de document.

**Nouvelle page : Tableau de bord** (`/tableau-de-bord`, nouvelle route par défaut après connexion)
- Composée entièrement à partir des endpoints existants (assessments, monitoring, actions) —
  aucun endpoint backend ajouté, la donnée nécessaire existait déjà.
- Carte héro score de conformité (anneau SVG animé une seule fois au montage — `ScoreRing.jsx`,
  réutilisé sur Résultats — avec tendance vs évaluation précédente), carte météo du jour (icônes
  météo Sun/CloudSun/CloudLightning reprenant la métaphore ☀️/⚠️/🔴 déjà présente côté backend),
  alertes ouvertes (liste courte), progression du plan d'action avec quick wins (mesures impact
  élevé + effort faible non terminées), accès rapides.
- Onboarding en 3 étapes visuelles si aucune évaluation terminée (nouveau tenant) : Diagnostic →
  Plan d'action → Surveillance, chacune avec sa propre carte et son CTA.

**Refonte page par page** (détails dans les commits `feat(design): redesign ...`)
- **Diagnostic** : liste plate de 10 sections → assistant par étapes, un domaine ANSSI à la fois,
  barre de progression sticky globale + par domaine, réponses en `SegmentedControl` (role="radio"),
  navigation Précédent/Suivant gagnée par domaine (Suivant désactivé tant que le domaine courant
  n'est pas complet), reprise automatique au premier domaine incomplet plutôt que redémarrage
  systématique, écran de complétion sobre (une icône de succès, pas de confettis) avant renvoi vers
  les résultats.
- **Résultats** : `ScoreRing` héroïque, radar Recharts recoloré à la palette de marque (avec un
  correctif de troncature des libellés de domaines longs — bug pré-existant, révélé en testant avec
  de vraies données), cartes de détail par domaine avec barre de score colorée et lien direct vers
  le plan d'action filtré sur ce domaine.
- **Plan d'action** : vrai kanban 3 colonnes, cartes riches (badge « Quick win » quand impact élevé
  + effort faible, badge priorité, tags impact/effort, avatar-initiales de l'assigné à côté du
  sélecteur de réassignation), compteurs par colonne, filtre par domaine relié à `?domaine=` dans
  l'URL (permet le lien profond depuis Résultats).
- **Surveillance** : une carte par actif avec statut global calculé (pire état entre alertes
  ouvertes et derniers checks), historique d'uptime en barres recoloré, les 4 types de check en
  grille, panneau d'alertes ouvertes. Le formulaire de déclaration d'actif est passé dans une Modal.
- **Documents** : liste de documents en cartes sélectionnables (badge de statut, pas juste un
  libellé), éditeur de relecture nettoyé, export PDF rendu visuellement prioritaire (`variant
  primary`) par rapport à l'export Markdown (`secondary`).
- **Assistant** : vraie UI de chat — bulles avec avatar produit (icône Bot dans un rond marine),
  indicateur de génération en points qui rebondissent plutôt qu'une ligne de texte, suggestions de
  questions à la première utilisation, zone de saisie fixe en bas avec bouton d'envoi icône.
- **Connexion/Inscription** : écran deux panneaux (`AuthLayout.jsx`) — panneau de marque sombre à
  gauche (wordmark, tagline en Fraunces italique, 3 bénéfices produit), formulaire épuré à droite ;
  collapse en colonne unique (juste le wordmark) sur mobile. L'étape de challenge 2FA du login
  utilise le même panneau.
- **Sécurité (2FA) et Préférences de notification** : non nommées explicitement dans la mission mais
  restylées pour la même raison que le reste — « zéro style ad hoc dupliqué » s'applique à toute
  l'application, pas seulement aux pages listées.

**États et micro-interactions**
- Skeletons pendant les chargements sur toutes les pages (jamais de page blanche).
- EmptyState avec guidance + CTA sur chaque liste vide (documents, actifs, plan d'action, résultats).
- Erreurs migrées des messages inline vers le système de Toast global avec action « Réessayer » là
  où une nouvelle tentative a du sens (rechargement du tableau de bord, du plan d'action).
- Transition CSS uniforme à 180ms (`.transition-smooth`, désactivée sous
  `prefers-reduced-motion: reduce`) sur hover/focus/apparitions — aucune animation au-delà de ça
  (le mission demandait explicitement la sobriété).
- Focus visibles conservés partout (`focus-visible:outline-2` systématique sur les primitives).

### Tests et vérification
- **Vérification visuelle réelle** : capture d'écran Playwright (desktop 1440px, tablette 900px,
  mobile 390px) de chaque page refondue, avec un vrai compte de démonstration et de vraies données
  (diagnostic complété via l'API, actif surveillé avec alerte simulée via `simulate_check_failure`,
  Phase 5) — pas seulement l'état vide. Plusieurs itérations réelles à partir de ces captures, pas
  de « ça devrait aller » :
  - Radar Résultats : libellés de domaines longs tronqués par le bord du graphique — `outerRadius`
    et `tickFormatter` corrigés.
  - Deux jetons de couleur (`--color-ink-500`, `--color-ink-400`) ne passaient pas le seuil AA
    4,5:1 sur fond blanc/canvas malgré un rendu visuellement correct à l'œil — détecté par
    axe-core, pas par inspection visuelle, alors même que la vérification visuelle avait été faite
    en amont. Confirme que le contrôle automatisé reste nécessaire même après une revue à l'œil.
  - Un artefact de capture plein-page (footer `position: fixed` du diagnostic apparaissant à
    chevaucher le contenu) a été vérifié comme un artefact de l'outil de capture, pas un vrai bug —
    confirmé par une capture du viewport réellement scrollé jusqu'en bas.
- **Suite e2e Playwright + axe-core** (`frontend/e2e/`, 5 specs, contre la vraie stack
  docker-compose) : entièrement remise à niveau pour le nouveau markup, cf. « Difficultés » —
  **5/5 vertes**, **0 violation critique/sérieuse axe-core** sur l'ensemble des pages parcourues.
- Suite backend complète (323 tests) rejouée sans modification : verte, confirme l'absence de
  régression fonctionnelle (aucun fichier backend touché par cette mission).
- `ruff check`/`ruff format --check` (backend, inchangé) et `npm run lint` (frontend, 0 erreur, 2
  avertissements pré-existants sans rapport) verts.

### Difficultés rencontrées et solutions
- **Commentaire CSS fermant prématurément le bloc `@theme`** : le commentaire d'en-tête de
  `index.css` contenait littéralement la séquence `*/` (dans « `--color-*/--font-*/` », un raccourci
  visuel pour lister plusieurs préfixes) — qui ferme un commentaire CSS `/* ... */` avant l'endroit
  prévu. Tout le texte suivant (y compris le vrai `@theme` avec les jetons de couleur) se retrouvait
  interprété comme du CSS réel, provoquant une erreur « Unknown word --shadow-* » du serveur de dev
  à une ligne (1172) très éloignée de la source réelle (145 lignes) — les fichiers de police
  `@import`és sont inlinés avant ce commentaire lors du traitement, décalant fortement les numéros
  de ligne rapportés. Root cause trouvée en comparant : `npm run build` (pipeline de production,
  plus tolérant) passait, alors que le serveur de dev (pipeline postcss strict) échouait sur le
  même fichier — signal qu'il fallait chercher un problème de syntaxe fragile plutôt qu'une
  incompatibilité d'outils. Corrigé en reformulant le commentaire pour ne jamais faire apparaître
  `*/` involontairement.
- **Apostrophe droite vs courbe entre le JSX et les sélecteurs e2e** : le bouton « Terminer
  l'évaluation » utilise une apostrophe courbe (’) dans le JSX, conforme à la convention déjà
  établie ailleurs dans le projet (« Plan d'action », etc.), mais le test e2e réutilisait encore
  l'apostrophe droite (') de l'ancienne implémentation. `getByRole` ne normalise pas ce genre de
  caractère : le sélecteur ne matchait jamais, provoquant un timeout de 150 s en attente d'un
  bouton qui existait bel et bien à l'écran (confirmé par capture). Corrigé dans le test ; réaffirme
  la discipline déjà notée en Phase 4/5 de toujours utiliser l'apostrophe courbe dans le texte UI
  français du projet.
- **Course entre résolution réseau et rendu React dans la boucle e2e du diagnostic** : après le
  dernier `PUT`/`GET` d'un domaine, le test vérifiait immédiatement (`.count()`) si le bouton
  « Terminer l'évaluation » était présent pour savoir s'il s'agissait du dernier domaine — mais la
  promesse réseau résolue ne garantit pas que React a déjà validé le re-rendu qui insère ce bouton
  dans le DOM. Sur le dixième domaine, cette course faisait parfois cliquer le test sur un bouton
  « Suivant » qui n'existe plus une fois sur le dernier domaine, bloquant le test indéfiniment.
  Corrigé en attendant sur un locator combiné (`finishButton.or(nextButton).waitFor()`) qui laisse
  le mécanisme de nouvelle tentative de Playwright absorber la course, plutôt qu'un instantané
  synchrone.
- **Timeouts par défaut trop courts pour de vrais appels serveur enchaînés** : deux assertions
  (l'apparition de l'écran de complétion après `complete()`, qui déclenche
  `generate_action_plan` côté serveur pour 42 mesures ; l'apparition du plan d'action, qui enchaîne
  `actionsApi.listAll()` paginé + `tenantsApi.listMembers()` + `projectedScore()`) dépassaient
  parfois le timeout par défaut de 5 s de Playwright contre la vraie stack Docker Compose — pas un
  bug applicatif, juste un temps de traitement serveur réel plus long que l'attente par défaut d'un
  test. Timeouts étendus (15 s) sur ces deux assertions précises avec un commentaire expliquant
  pourquoi, plutôt qu'un `waitForTimeout` arbitraire global qui aurait ralenti toute la suite.
- **Jeton de couleur " correct à l'œil, invalide au contraste »** : `--color-ink-500` (texte
  secondaire utilisé partout) atteignait ~4,3:1 sur blanc — sous le seuil AA 4,5:1 — malgré un
  rendu visuellement tout à fait lisible. Recalculé (formule de luminance relative WCAG, cf. script
  Node utilisé en Phase 5 pour les mêmes vérifications) et assombri au niveau du jeton lui-même
  plutôt que patché usage par usage, pour que toute la palette reste garantie conforme d'un coup.

### Reste à faire (sessions suivantes)
- Découpage de code (`code-splitting`) du bundle frontend : l'avertissement Vite « chunks > 500 kB »
  pré-existant (Phase 1-5) n'a pas été traité cette session — hors périmètre d'une refonte visuelle,
  mais à envisager si le budget de performance frontend (Green IT, CLAUDE.md) devient un critère
  d'évaluation explicite.
- Le panneau d'alertes de Surveillance reste « ouvertes uniquement » — un panneau ouvert/résolu
  demanderait un nouvel endpoint d'historique des alertes résolues, hors du périmètre backend
  autorisé pour cette mission (« sauf si un endpoint léger manque pour le dashboard »).
- Tabs et Tooltip (primitives du kit) sont construits et exportés mais pas encore consommés par une
  page — aucun besoin identifié ne les justifiait dans cette passe ; disponibles pour la prochaine
  fonctionnalité qui en aura besoin plutôt que forcés dans une page qui n'en a pas l'usage.

---

## 2026-08-08 — Phase 7 : renseignement sur la menace (intégration Breachsense)

### Contexte
Mission complète, en autonomie : intégrer Breachsense (Cyber Threat Intelligence, palier
Essentials) comme nouvelle source de détection de compromissions — mode requête (scan de
diagnostic, quota partagé de 1000 requêtes/mois) et mode webhook (monitoring temps réel, pool
partagé de 15 actifs). Contraintes structurantes de la licence : quota, pool et débit (1 req/s,
bursts de 5) sont des ressources **partagées par toute la plateforme**, pas allouées par tenant —
contrainte centrale de toute la conception, très différente du quota IA (`AIUsageQuota`, par
tenant, Phase 4). L'API renvoie des secrets en clair (mots de passe, tokens, cookies) — règle
absolue : ne jamais les stocker (ADR-014).

**Arbitrage documenté (demandé explicitement, à ne pas trancher silencieusement)** : le cadrage
(§3.2, roadmap V2) prévoyait la détection de fuites via l'API Have I Been Pwned. Le prompt de
mission remplace ce choix par Breachsense. Ce n'est pas un simple changement de nom de fournisseur :
HIBP est une API de requête ponctuelle sans webhook, alors que Breachsense expose un canal de
notification temps réel et des catégories de fuite plus larges (stealer, sessions, NHI, dark web,
documents, surface d'attaque) — pertinent pour la promesse produit « surveillance continue » du
cadrage §1.3. Documenté dans ADR-013 et répercuté dans le cadrage (§3.2, la ligne HIBP est
remplacée, la M6 « Breachsense — intégré » ajoutée).

### Réalisé
- **ADR-013** (intégration Breachsense, choix d'architecture) et **ADR-014** (traitement des
  secrets de fuite — masquage, minimisation, rétention, RGPD).
- **Nouvelle app `threat_intelligence`** :
  - Interface abstraite `BreachIntelligenceProvider` (inversion de dépendance) + `NullProvider` de
    repli (aucune licence configurée → aucun appel réel, findings vides) + factory `get_provider()`.
  - Client HTTP bas niveau (`BreachsenseClient`) : header `lic`, pagination `206`→`200` automatique
    (plafond de sécurité), un type d'erreur par code (400/401/403/422/429/500), retries + backoff,
    tous les endpoints du palier Essentials (`/stealer`, `/combo`, `/creds`, `/sessions`, `/nhi`,
    `/darkweb`, `/docs`, `/asm`, `/radar`, `/account` avec ses actions add/del/list/test/rotate/
    audit/remaining). Le premium-marketplace (palier supérieur) est explicitement non implémenté
    (commentaire dans le code + noté en roadmap V2 du cadrage).
  - Throttle Redis (token-bucket, script Lua atomique, clé globale) sérialisant tous les appels
    sortants à 1 req/s, bursts de 5 — empêche structurellement les 429 plutôt que de les retenter.
  - `QuotaManager` : source de vérité `/account?action=remaining` (cache court, 5 min), marge de
    sécurité configurable, refus propre avant même d'appeler l'API.
  - Normaliseur : masquage récursif des secrets par nom de champ (pas une liste exacte par
    endpoint — délibérément robuste à des schémas hétérogènes), mapping de sévérité imposé par le
    prompt (stealer/sessions/nhi/darkweb = critique ; creds/combo/docs = élevé ; radar/asm =
    attention), minimisation des identifiants tiers (masqués sauf s'il s'agit de l'email pro d'un
    membre du tenant).
  - Modèles tenant-scopés `BreachFinding` (jamais de secret en clair), `MonitoredAsset` (pool de 15
    slots), `BreachIntelligenceUsage` (journal d'usage, pour l'attribution même si le budget est
    global), `BreachScanJob` (pattern job asynchrone réutilisé d'ADR-011).
  - Service `run_breach_scan` (mode requête) : cooldown anti-abus par tenant (manuel uniquement, le
    scan initial en est exempté), garde-fou quota, dédoublonnage, création d'`Alert` via le moteur
    existant d'`apps.monitoring` (nouveau type `BREACH_COMPROMISE`, nouvelle fonction publique
    `monitoring.services.open_or_update_alert` qui extrait la logique déjà privée du moteur plutôt
    que de la dupliquer).
  - Scan initial déclenché par un signal Django `post_save` sur `monitoring.Asset` — choix
    délibéré pour que `apps.monitoring` reste totalement ignorant de `threat_intelligence` (sens de
    dépendance correct). L'inscription au pool de 15 slots (webhook), elle, reste une action
    **explicite** distincte (bouton dédié) : automatiser l'inscription webhook sur chaque
    déclaration d'actif épuiserait vite une ressource partagée par toute la plateforme.
  - Webhook `POST /api/v1/webhooks/breachsense` : Basic Auth en temps constant
    (`hmac.compare_digest`), CSRF exempté (endpoint serveur-à-serveur), tenant résolu via
    `MonitoredAsset.provider_ref` (le webhook n'a ni JWT ni `X-Tenant-Id`), ingestion idempotente
    (contrainte d'unicité `(tenant, dedup_hash)`), les notifications `test:true` (vérification de
    connectivité côté Breachsense) sont reconnues et ignorées sans créer de fausse fuite.
  - API tenant-scopée (findings, actifs monitorés, déclenchement/suivi de scan, état quota/
    cooldown/pool) + back-office plateforme (`IsAdminUser`, quota/pool/journal — `platform_admin`
    restant un scaffold vide réservé à une phase ultérieure, cette vue est exposée directement par
    `threat_intelligence` plutôt que d'anticiper la construction du back-office complet).
  - Commande de gestion `simulate_breach_finding` (même esprit que `simulate_check_failure`, Phase
    3) : injecte une fuite simulée à travers le vrai pipeline d'ingestion, sans licence réelle.
- **Intégration IA** (pseudonymisée, ADR-005 réutilisé sans nouveau point d'appel) :
  `build_assistant_context`/`build_weather_context` incluent désormais les `BreachFinding` ouverts
  (jamais `raw_data`, jamais un secret). La météo ☀️/⚠️/🔴 reflétait déjà les compromissions via le
  moteur d'alertes réutilisé ; les templates email affichent maintenant le détail. Prompts
  assistant/météo passés en V2 (versionnage existant) avec consigne explicite de reformuler une
  compromission en langage dirigeant sans jamais mentionner de secret.
- **Frontend** : nouvelle page `/compromissions` (onglets ouvertes/traitées/ignorées, secrets/
  identifiants tiers masqués, explication en langage simple par type de fuite, bouton « Lancer un
  scan » avec quota/cooldown visibles, section surveillance temps réel avec inscription/
  désinscription par actif) ; bandeau critique + accès rapide sur le tableau de bord ; back-office
  `/admin/breachsense` (gate `is_staff` frontend + `IsAdminUser` serveur). Entièrement construit sur
  le design system existant (`ui/`, Sidebar, Tabs enfin utilisé — noté disponible-mais-inutilisé en
  Phase 6).
- **Sécurité** : `docs/security_review.md` mis à jour catégorie par catégorie (A01, A02, A04, A05,
  A07, A08, A09, A10) + section dédiée de synthèse des nouveaux flux et du volet RGPD.
- **Documentation** : cadrage (§3.1 nouvelle US-5.7 + M6, §3.2 roadmap corrigée, §4.2/§4.6 mis à
  jour, §5 ADR-013/014 ajoutées, §11 Phase 7 ajoutée), README (section Breachsense dédiée, variable
  d'environnement, note webhook non testable en local).

### Tests et vérification
- **219 tests dédiés `threat_intelligence`** (97 % de couverture sur le module) : client HTTP
  (pagination, chaque code d'erreur, retries), throttle (burst, blocage jusqu'au refill,
  non-dépassement sous concurrence réelle — vrai Redis, vrais threads), quota manager, normaliseurs
  (masquage, sévérité, dédoublonnage), **test de propriété dédié** (`test_no_secret_persistence.py`,
  ADR-014 §3) vérifiant par SQL brut qu'aucun secret connu n'apparaît en clair dans la ligne
  persistée pour chaque endpoint porteur de secret, provider Breachsense (client mocké) +
  NullProvider, services (ingestion/alerte/cooldown/quota/pool), API (étanchéité tenant sur chaque
  endpoint), webhook (basic auth, idempotence, CSRF), signal de scan initial, tâche Celery
  (idempotence, retry, échec définitif).
- **Non-fuite IA spécifique aux données Breachsense** (`ai_assistant/tests/test_pseudonymization.py`,
  nouvelle classe `TestBreachDataNoLeak`, réutilise les 4 scénarios à caractères spéciaux existants) :
  confirme qu'un `BreachFinding` réel (identifiant = email du tenant, secret réel) ne fuit ni dans le
  payload assistant ni dans celui de la météo enrichie, et — pour ne pas être trivialement vrai —
  confirme aussi qu'un placeholder pseudonymisé apparaît bien dans ce payload (la donnée atteint
  réellement le pipeline, elle n'a pas juste été oubliée).
- **Vérification réelle de bout en bout**, pas seulement « ça devrait marcher » :
  - Suite backend complète rejouée (455 tests, seuls les 3 tests d'export PDF pré-existants échouent
    — limite connue de l'environnement Windows local hors Docker, WeasyPrint nécessite des
    bibliothèques GTK absentes hors conteneur, sans rapport avec cette session).
  - Suite e2e Playwright (5/5) rejouée contre la vraie stack docker-compose après ajout de
    `/compromissions` au balayage d'accessibilité — 0 régression, 0 violation axe-core.
  - Conteneurs `web`/`worker`/`beat` réellement redémarrés pour charger la nouvelle app ; migrations
    réellement appliquées à la base du docker-compose de développement.
  - Captures d'écran Playwright avec des fuites simulées (`simulate_breach_finding`) : masquage
    confirmé **visuellement**, pas seulement en test unitaire (identifiant non-tenant affiché
    `co••••@ex••••.com`, secret affiché `••••••23`).
  - Le journal d'usage du back-office affiche de vraies lignes produites par le vrai pipeline
    (signal → tâche Celery réelle → `NullProvider` → `BreachIntelligenceUsage`) déclenché par les
    déclarations d'actifs de la suite e2e — preuve que le scan initial fonctionne bout en bout sur
    la vraie stack, pas seulement en test mocké.
  - Données de démonstration nettoyées après capture (fuites simulées supprimées, utilisateur de
    démo remis à `is_staff=False`) pour ne pas polluer l'environnement de test manuel du prochain
    smoke test.

### Difficultés rencontrées et solutions
- **Bug réel trouvé par le test de propriété non-fuite** : la première version de
  `test_no_secret_persistence.py` construisait un payload de test où le champ `id` valait
  volontairement la même chaîne que le secret — un artefact de construction de test, pas un scénario
  Breachsense réaliste (`id` est un identifiant de fuite, pas un duplicata du secret). Comme `id`
  n'est pas un nom de champ reconnu comme secret, il n'était pas masqué, et le test échouait à juste
  titre — mais sur un faux positif de sa propre fabrication. Corrigé en donnant à `id` une valeur
  distincte du secret dans le payload de test.
- **Dict de pagination partagé et muté entre pages** (`BreachsenseClient.get_paginated`) : le code
  initial réutilisait le même dict `params` d'une page à l'autre (`params["p"] = page`). Sans
  conséquence fonctionnelle en production (`requests` sérialise la requête de façon synchrone avant
  la mutation suivante), mais un test vérifiant les pages effectivement demandées
  (`session.request.call_args_list`) l'a révélé : `Mock` conserve une référence au dict, pas un
  instantané, donc tous les appels enregistrés pointaient vers l'état final du même objet. Corrigé
  en construisant un nouveau dict à chaque page — plus sûr à raisonner, plus facile à tester.
- **Simulation Celery de l'épuisement des tentatives** : mocker directement `.retry()` pour qu'il
  lève une exception ne représente pas fidèlement un « épuisement des tentatives » (en production,
  `.retry()` lève une exception de contrôle de flux que Celery intercepte, elle ne se propage jamais
  telle quelle à l'appelant). Corrigé en poussant un contexte de requête Celery
  (`task.push_request(retries=task.max_retries)`) pour que le code lise l'état réel qu'il verrait à
  la dernière tentative, plutôt que de simuler l'effet de bord d'un appel à `.retry()`.
- **Deux serveurs de développement Vite en parallèle** : un ancien serveur de dev (session de la
  refonte d'interface précédente), toujours actif sur le port 5173, absorbait le trafic Playwright
  via le rechargement à chaud (HMR) au lieu qu'un nouveau serveur propre démarre — a produit un échec
  e2e à une seule assertion, sur une page dont le contenu principal ne s'affichait pas (`main` vide
  dans l'arbre d'accessibilité), symptôme d'un état de HMR incohérent après une longue session
  d'édition. Diagnostiqué en constatant que `npm run build` (compilation fraîche) réussissait sans
  erreur alors que le serveur de dev échouait sur cette page précise — même signal diagnostique que
  le bug de commentaire CSS de la session précédente (« le build passe, le dev échoue » pointe vers
  un état de processus, pas vers une erreur de code). Résolu en tuant les processus Vite orphelins
  (ports 5173/5174) et en relançant un serveur propre ; suite entièrement verte ensuite.
- **`Tenant.objects` vs `TenantScopedManager`** : `apps.tenants.services.get_tenant` utilise le
  manager par défaut de `Tenant` (`Tenant.objects`), pas `all_objects` — `Tenant` lui-même n'hérite
  pas de `TenantScopedModel` (c'est la racine de l'isolation, pas une ressource scopée), donc son
  manager par défaut n'est pas le `TenantScopedManager` fail-closed des autres modèles. Vérifié avant
  d'écrire `tasks.py` (qui appelle cette fonction sans contexte de requête) plutôt que supposé —
  aurait été un bug silencieux (tâche Celery ne trouvant jamais le tenant) sinon.

### Reste à faire (sessions suivantes)
- **Smoke test avec la licence réelle** (explicitement à la charge de l'utilisateur, pas de
  cette session) : vérifier `/account?action=remaining`, un vrai scan de domaine, et l'inscription
  au pool de 15 slots contre l'API réelle — cette session s'est appuyée sur `NullProvider` en dev et
  sur un client mocké en test, jamais sur un appel réel à `api.breachsense.com`.
- **Webhook en conditions réelles** : non testable avant déploiement (URL publique requise). Au
  déploiement : définir `BREACHSENSE_WEBHOOK_CALLBACK_URL`, configurer les identifiants Basic Auth
  côté Breachsense (`/account?action=add&creds=...`), inscrire un premier actif au pool, puis
  déclencher une alerte de test (`send_test_alert` / action `test`) pour confirmer la connectivité
  de bout en bout.
- **Schéma exact des payloads Breachsense — résolu dans cette même phase** : voir l'addendum
  ci-dessous. Un smoke test avec la licence réelle reste néanmoins recommandé pour confirmer que le
  mapping construit à partir des schémas fournis correspond bien aux réponses réelles de l'API.
- **Purge automatique planifiée des `BreachFinding`** (rétention 90 jours, ADR-014 §5) : la politique
  de rétention est documentée mais la tâche Celery Beat de purge n'est pas implémentée dans cette
  phase — livraison du flux d'ingestion et de l'affichage d'abord.
- **`LOGGING` dict et outil de suivi d'erreurs** (gap déjà identifié en Phase 5, A09) : gagne en
  urgence avec ce module, qui manipule les données les plus sensibles de la plateforme à date.
- Le back-office CTI est exposé directement par `threat_intelligence` (gardé par `IsAdminUser`)
  plutôt que par un vrai module `platform_admin` construit — cohérent avec le scaffold vide actuel
  de cette app (réservée à une phase ultérieure), mais à réconcilier si `platform_admin` est un jour
  développé pour de vrai (éviter deux back-offices parallèles).

### Addendum (même jour) — schéma réel des endpoints Breachsense fourni par l'utilisateur

Après la livraison initiale, l'utilisateur a communiqué le schéma JSON réel de chaque endpoint du
palier Essentials (champs exacts par endpoint, jusque-là devinés à partir de la seule description
du prompt de mission). Corrections apportées à
`threat_intelligence/providers/breachsense/normalizer.py` :

- **Mapping exact par endpoint** (`ENDPOINT_SCHEMAS`) pour l'extraction de l'identifiant, de la
  date de fuite et du type de fuite — les noms de champs réels (`usr`/`eml`/`user_name`, `inf`/
  `fnd`/`found`/`leak_date`, `mal`/`category`/`content_type`/`type`) sont propres à chaque endpoint
  et ne correspondaient à aucune des clés génériques devinées initialement (`email`, `date`,
  `type`). L'ancienne heuristique générique est conservée en **repli** (schémas non couverts,
  dérive future), plus comme mécanisme principal.
- **Deux vrais bugs de masquage corrigés**, trouvés en confrontant les sous-chaînes génériques
  existantes au schéma réel :
  - `val` (valeur du cookie de session, `/sessions`) n'était masqué par **aucune** règle
    existante — un vrai gap de sécurité (le cookie de session, un secret au même titre qu'un mot
    de passe, aurait été persisté en clair). Corrigé par correspondance exacte de nom de champ
    (`EXACT_SECRET_FIELDS`), la sous-chaîne étant trop cryptique pour être fiable ici.
  - `ccn`/`ccx` (carte bancaire) et `cwa` (wallet crypto), propres à `/stealer`, avaient le même
    problème — mêmes corrections.
  - À l'inverse, la sous-chaîne générique `cookie` masquait à tort `cookie_name`/`cookie_path`
    (métadonnées, pas des secrets) et `hash` masquait à tort `file_hash` (`/docs`) et l'indicateur
    0/1 `hash` de `/creds` (« haché ou déchiffré », pas un secret) — retirées des sous-chaînes
    génériques.
  - Ces deux dernières corrections (`cookie`, `hash` retirés) n'étaient pas des fuites de secret
    (sur-masquage, pas sous-masquage) mais dégradaient la qualité de l'information affichée au
    dirigeant (`cookie_name`/`file_hash` auraient été inutilement masqués) — corrigées dans le même
    passage par souci de cohérence, pas seulement le gap `val`/`ccn`/`ccx`/`cwa` qui était le vrai
    risque de sécurité.
  - `asm.type == "pphish"` (typosquatting/phishing) élève désormais la sévérité à « élevé » plutôt
    que le niveau « attention » par défaut des autres sous-types `asm` (ns/mx/ast, simple
    inventaire de surface d'attaque).
- Suite de tests étendue en conséquence : `test_normalizer.py` couvre désormais un payload
  réaliste complet par endpoint (`REALISTIC_PAYLOADS`), avec des tests de non-régression explicites
  pour les deux corrections de sur-masquage (`cookie_name`/`file_hash` non masqués) ;
  `test_no_secret_persistence.py` utilise les vrais noms de champs secrets par endpoint, plus des
  cas dédiés pour les champs financiers de `/stealer` et la confirmation que `/darkweb`, `/radar`
  et `/asm` n'ont, par construction, aucun champ secret. ADR-014 mis à jour (§2, addendum) pour
  documenter ce changement de mapping et sa raison. 348 tests rejoués verts (hors les 3 tests PDF
  WeasyPrint pré-existants, limite d'environnement Windows local sans rapport).

**Reste à faire, inchangé** : un smoke test avec la licence réelle demeure la seule façon de
confirmer que ce mapping — construit à partir des schémas fournis, pas d'un appel réel à l'API —
correspond exactement aux réponses effectives de Breachsense.

---

## 2026-08-08 (suite) — Chiffrement réversible et révélation privilégiée des secrets de fuite

### Contexte
Session de suite, même jour : le dirigeant a un besoin métier légitime que le masquage définitif
d'ADR-014 ne couvre pas — retrouver la valeur exacte d'un mot de passe compromis (pas seulement
savoir qu'il a fuité), par exemple pour vérifier une réutilisation ailleurs avant de le faire
changer partout. Mission : remplacer le masquage définitif par un chiffrement réversible à accès
privilégié, ré-authentifié et tracé, sans jamais persister le secret en clair.

### Réalisé

**Modèle et migration**
- `BreachFinding.secret_seen` retiré, remplacé par `has_secret` (même rôle d'indicateur) et
  `secret_encrypted` (`BinaryField`, blob Fernet). Migration volontairement `RemoveField` +
  `AddField`, jamais un `RenameField` : `has_secret` doit refléter « un secret chiffré est
  réellement disponible », pas hériter de la valeur de l'ancien indicateur pour des findings déjà
  en base qui, eux, n'ont jamais eu de secret conservé — les deux valeurs par défaut (`False`/`b""`)
  s'appliquent donc à toutes les lignes existantes, sans script de migration de données dédié.
- Nouveau modèle `SecretRevealAudit` (tenant-scopé) : qui, quel finding, quel tenant, horodatage,
  IP, user-agent, succès/refus et raison du refus — jamais le secret.

**Chiffrement**
- Clé Fernet dédiée `BREACH_SECRET_ENCRYPTION_KEY` (variable d'env, jamais commitée), distincte de
  `TOTP_ENCRYPTION_KEY` et `AI_PSEUDONYMIZATION_KEY` — même principe de séparation déjà en place
  dans le projet. `threat_intelligence.services.encrypt_secret`/`decrypt_secret`, mêmes conventions
  que `apps.accounts.services`/`apps.ai_assistant.services`.
- `normalizer.mask_payload` retourne désormais aussi la valeur en clair du secret représentatif
  (celui qui produisait déjà `secret_masked`) — jamais journalisée, poppée et chiffrée
  immédiatement par `services.ingest_raw_findings` avant tout appel à `BreachFinding.objects.create`.

**Endpoint de révélation** (`POST /api/v1/threat-intelligence/findings/{id}/reveal/`)
- Conditions cumulatives : rôle admin du tenant (ou `is_staff` s'il est déjà membre du tenant — pas
  de mécanisme d'emprunt d'identité inter-tenant dans cette plateforme, limite de portée assumée et
  documentée dans ADR-014) ; ré-authentification fraîche à **chaque** appel (mot de passe ou code
  TOTP, réutilise directement les primitives 2FA d'`apps.accounts.services`) ; étanchéité tenant
  stricte (`services.get_finding` reste filtré par `request.tenant`).
- Le contrôle de rôle est fait **manuellement** dans la vue plutôt que via `permission_classes`,
  précisément pour que chaque refus (y compris « rôle insuffisant ») soit tracé dans
  `SecretRevealAudit` — le court-circuit habituel de DRF sur un `has_permission` figé ne l'aurait
  pas permis.
- Rate limiting dédié et strict (`5/min` par utilisateur, `10/min` par IP), plus serré que le
  rate limiting générique par tenant — anti-extraction-massive même via un compte admin compromis.
  Réponse `Cache-Control: no-store`.
- Journal consultable par l'admin du tenant (ses propres tentatives, `GET /audit/reveals/`, gardé
  par `IsTenantAdmin` strict) et par l'admin plateforme (agrégat toutes entreprises, ajouté à
  `ThreatIntelligenceAdminStatusView`).

**Frontend**
- `CompromisesPage.jsx` : bouton « Révéler le mot de passe » sur les findings `has_secret`, visible
  aux admins de tenant et aux utilisateurs plateforme ; panneau « Journal des révélations » (rôle
  admin strict, chargement à la demande).
- `RevealSecretModal.jsx` (nouveau) : ré-authentification (mot de passe ou code TOTP) puis
  affichage éphémère du secret (masqué automatiquement après 30s ou à la fermeture), copie
  presse-papier, bandeau de traçabilité — état local uniquement, jamais dans le contexte global,
  jamais persisté côté client.
- `AdminBreachsensePage.jsx` : nouvelle table « Journal des révélations de secrets » (agrégat
  toutes entreprises).

**Documentation**
- ADR-014 : nouvelle section « Mise à jour — chiffrement réversible et révélation privilégiée »
  documentant le revirement assumé (l'option A, initialement rejetée, est reconsidérée avec des
  mesures compensatoires que la version initiale de l'ADR n'avait pas anticipées), l'arbitrage
  bénéfice/risque, et la portée exacte du bypass `is_staff`.
- `docs/security_review.md` : A01 (contrôle de rôle manuel + traçabilité, étanchéité tenant sur la
  révélation), A02 (chiffrement réversible remplace la non-persistance, test de propriété étendu à
  `secret_encrypted`), A07 (step-up authentication, rate limiting dédié), section RGPD Phase 7
  (conservation chiffrée assumée, traçabilité des accès, minimisation inchangée pour le reste du
  payload), synthèse finale.

### Décisions
- `has_secret` remplace `secret_seen` (rename sémantique, pas juste cosmétique) : les deux notions
  ont cessé de coïncider avec ce changement (« un secret était présent à l'ingestion » vs. « un
  secret chiffré est disponible pour révélation »).
- Contrôle de rôle manuel plutôt que `permission_classes`, pour permettre l'audit complet de tous
  les refus, y compris ceux qu'un `has_permission` DRF standard aurait court-circuités avant
  d'atteindre le code de la vue.
- Pas de session/jeton d'élévation mis en cache pour le step-up : chaque révélation exige une
  preuve fraîche (mot de passe ou TOTP) fournie dans la requête elle-même, plus simple et sans
  nouvelle surface d'état côté serveur qu'un mécanisme de « sudo mode » à durée de vie propre.
- Portée du bypass `is_staff` limitée aux tenants dont l'utilisateur plateforme est déjà membre
  (via une adhésion réelle, comme tout le reste de la plateforme) — pas de mécanisme d'emprunt
  d'identité inter-tenant construit spécialement pour ce cas, choix documenté dans ADR-014 plutôt
  que décidé silencieusement.

### Difficultés rencontrées et solutions
- Renommer `secret_seen` en `has_secret` cassait un appel cross-app non repéré au premier passage :
  `apps.ai_assistant.services.build_assistant_context` lit `finding.secret_seen` pour le contexte
  IA pseudonymisé (`secret_expose`). Trouvé par une recherche exhaustive de toutes les références au
  champ avant de considérer le renommage terminé, pas seulement dans `threat_intelligence` lui-même
  — corrigé, suite `test_pseudonymization.py` toujours verte ensuite (aucune fuite du secret réel
  vers l'IA, propriété déjà couverte et non affectée par ce changement).
- La fixture de clé Fernet de test (`BREACH_SECRET_ENCRYPTION_KEY`) placée initialement dans
  `apps/threat_intelligence/tests/conftest.py` ne suffisait pas : `ingest_raw_findings` est aussi
  appelé depuis `apps/ai_assistant/tests/test_pseudonymization.py` (portée de fixture pytest limitée
  au sous-arbre de conftest), provoquant des échecs `ThreatIntelligenceError` dans un module qui
  n'a pourtant rien à voir avec le chiffrement des secrets de fuite. Déplacée vers le `conftest.py`
  racine (même endroit que `_fast_password_hashing`), qui s'applique à toute la suite — cohérent
  avec le fait que ce chiffrement est désormais une dépendance transverse, pas propre à un seul app.
- Test du step-up TOTP : une fois la 2FA confirmée pour un utilisateur de test, `LoginView` renvoie
  un challenge MFA au lieu de jetons directement — le helper `_auth` standard (login mot de passe)
  échouait avec un `KeyError` sur `access`. Résolu en émettant le JWT directement
  (`RefreshToken.for_user`) pour ces tests spécifiques plutôt qu'en re-testant tout le flux de
  connexion à deux étapes, déjà couvert par ailleurs (`apps.accounts.tests.test_two_factor`).
- Vérification navigateur de bout en bout tentée (skill `run`) mais bloquée : le moteur Docker
  Desktop, joignable en début de session (`docker compose ps` fonctionnait), est devenu injoignable
  en cours de session (pipe Windows introuvable) sans action de ma part — probablement mis en veille
  ou redémarré côté hôte. N'ayant pas relancé Docker Desktop moi-même (action système hors du
  périmètre sûr de l'automatisation), la vérification visuelle du flux de révélation en conditions
  réelles (bouton, modale, journal) n'a **pas** été faite cette session — seule la suite de tests
  automatisée (501 tests verts, hors les 3 tests PDF WeasyPrint pré-existants sans rapport ;
  17 dédiés à la révélation) et la compilation/lint frontend l'ont été. À refaire dès que
  l'environnement Docker est disponible.

### Addendum (même jour) — vérification navigateur end-to-end après redémarrage de Docker Desktop

L'utilisateur a redémarré Docker Desktop ; la vérification différée ci-dessus a été faite.

- `docker compose up -d` a d'abord échoué partiellement : `web`/`beat` sont sortis en erreur
  (`Exited (1)`) sur `django.db.utils.ProgrammingError: column "secret_seen" ... does not exist` —
  une course entre les trois entrypoints (`web`/`worker`/`beat`) exécutant chacun `migrate` au
  démarrage : l'un des trois a appliqué la migration 0002 avec succès (schéma vérifié ensuite par
  `psql \d` : `has_secret`/`secret_encrypted`/`secretrevealaudit` présents, `secret_seen` absent),
  les deux autres ont couru dessus une fraction de seconde trop tard et ont crashé sur une colonne
  déjà supprimée par le premier. Résolu en relançant simplement `web`/`beat` (migration déjà
  appliquée, donc no-op au second passage) — pas un bug du code, un artefact de multiples
  entrypoints Docker migrant la même base concurremment sans verrou applicatif, déjà latent avant
  cette session (accepté tel quel, hors périmètre de cette phase).
- `BREACH_SECRET_ENCRYPTION_KEY` manquait dans le `backend/.env` réel de développement (seul le
  placeholder de `.env.example` avait été ajouté) — généré et ajouté, `web`/`worker`/`beat`
  redémarrés pour le charger.
- Suite Playwright ad hoc (flow complet : inscription, déclaration d'actif, injection d'une fuite
  simulée via `manage.py simulate_breach_finding`, révélation avec mauvais mot de passe puis bon
  mot de passe, journal des révélations côté tenant, passage en admin plateforme via `is_staff` et
  vérification du journal agrégé) — **un vrai bug trouvé et corrigé** :
  l'intercepteur Axios générique (`apiClient.interceptors.response.use`, `frontend/src/api/
  client.js`) retente automatiquement toute requête en 401 après rafraîchissement du jeton d'accès
  — pensé pour le cas « jeton expiré », jamais auparavant confronté à un 401 métier sur un endpoint
  déjà authentifié. Le step-up de révélation renvoie précisément ce cas (mauvais mot de passe/code
  → 401), ce que l'intercepteur interprétait à tort comme un jeton expiré : il rafraîchissait le
  jeton (qui n'avait pourtant rien d'invalide) et **resoumettait silencieusement la même requête
  une seconde fois** — un seul clic utilisateur produisait deux tentatives réelles côté serveur,
  visibles en double dans `SecretRevealAudit` et comptant double contre le rate limit dédié
  (5/min). Trouvé uniquement grâce à la vérification navigateur réelle (invisible en pytest, qui
  n'exerce jamais l'intercepteur HTTP du frontend). Corrigé par un flag `skipAuthRetry` sur la
  requête de révélation (`endpoints.js`) que l'intercepteur respecte désormais — vérifié après
  correctif : un clic = un seul appel réseau, une seule ligne d'audit.
- Suite verte confirmée après redémarrage propre : 501 tests backend (hors les 3 WeasyPrint/
  Windows pré-existants), lint frontend propre, et le scénario Playwright ci-dessus rejoué au vert
  après le correctif (captures d'écran : carte de fuite avec bouton « Révéler », modale de
  ré-authentification, secret affiché en clair avec compte à rebours et copie, journal des
  révélations côté tenant, journal agrégé côté admin plateforme — tous conformes au design attendu).

### Reste à faire (sessions suivantes)
- **Suite Vitest** : CLAUDE.md prévoit des tests de composants frontend critiques, mais aucune suite
  Vitest n'existe encore dans ce projet (ni dépendances, ni config) — `RevealSecretModal.jsx` reste
  donc non couvert par des tests unitaires frontend, comme tout le reste du frontend à ce stade.
  Mise en place de l'outillage Vitest hors périmètre de cette session (changement d'outillage
  transverse, pas propre à cette fonctionnalité).
- **Purge automatique planifiée des `BreachFinding`** (et donc de `secret_encrypted`) : toujours pas
  implémentée (reste-à-faire déjà noté en Phase 7 initiale, inchangé par cette mise à jour).
- **Rotation des clés Fernet** (dont la nouvelle `BREACH_SECRET_ENCRYPTION_KEY`) : toujours
  manuelle, reste-à-faire déjà noté pour `TOTP_ENCRYPTION_KEY`/`AI_PSEUDONYMIZATION_KEY`
  (`docs/security_review.md`, A02).

---

## 2026-08-10 — Phase 8A : socle de démonstration client + radar pré-incident

### Contexte
Le produit va être présenté en démo live (écran partagé) à des prospects. Deux contraintes
structurantes : la démo ne doit jamais dépendre d'un appel API Breachsense en direct, et le quota
de la licence réelle (1000 requêtes/mois, partagé par toute la plateforme) ne doit être consommé
ni par les tests ni par le développement courant.

### Réalisé

**Modes CTI et cassettes rejouables (ADR-015)**
- Nouveau réglage `BREACHSENSE_MODE` : `live` / `replay` / `null` / `auto` (défaut).
- Nouveau `ReplayProvider` : sert des cassettes JSON depuis
  `apps/threat_intelligence/tests/fixtures/breachsense/`, **zéro appel réseau**, et renvoie
  `requests_consumed=0` (un rejeu ne doit pas gonfler les compteurs d'usage d'une dépense qui n'a
  pas eu lieu).
- `get_provider()` sélectionne désormais sur le **mode**, plus sur la simple présence d'une clé de
  licence — et le défaut ne bascule **jamais** en `live`, même licence configurée. C'est le cœur
  de l'ADR-015 : disposer d'une licence est une capacité, pas une instruction de la dépenser.
- `record_breachsense_cassette --domain X --confirm-live-call` : seule commande du dépôt qui appelle
  délibérément l'API réelle (elle instancie `BreachsenseProvider` directement, sans passer par
  `get_provider()` — contourner le mode configuré est précisément son rôle). Les payloads passent
  par `normalizer.mask_payload` **avant** écriture : l'ADR-014 s'applique aux fixtures comme à la
  base, une cassette ne contient jamais de secret en clair et est donc committable.
- `apps/threat_intelligence/README.md` documente les modes et la procédure d'enregistrement.

**Tenant de démonstration**
- `seed_demo_tenant` (idempotente, `--reset`, garde-fou `--allow-production` si `DEBUG=False`) :
  crée « Demo — Cabinet Comptable Durand » avec 3 utilisateurs, 4 actifs (domaine, site, VPN,
  webmail) et 12 fuites couvrant **tous** les `source_endpoint`, dates étalées sur ~6 mois.
- Les fuites sont créées via `services.ingest_raw_findings`, donc à travers le pipeline **réel**
  (masquage, chiffrement du secret, dédoublonnage, ouverture d'alerte) — pas une insertion directe
  en base qui divergerait silencieusement du comportement de production. C'est aussi ce qui rend la
  commande naturellement idempotente : mêmes payloads donnent mêmes `dedup_hash`, donc aucun doublon.
- Données de démo non confondables avec du réel : slug réservé `demo-cabinet-durand`, préfixe de nom
  « Demo — », et « mots de passe » manifestement factices mais crédibles à l'écran
  (`Hiver2024!durand`).

**Radar pré-incident**
- `GET /api/v1/threat-intelligence/pre-incident/` : les findings `radar`/`darkweb`/`asm` **ouverts**
  du tenant, groupés par **nature de signal** — une classification qui ne recouvre pas 1:1 les
  `source_endpoint` : `radar` mélange un dépôt de domaine ressemblant (actionnable, urgence élevée)
  et une simple mention publique (informationnel), et seul le sous-type phishing d'`asm` est un vrai
  signal pré-incident plutôt que de l'inventaire. Chaque groupe porte une phrase de vulgarisation
  (une phrase, sans jargon) et un niveau d'urgence, calculés côté serveur pour que le frontend n'ait
  aucune règle métier à dupliquer.
- Frontend : carte « Signaux avant-coureurs » en haut de la page Compromissions, visuellement
  distincte (fond et bordure « veille », icône radar, **pas de rouge** — le rouge reste réservé aux
  compromissions avérées, sinon on habitue le dirigeant à ignorer les vraies alertes). État vide
  soigné : « Aucun signal avant-coureur détecté — votre exposition publique est calme ».
- Notification dédiée : un signal `radar`/`darkweb`/`asm` arrivant **par webhook** déclenche un email
  « signal avant-coureur » (nouveau `EmailLog.Kind`, templates dédiés) au ton délibérément différent
  d'une alerte de compromission — il dit explicitement qu'aucune donnée n'a fuité. Volontairement
  webhook-only : un scan de diagnostic remonte d'un coup tout l'historique de signaux, les mailer
  tous serait du bruit — la valeur de cette notification est que quelque chose vient de *changer*.

### Décisions
- Le défaut `auto` ne résout jamais vers `live` (ADR-015 §2) : c'est la décision structurante de la
  phase, elle ferme par construction — pas par discipline — le risque d'épuisement silencieux du
  quota partagé.
- La suite de tests force `BREACHSENSE_MODE=null` par défaut (conftest racine) : le résultat des
  tests ne doit jamais dépendre des cassettes qui se trouvent committées, ni pouvoir partir sur le
  réseau. Les tests de rejeu s'y inscrivent explicitement, avec leur propre répertoire de cassettes.
- Seed via le pipeline réel plutôt qu'en insertion directe (voir ci-dessus) — option explicitement
  pesée et tranchée dans l'ADR-015 (« Options étudiées », B).
- `--reset` efface les données CTI/alertes du tenant de démo mais **pas** le tenant, ses
  utilisateurs ni ses actifs : rejouer la commande juste avant une démo ne doit pas invalider une
  session déjà ouverte à l'écran.

### Difficultés rencontrées et solutions
- **Échappement HTML dans un email en texte brut** : le rendu Django applique l'autoescape à
  **tous** les templates, extension `.txt` comprise. La phrase de vulgarisation contenant une
  apostrophe (« Quelqu'un a déposé... »), l'email texte affichait `Quelqu&#x27;un`. Invisible
  jusqu'ici parce qu'aucun template texte existant n'interpolait de valeur contenant une apostrophe
  (uniquement des URL d'actifs et des libellés). Corrigé par `{% autoescape off %}` sur le template
  texte (le HTML garde l'échappement, qui y est correct). Trouvé par un test qui comparait la phrase
  rendue à la constante source — une assertion « le texte affiché est bien celui qu'on a écrit »,
  pas seulement « un email est parti ».
- **Garde-fou de production vs. suite de tests** : la suite tourne avec `DEBUG=False`, donc le
  garde-fou de `seed_demo_tenant` faisait échouer tous les cas nominaux. Résolu par une fixture
  locale activant `DEBUG=True`, le garde-fou lui-même restant testé à part — plutôt que d'affaiblir
  la condition côté commande pour arranger les tests.
- **Assertion de démo trop spécifique** : le scénario Playwright visait le premier bouton
  « Révéler » en attendant le mot de passe du finding *stealer*, alors que les fuites sont triées
  par détection décroissante — le premier finding porteur de secret est le cookie de session M365.
  La fonctionnalité était correcte, l'attente du test ne l'était pas. Corrigé en visant la valeur
  réellement attendue (et c'est le meilleur cas à montrer en premier en démo : le cookie qui
  contourne la double authentification).

### Vérification
- 549 tests backend verts (49 nouveaux : modes/rejeu, seed, radar pré-incident, notification), hors
  les 3 tests PDF WeasyPrint pré-existants (limite d'environnement Windows local, sans rapport).
  `ruff check` propre.
- Lint frontend propre (2 avertissements pré-existants sans rapport).
- Scénario de démo déroulé en navigateur réel (Playwright) sur le tenant seedé : connexion,
  Compromissions, carte Radar (les 3 natures de signal affichées avec leur vulgarisation), liste
  des fuites, révélation d'un secret seedé avec ré-authentification. Vert.

### Reste à faire (sessions suivantes)
- **Doublon d'affichage assumé, à arbitrer** : les findings `radar`/`darkweb`/`asm` apparaissent à
  la fois dans la carte « Signaux avant-coureurs » et dans la liste des fuites en dessous. C'est
  actuellement nécessaire — seule la liste porte les actions « Ignorer »/« Marquer traité », donc
  les retirer rendrait ces signaux impossibles à traiter et ils resteraient indéfiniment dans la
  carte. À trancher au niveau produit : soit porter les actions dans la carte et filtrer la liste,
  soit assumer le doublon (résumé + détail).
- **Purge planifiée** et **rotation des clés Fernet** : reste-à-faire inchangés (Phases 7 et 8).
- **Smoke test avec la licence réelle** : toujours à faire, et c'est désormais le moment naturel
  pour enregistrer les premières vraies cassettes (`record_breachsense_cassette`), qui remplaceront
  la cassette synthétique de démo actuellement committée.

---

## 2026-08-11 — Phase 8B : fil d'exposition priorisé (« le médecin, pas la chemise de résultats »)

### Contexte
La Phase 8A livrait une page Compromissions correcte mais qui laissait au dirigeant tout le travail
d'interprétation : une liste plate de fuites, sans hiérarchie ni conduite à tenir. Objectif de cette
phase : passer d'un rendu de résultats à un avis — quoi regarder en premier, ce que ça veut dire,
quoi faire — et trancher au passage le doublon d'affichage laissé ouvert en 8A.

### Réalisé

**Tâche 0 — arbitrage 8A tranché**
- La carte « Signaux avant-coureurs » porte désormais « Marquer traité » / « Ignorer » (mêmes
  transitions de statut, mêmes permissions que la liste) et un lien « Voir les signaux traités ».
- `services.list_findings` exclut par défaut les endpoints pré-incident : la liste Compromissions
  ne montre plus que des fuites avérées. Le paramètre `include_pre_incident=True` restitue la vue
  complète pour les appelants qui raisonnent sur l'exposition d'un actif et non sur une liste.
- ADR-013 amendé en conséquence (la sémantique de la liste qu'il documentait a changé).

**Tâche 1 — score d'exposition (ADR-016)**
- Calcul entièrement déterministe (`exposure.py`), sans aucun appel IA : sévérité (40/22/8),
  fraîcheur (×1,0 à ×0,35), secret réellement récupérable (+10), statut ouvert uniquement.
  Contributions décroissantes (×0,6 par rang) et plafond à 100, pour que dix broutilles anciennes ne
  passent jamais devant une fuite critique fraîche.
- Le calcul renvoie **toujours** ses composantes avec le total : l'API les expose, l'interface les
  affiche sous « Comment ce score est calculé ». Un score qu'on ne peut pas justifier devant un
  client ne vaut rien — c'est le cœur de l'ADR-016.
- Seuils des quatre niveaux en configuration (`EXPOSURE_LEVEL_THRESHOLDS`), pas en dur.

**Tâche 2 — vulgarisation déterministe**
- Module dédié `plain_language.py` : pour chaque `source_endpoint` (et le sous-type phishing d'ASM),
  « ce que ça veut dire » + « l'action à mener », en français simple, vouvoyé, sans jargon nu.
  Aucun appel IA : ces phrases s'affichent immédiatement, sans latence ni quota.
- Exposées par l'API sur chaque finding (`meaning` / `recommended_action`), donc identiques partout.
  Le tableau de textes qui existait **en dur dans le frontend** depuis la Phase 7 a été supprimé au
  profit de ces champs : il commençait déjà à diverger de ce que le backend racontait ailleurs.

**Tâche 3 — fil d'exposition**
- `GET /threat-intelligence/exposure-feed/` : fuites ouvertes groupées par actif, chaque groupe avec
  son score, ses composantes et ses findings triés par (sévérité, fraîcheur) ; groupes triés par
  score décroissant.
- Nouvelle page frontend « Exposition », placée au-dessus de Compromissions dans la navigation.
  Cartes par actif avec cadran de score, dépliables sur le détail. La carte Radar de 8A y a été
  déplacée (tout en haut). C'est cette page qu'on ouvre en démonstration.

**Tâche 4 — synthèse IA contextuelle**
- Modèle `ExposureSynthesis` (une ligne par tenant : c'est un cache, pas une piste d'audit —
  `AIUsageLog` trace déjà chaque appel), job asynchrone (pattern ADR-011), routage Haiku (ADR-004),
  quota par tenant existant.
- Pipeline ADR-005 complet : pseudonymisation avant appel, ré-injection après. Le contexte transmis
  exclut délibérément jusqu'au `secret_masked` — « ••••••23 » n'aide en rien une mise en relation, et
  le laisser partir ouvrirait une discussion inutile sur ce qui sort chez le fournisseur.
- Invalidation à chaque création de fuite et à chaque changement de statut. La synthèse est marquée
  **obsolète** plutôt que supprimée : on peut ainsi afficher « antérieure à vos dernières actions »
  au lieu de faire disparaître le bandeau sans explication.
- La page est complète sans synthèse : aucun spinner bloquant, aucun état d'erreur, le bandeau est
  simplement absent. Cooldown de 10 min sur le bouton « Actualiser l'analyse ».
- `seed_demo_tenant` pose une synthèse pré-générée (texte fixe, jamais un appel IA au seed), rédigée
  pour correspondre exactement aux fuites seedées — même principe que les cassettes de l'ADR-015.

### Décisions
- **Score déterministe, jamais IA** (ADR-016) : reproductibilité et justifiabilité priment sur la
  finesse. L'IA lit l'exposition, elle ne la mesure pas — deux modules distincts, aucune dépendance.
- **Vulgarisation en module Python**, ni en base ni en templates : ce sont des constantes produit à
  relire et versionner comme du texte éditorial, et les tests peuvent assertir dessus.
- **Synthèse marquée obsolète plutôt que supprimée** : dire « cette analyse date d'avant vos
  dernières actions » est plus honnête que faire disparaître le bandeau.
- **Actions dans la carte AVANT de filtrer la liste** : l'ordre comptait. Retirer les signaux de la
  liste sans leur donner d'actions ailleurs les aurait rendus intraitables et bloqués à vie dans la
  carte.

### Difficultés rencontrées et solutions
- **Un défaut plus restrictif rétrécit silencieusement les appelants existants** : passer
  `list_findings` à « fuites avérées seulement » a modifié, sans erreur ni test rouge, le contexte
  envoyé à l'assistant IA et à la météo quotidienne — qui voyaient depuis la Phase 7 l'ensemble des
  findings. Repéré en relisant les appelants avant de considérer le changement terminé, pas signalé
  par la suite de tests (aucun test n'affirmait que la météo voit les signaux radar). Les deux
  appels ont été explicitement passés à `include_pre_incident=True`.
- **Page bloquée sur son squelette de chargement, API saine** : symptôme d'un serveur Vite en état
  HMR incohérent après une longue session d'édition — déjà rencontré et consigné lors d'une session
  précédente. Diagnostiqué en mesurant les endpoints directement (`exposure-feed` : 200 en 0,19 s)
  avant de suspecter le code ; résolu en redémarrant proprement le serveur de dev. Réflexe à garder :
  « le front tourne en rond mais l'API répond » pointe vers le processus, pas vers le code.
- **Assertion Playwright trop courte face à un coût de sécurité voulu** : la révélation d'un secret
  vérifie le mot de passe avec le hasher de production (PBKDF2, 1 000 000 d'itérations) — ~1,6 s
  mesuré en isolation, davantage sous charge, ce qui dépassait le délai par défaut de 5 s. Ce n'est
  pas une lenteur à corriger mais le coût assumé du step-up : délai du test porté à 20 s, avec le
  commentaire expliquant pourquoi.
- **Une assertion de test qui matchait le texte d'introduction de la page** : la vérification « la
  liste ne contient plus de signaux dark web » tombait sur la phrase d'introduction que je venais
  d'écrire, laquelle mentionne ces catégories à dessein. Corrigé en ciblant les libellés des cartes
  de fuite plutôt que le texte libre — la fonctionnalité était correcte depuis le début.
- **« +0 » dans l'explication du score** : la 7e fuite d'un actif contribue ~0,37 point, donc « +0 »
  à l'affichage — honnête, mais se lit comme un bug côté client. Rendu « moins de 1 » plutôt que
  d'arrondir à 1 (ce qui aurait faussé la somme affichée) ou de masquer la ligne (ce qui aurait
  rendu l'explication incomplète).

### Vérification
- 639 tests backend verts (90 nouveaux : score et ses cas limites, vulgarisation et sa couverture
  éditoriale, fil d'exposition et étanchéité tenant, filtrage de la liste, historique des signaux,
  cache/invalidation de la synthèse, non-fuite d'identifiants vers le fournisseur). Hors les 3 tests
  PDF WeasyPrint pré-existants (limite d'environnement Windows local, sans rapport). `ruff` propre.
- Lint frontend propre (2 avertissements pré-existants sans rapport).
- Scénario de démonstration déroulé en navigateur réel (Playwright) sur le tenant Durand : connexion,
  page Exposition, bandeau de synthèse, carte Radar, traitement d'un signal depuis la carte,
  historique des signaux traités, dépliage d'un actif, explication du score, vulgarisation, révélation
  d'un secret avec ré-authentification, et vérification que la liste Compromissions ne contient plus
  que des fuites avérées. Vert.

### Reste à faire (sessions suivantes)
- **Tests de propriété sur la vulgarisation** : la couverture éditoriale est testée (chaque endpoint
  a une entrée, ton vouvoyé, pas de jargon listé), mais rien ne garantit qu'une entrée future reste
  *compréhensible* — cela demanderait une relecture humaine, pas un test.
- **Pondération par type d'actif** dans le score (un VPN vaut-il plus qu'un site vitrine ?) : non
  couvert, tous les actifs déclarés sont à égalité. À rouvrir sur retour client (ADR-016).
- **Suite Vitest** : toujours absente du projet ; `ExposurePage`/`PreIncidentRadar` restent sans
  tests unitaires frontend, comme le reste du frontend.
- **Purge planifiée**, **rotation des clés Fernet**, **smoke test licence réelle** : reste-à-faire
  inchangés des phases précédentes.

---

## 2026-08-11 (suite) — Phase 8C : corrélation de réutilisation et cycle de vie complet du secret

### Contexte
Trois chantiers distincts réunis par un même fil : donner à la révélation de secret (Phase 8) une
raison d'être produit (la corrélation), et fermer les deux questions que le chiffrement réversible
laissait ouvertes (les secrets s'accumulaient indéfiniment ; la clé n'était pas rotable).

### Réalisé

**Tâche 0 — fermeture du couplage implicite repéré en 8B**
- Nouveau fichier `test_shared_scope_contract.py` : épingle le périmètre de findings vu par
  l'assistant IA, la météo et la synthèse d'exposition, sur le tenant de démo (seul jeu du dépôt
  couvrant tous les `source_endpoint`). L'en-tête du fichier explique l'incident 8B et pourquoi ces
  tests ne sont pas un doublon — pour qu'un futur lecteur ne les supprime pas.
- **Vérifié qu'ils rougissent réellement** : le correctif 8B a été temporairement annulé, deux tests
  sont tombés, puis le correctif restauré. Un test de non-régression qu'on n'a pas vu échouer ne
  prouve rien.
- Audit des autres consommateurs partagés : `count_critical_open_findings` (endpoint « status » du
  tenant) interroge le modèle directement sans passer par `list_findings` — son périmètre est
  épinglé lui aussi, pour qu'il reste un choix visible et non un effet de bord.

**Tâche 1 — UX de la révélation**
- Message explicite « Vérification de votre identité… » pendant les ~1,5 s de PBKDF2, bouton
  désactivé, garde anti-double-soumission côté handler (pas seulement `disabled` sur le bouton).
  Vérifié en navigateur : plus rien ne paraît figé.

**Tâche 2 — corrélation « réutilisation possible » (ADR-017)**
- Module `correlation.py`, entièrement déterministe. Deux signaux : même identifiant dans plusieurs
  fuites ; adresse professionnelle d'un membre retrouvée dans la fuite d'un service externe.
- **Vocabulaire imposé et vérifié mécaniquement** : « possible », « à vérifier », « pourrait » ;
  jamais « confirmée », « compromis », « avéré ». Une classe de tests refuse le vocabulaire interdit
  et exige une formulation d'hypothèse. Une règle de rédaction qui ne repose que sur la vigilance
  humaine finit toujours par céder.
- Normalisation d'identifiant volontairement prudente (casse + espaces, rien de plus) : fusionner
  les points de la partie locale ou les suffixes `+…` lierait des comptes réellement distincts.
  **Le coût d'un faux positif est ici très supérieur à celui d'un faux négatif.**
- Le croisement n'utilise que des identifiants en clair — un identifiant masqué est ambigu par
  construction, s'en servir comme clé fabriquerait des liens faux.
- C'est là que la révélation prend son sens : quand une corrélation porte sur une fuite au mot de
  passe disponible, l'action recommandée propose de le révéler pour trancher, en rappelant que
  l'accès est tracé.

**Tâche 3 — purge planifiée (ADR-014 §4)**
- Tâche Celery Beat quotidienne : au-delà de `BREACH_SECRET_RETENTION_DAYS` (90), le secret chiffré
  est effacé, `has_secret` repasse à False, `secret_purged_at` est horodaté. **On purge le secret,
  pas la fuite** — l'historique de conformité reste, et l'interface affiche « mot de passe effacé
  le … » plutôt que de laisser croire qu'il n'y en a jamais eu.
- Chaque exécution tracée (`SecretPurgeRun` : volumes, horodatage, jamais de secret), visible au
  back-office plateforme.
- **Rétentions tranchées explicitement** : journal des révélations conservé 365 j, soit plus
  longtemps que les secrets — c'est une piste d'audit, sa valeur est de survivre à la donnée
  qu'elle protège. Cassettes de test : hors périmètre, elles ne contiennent aucun secret (masquées
  à l'enregistrement) ; les soumettre à une rétention laisserait croire l'inverse.
- Politique lisible par le client sur la page Exposition — une promesse de conservation limitée
  n'est crédible que si elle figure dans le produit, pas seulement dans un contrat.

**Tâche 4 — rotation de clé (ADR-014 §5)**
- `BREACH_SECRET_ENCRYPTION_KEYS` : liste ordonnée, MultiFernet (la première chiffre, toutes
  déchiffrent). Rotation sans coupure ; l'ancien réglage à clé unique reste accepté en repli.
- Commande `rotate_breach_secret_key` (idempotente, `--dry-run`, sûre à interrompre). Un secret
  qu'aucune clé n'ouvre est **signalé et laissé intact** : l'effacer détruirait une donnée qu'une
  clé retrouvée plus tard pourrait encore lire.
- Procédure d'exploitation en quatre étapes documentée dans le README de l'app.

**Tâche 5 — ADR-014 réécrit**
- Le document décrit désormais le cycle de vie d'un bout à l'autre (chiffré → révélable → purgé →
  clé rotable) et se lit sans reconstituer la chronologie. L'historique des revirements est conservé
  en fin de document, pour la traçabilité des décisions.

**Seed** : le tenant Durand reçoit le cas de réutilisation mis en scène (l'adresse de Marie Durand
apparaît à la fois dans un log de malware et dans la fuite d'un service externe, sur une fuite qui
porte un mot de passe récupérable — les deux signaux et la révélation s'enchaînent) et une fuite
ancienne dont le secret est purgé. La purge de démo passe par le **vrai** service, pas par une
manipulation d'état : la démo montre un état réel.

### Décisions
- **Vocabulaire de la corrélation vérifié par les tests**, pas seulement par relecture. Un produit
  qui laisserait croire qu'il a testé un identifiant mentirait sur ce qu'il fait.
- **Purger le secret, jamais la fuite** : supprimer le finding ferait perdre l'historique de
  conformité, qui est exactement ce qu'un tenant doit pouvoir présenter.
- **Journal des révélations conservé plus longtemps que les secrets** : c'est une piste d'audit.
- **Cassettes hors périmètre de rétention**, décidé explicitement plutôt que par omission.
- **Prudence sur la normalisation des identifiants** : arbitrage assumé en faveur des faux négatifs.

### Difficultés rencontrées et solutions
- **Un test de corrélation a révélé un vrai défaut du normaliseur** : la reconnaissance d'un membre
  du tenant comparait `identifier.lower()` à des emails eux-mêmes minusculés, mais sans retirer les
  espaces de bord. Un payload fournisseur arrivant avec une espace parasite masquait donc à tort
  l'adresse d'un membre — le tenant perdait la capacité d'agir directement dessus (ADR-014 §4).
  Corrigé en normalisant des deux côtés. Le test avait été écrit pour la corrélation ; il a trouvé
  un bug une couche plus bas.
- **Exception de librairie qui fuitait à travers une frontière de module** : `rotate_secret_ciphertext`
  laissait remonter `cryptography.fernet.InvalidToken`, alors que la commande de rotation attrapait
  `ThreatIntelligenceError` — le cas « secret illisible avec les clés actuelles » faisait donc
  planter toute la rotation au lieu d'être signalé et ignoré. Corrigé en traduisant l'exception
  comme le fait déjà `decrypt_secret` : l'appelant n'a pas à connaître `cryptography` pour
  distinguer une donnée illisible d'une panne.
- **Assertion Playwright sur la mauvaise carte** : le scénario cliquait « Voir le détail » sur la
  première carte — laquelle est dépliée d'office, le clic la repliait donc — alors que la fuite
  corrélée à révéler est sur la carte suivante. Corrigé en ciblant la carte par son contenu
  (`boutique-loisirs.example`) plutôt que par sa position. La fonctionnalité était correcte.
- **La purge de démo efface plus que la fuite prévue** : quatre secrets seedés dépassent 90 jours,
  pas seulement celui de 2019. Constaté puis **conservé tel quel** : c'est le comportement réel de
  la politique, et une démo qui montre la rétention réellement à l'œuvre vaut mieux qu'une mise en
  scène calibrée. Le cas de réutilisation à révéler (58 jours) reste intact, ce qui était la
  contrainte à respecter.

### Vérification
- 690 tests backend verts (51 nouveaux : épinglage de périmètre, corrélation et ses faux positifs,
  purge et son idempotence, rotation et rejouabilité), hors les 3 tests PDF WeasyPrint pré-existants.
  `ruff` propre, lint frontend propre.
- Scénario de démonstration déroulé en navigateur réel : Exposition → section « Réutilisation
  possible — à vérifier » avec les deux signaux → dépliage de l'actif corrélé → révélation avec état
  de chargement explicite → fuite au mot de passe purgé → politique de rétention lisible.

### Reste à faire (sessions suivantes)
- **Corrélation inter-tenant impossible par construction** (et c'est voulu) : deux entreprises
  partageant un prestataire compromis ne se le signalent pas mutuellement. Un signal agrégé
  anonymisé côté plateforme serait utile mais soulève une question RGPD à trancher en ADR.
- **Détection de réutilisation nécessairement incomplète** : un même mot de passe sous deux adresses
  différentes échappe au croisement. C'est le cas que seul un test d'identifiant révélerait — refusé
  par principe (ADR-010/017). Ne jamais laisser croire qu'une absence de signal vaut absence de
  réutilisation.
- **Suite Vitest** toujours absente ; **smoke test licence réelle** toujours à faire.

---

## 2026-08-13 — Phase 8D : tests frontend, préparation au déploiement, hygiène du dépôt

### Contexte
Trois objectifs : combler l'absence de suite de tests frontend (prévue par CLAUDE.md, jamais mise
en place), déployer en production, et préparer le dépôt et la démonstration pour un regard
extérieur.

### Constat bloquant sur le déploiement (tâche 2)
`rssiasservice.online` résout vers `194.126.193.53` et sert **la page de parking par défaut de
LWS** : aucune instance n'est déployée, aucun VPS n'est provisionné, et je n'ai ni clé SSH ni accès
d'hébergement. Le déploiement lui-même, les vérifications Celery en production, le webhook
Breachsense de bout en bout et le seed du tenant de démo en production **n'ont donc pas été faits**
— et ne pouvaient pas l'être depuis cet environnement.

Ce qui a été livré à la place, et qui couvre la partie « code » de la tâche :
- **Garde-fou de configuration** (`config/startup_checks.py`) : refuse le démarrage si une clé
  Fernet est absente, invalide ou **réutilisée d'un usage à l'autre**. Validé à l'import des
  settings et non via les *system checks* Django, seul moyen de garantir que Gunicorn ne serve
  rien : un serveur WSGI n'exécute pas les system checks. Vérifié réellement dans les deux sens
  (trois clés identiques → refus explicite listant les deux collisions ; trois clés distinctes →
  `System check identified no issues`).
- **`BREACHSENSE_MODE` en production : `live`, explicite.** Un mode `replay` en production servirait
  des données fictives à des clients payants — pire qu'une panne, qui elle se voit. Le choix est
  posé dans `settings_production.py` avec ses trois garde-fous (mode explicite plutôt qu'`auto`,
  marge de sécurité du quota, cooldown par tenant).
- **`docs/deployment_runbook.md`** : la procédure complète, chaque étape se terminant par une
  vérification observable (certificat, files Celery réellement consommées, webhook de bout en bout,
  seed de démo, contrôles de sécurité finaux), plus un tableau de diagnostic.

### Réalisé — suite Vitest (tâche 1)
Vitest + Testing Library, job CI dédié et bloquant (`frontend-unit`), 37 tests sur les endroits où
une régression serait silencieuse et coûteuse : modale de révélation (état de chargement, garde
anti-double-soumission, **un seul appel réseau sur identifiants refusés** — la régression 401 de la
Phase 7 est désormais verrouillée par un test), masquage automatique du secret à 30 s, carte Radar
(actions, mode historique, état vide), rendu du score et de ses composantes, finding au secret
purgé, vocabulaire de corrélation non reformulé.

### Un vrai bug d'interface trouvé par le premier test écrit
Le premier test de saisie a échoué avec `password === "M"` : un seul caractère. Cause réelle —
`Modal` déclarait `onClose` dans les dépendances de son effet de mise au point. Or `onClose` est
presque toujours une fonction recréée à chaque rendu du parent : l'effet se relançait donc à
**chaque frappe**, et `dialogRef.current.focus()` volait le focus de l'input. **Toute saisie dans
n'importe quelle modale de l'application était cassée** — invisible jusque-là parce que les tests
Playwright utilisent `fill()`, qui écrit la valeur d'un coup au lieu de la taper caractère par
caractère. Corrigé par une ref sur `onClose`, l'effet ne dépendant plus que de `open`.

C'est l'argument le plus net en faveur des tests de composants : aucun test e2e existant ne pouvait
révéler ce défaut, et un utilisateur réel l'aurait rencontré au premier mot de passe saisi.

### Hygiène du dépôt (tâche 3)
Scan des 72 commits de l'historique complet (motifs : clés API, clés Fernet, clés AWS, jetons,
clés privées, mots de passe en dur). Résultats, sans divulgation de valeur :
- **1 vraie fuite, la mienne** : la clé `BREACH_SECRET_ENCRYPTION_KEY` du `.env` de développement
  avait été reprise telle quelle comme constante de test en Phase 8C, donc publiée. Portée limitée
  (clé de développement, protégeant des données de démonstration factices), mais réelle.
  **Traitée** : test réécrit pour générer ses clés à l'exécution — ce qui rend cette confusion
  structurellement impossible — puis rotation effective de la clé de développement via la commande
  `rotate_breach_secret_key` de la Phase 8C (11 secrets re-chiffrés, ancienne clé retirée,
  déchiffrement revérifié). La procédure de rotation a ainsi été exercée pour de vrai, sur des
  données réelles, et pas seulement en test.
- Le reste : mots de passe de tests, et une fausse clé AWS (`AKIADEMOFAKEKEY00000`) délibérément
  factice dans le seed de démonstration. Aucune action.
- `ANTHROPIC_API_KEY`, `DJANGO_SECRET_KEY`, `TOTP_ENCRYPTION_KEY`, `AI_PSEUDONYMIZATION_KEY` et la
  licence Breachsense : absentes du dépôt, `.gitignore` correct.

README racine réécrit pour un lecteur découvrant le projet : ce que fait le produit, les trois
différenciateurs, schéma d'architecture, état des tests, table des ADR. Au passage, une affirmation
devenue **fausse** a été corrigée : le README promettait encore qu'aucun secret de fuite n'est
jamais stocké, alors qu'ADR-014 a été révisé en Phase 8 (chiffré, révélable sous conditions, purgé).

### Kit de démonstration (tâche 4)
`docs/demo_runbook.md` : 8 étapes minutées, avec pour chacune ce qu'on montre et ce qu'on dit, la
remise à zéro entre deux démos, un tableau « si ça casse en direct », et une section **« ce qu'il ne
faut pas promettre »** (webhook temps réel jamais validé en réel, volumes de détection, envoi
d'emails en production).

Chronométrage réel du parcours complet (Playwright, en local) : **24 s** de temps machine pour les
8 étapes. Le budget de 12 minutes est donc presque entièrement du temps de parole, très en deçà des
15 minutes demandées. **Non rejoué sur le VPS**, faute de déploiement.

### Un second vrai défaut, trouvé en conditions réelles
Après la rotation de clé, la révélation renvoyait une **500 brute** : le conteneur tournait encore
avec la clé d'avant rotation. La cause immédiate était un simple redémarrage manquant, mais elle a
exposé un vrai manque : un secret présent mais illisible (rotation sans re-chiffrement, ancienne clé
retirée trop tôt, donnée corrompue) faisait planter l'endpoint au lieu de répondre proprement.
Corrigé — 503 avec un message compréhensible, erreur journalisée côté serveur, et la tentative reste
tracée dans le journal d'audit (c'est un accès refusé, pas un non-événement). Trois tests ajoutés.

### Difficultés
- **Minuteurs et Testing Library** : `waitFor` sonde sur l'horloge réelle et se bloque sous horloge
  figée. Résolu avec `vi.useFakeTimers({ shouldAdvanceTime: true })`, documenté dans le README
  frontend pour le prochain test qui touchera au compte à rebours.
- **« Fermer » est ambigu** dans une modale (arrière-plan, croix, bouton de pied portent tous ce
  libellé) — déjà rencontré côté Playwright, reconfirmé côté Vitest.
- **Serveur Vite en état de rechargement à chaud incohérent** après édition de `vite.config.js` :
  page bloquée sur ses squelettes alors que l'API répondait en 0,19 s. Même réflexe que les fois
  précédentes (mesurer l'API avant de suspecter le code, puis redémarrer proprement).
- **Redirection de port Docker instable** après `restart` : port en écoute mais réponse vide, et
  `localhost` résolvant vers un écouteur IPv6 périmé. Résolu par `up -d --force-recreate web`.

### Vérification
- Backend : **713 tests verts** (hors les 3 tests PDF WeasyPrint, limite d'environnement Windows).
  `ruff` propre.
- Frontend : **37 tests Vitest verts**, lint propre (2 avertissements pré-existants).
- Parcours de démonstration complet rejoué en navigateur réel, vert, chronométré.
- Garde-fou de production vérifié dans ses deux cas (refus et acceptation).

### Reste à faire
- **Le déploiement lui-même** — provisionner un VPS, faire pointer le DNS, puis dérouler
  `docs/deployment_runbook.md`. Tout le reste de la tâche 2 (Celery en production, webhook réel,
  seed de démo en production, vérification des variables d'environnement) en dépend.
- **Rejouer le chronométrage de la démo sur le VPS**, la latence réseau n'étant pas représentée en
  local.
- **Purge planifiée, licence réelle, pondération du score par type d'actif** : reste-à-faire
  inchangés des phases précédentes.
