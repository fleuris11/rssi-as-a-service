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
