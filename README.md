# RSSI as a Service

Plateforme SaaS de conformité et de surveillance cybersécurité pour les TPE/PME françaises, qui
n'ont ni RSSI ni budget pour en recruter un.

Le produit répond à une question que ces entreprises se posent sans pouvoir y répondre seules :
**« sommes-nous exposés, et par quoi devons-nous commencer ? »** Il combine un diagnostic de
maturité (référentiel ANSSI, 42 mesures), un plan d'action priorisé, la surveillance continue des
actifs déclarés (disponibilité, TLS, en-têtes, SPF/DMARC), la détection de fuites de données,
et une assistance par IA.

## Ce qui le distingue

**1. Des signaux avant-coureurs, pas seulement des constats.** Un domaine ressemblant au vôtre
vient d'être déposé, votre nom circule sur un forum : ces signaux arrivent *avant* l'incident et
sont présentés séparément des fuites avérées, avec un ton distinct (« nous surveillons » plutôt que
« vous avez fuité »).

**2. Une vulgarisation écrite pour un dirigeant, pas pour un analyste.** Chaque élément détecté
s'accompagne de ce que ça veut dire et de l'action à mener, en français courant. Exemple, pour un
cookie de session volé : *« c'est le jeton que votre navigateur garde après une connexion réussie ;
avec lui, un attaquant entre dans le compte sans avoir besoin du mot de passe ni du code de double
authentification. »* Ces textes sont déterministes (aucun appel IA) : ils s'affichent
instantanément et ne dépendent d'aucun fournisseur.

**3. Une corrélation de réutilisation possible.** Le même identifiant apparaissant dans plusieurs
fuites, ou une adresse professionnelle retrouvée dans la fuite d'un service externe, sont signalés
comme **hypothèses à vérifier** — jamais comme des faits. La plateforme ne teste aucun identifiant
nulle part et n'affirme donc jamais qu'un accès est compromis ; le vocabulaire employé
(« réutilisation possible », « à vérifier ») est contraint dans le code et vérifié par les tests.

## Architecture

```
                    ┌──────────────────────────────────────────┐
   navigateur ──────▶  Caddy  (TLS Let's Encrypt, en-têtes)     │
                    └───────┬─────────────────────┬────────────┘
                            │ /api/*              │ /*
                            ▼                     ▼
                    ┌───────────────┐     ┌─────────────────┐
                    │ Django + DRF  │     │  SPA React/Vite │
                    │  (Gunicorn)   │     │   (statique)    │
                    └───┬───────┬───┘     └─────────────────┘
                        │       │
              ┌─────────┘       └──────────┐
              ▼                            ▼
      ┌──────────────┐            ┌──────────────────┐
      │ PostgreSQL   │            │ Redis            │
      │ (multi-tenant│            │ cache, broker,   │
      │  schéma      │            │ rate limiting    │
      │  partagé)    │            └────────┬─────────┘
      └──────────────┘                     │
                                           ▼
                          ┌────────────────────────────────┐
                          │ Celery — 3 files séparées       │
                          │  ai · monitoring · emails       │
                          │  + Beat (planification)         │
                          └───┬──────────────┬──────────────┘
                              ▼              ▼
                       API Anthropic   API Breachsense
                    (pseudonymisée,    (licence partagée,
                     ADR-005)           throttlée, ADR-013)
```

**Règles structurantes** (détail dans [`CLAUDE.md`](CLAUDE.md)) : une app Django par domaine
métier, aucune app n'important les modèles d'une autre ; toute table métier porte un `tenant_id`
avec un manager qui **échoue fermé** ; aucun appel réseau (IA, checks, emails) dans le cycle
requête/réponse HTTP.

## État du projet

Phases 1 à 8C livrées : socle (JWT + 2FA, multi-tenancy, RBAC), diagnostic ANSSI et plan d'action,
surveillance d'actifs et météo cyber quotidienne, IA documentaire et assistant, durcissement
sécurité, renseignement sur la menace (Breachsense), radar pré-incident, fil d'exposition priorisé,
corrélation de réutilisation, cycle de vie complet des secrets.

**Non déployé à ce jour.** Le domaine `rssiasservice.online` sert encore la page par défaut du
registrar ; la procédure de mise en production est écrite et prête à exécuter dans
[`docs/deployment_runbook.md`](docs/deployment_runbook.md). Le webhook Breachsense entrant, qui
requiert une URL publique, n'a donc pas encore été validé en conditions réelles.

### Tests

| Suite | Volume | Portée |
|---|---|---|
| `pytest` (backend) | ~700 | Logique métier, API, étanchéité multi-tenant, propriétés de sécurité |
| `vitest` (frontend) | 37 | Composants critiques (révélation de secret, radar, score) |
| `playwright` (e2e) | 5 parcours | Parcours réels contre la stack Docker + balayage d'accessibilité |

Trois tests d'export PDF échouent hors conteneur (bibliothèques système WeasyPrint absentes sous
Windows) ; ils passent en CI et dans le conteneur `web`.

La CI GitHub Actions exécute à chaque push et PR : lint + tests + audit de dépendances (backend),
lint + build + audit (frontend), tests de composants Vitest, suite Playwright complète, et scan
Trivy de l'image backend. Tous ces jobs sont bloquants.

### Décisions d'architecture

Toute décision structurante est consignée dans un ADR ([`docs/adr/`](docs/adr/)). Les plus
importantes pour comprendre le produit :

| ADR | Sujet |
|---|---|
| [005](docs/adr/005-pseudonymisation-avant-appel-ia.md) | Pseudonymisation systématique avant tout appel IA |
| [007](docs/adr/007-docker-compose-vps-caddy.md) | Docker / VPS / Caddy |
| [013](docs/adr/013-integration-breachsense-cti.md) | Intégration Breachsense (licence partagée) |
| [014](docs/adr/014-secret-handling-breach-data.md) | **Cycle de vie des secrets de fuite** : chiffrés, révélables sous conditions, purgés, clé rotable |
| [015](docs/adr/015-modes-cti-cassettes-rejouables.md) | Modes CTI et cassettes (démo sans appel réel) |
| [016](docs/adr/016-score-exposition-explicable.md) | Score d'exposition déterministe et explicable |
| [017](docs/adr/017-correlation-reutilisation-possible.md) | Corrélation de réutilisation (vocabulaire contraint) |

Le [journal de bord](docs/journal.md) consigne chaque session : ce qui a été fait, les décisions,
les difficultés rencontrées et leurs solutions. La [revue de sécurité](docs/security_review.md)
couvre l'OWASP Top 10:2021, mesures en place et risques résiduels acceptés.

---

## Démarrage rapide (Docker — recommandé)

Prérequis : Docker Desktop.

1. Copier les fichiers d'environnement :
   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   ```
   Renseigner un `POSTGRES_PASSWORD` (dans `.env`) et le même mot de passe dans le
   `DATABASE_URL` de `backend/.env`, ainsi qu'un `DJANGO_SECRET_KEY` unique (générable avec
   `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`).

   Générer aussi les **trois clés Fernet distinctes** (`AI_PSEUDONYMIZATION_KEY`,
   `TOTP_ENCRYPTION_KEY`, `BREACH_SECRET_ENCRYPTION_KEY`) — chacune protège un usage différent, et
   la production refuse de démarrer si l'une est absente ou réutilisée :
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. Lancer la stack :
   ```bash
   docker compose up --build
   ```
   Le service `web` attend Postgres et Redis, applique les migrations, puis démarre Django sur
   http://localhost:8000. `worker` et `beat` démarrent les files Celery (`ai`, `monitoring`,
   `emails`) : les checks de surveillance, l'IA et la météo quotidienne n'avancent pas sans eux.

3. Charger le référentiel ANSSI (nécessaire au diagnostic) :
   ```bash
   docker compose exec web python manage.py load_anssi_referential
   ```

4. Optionnel — peupler le tenant de démonstration :
   ```bash
   docker compose exec web python manage.py seed_demo_tenant --reset
   ```

L'API est servie sous `/api/v1/`, la santé sous `/healthz`, le schéma OpenAPI sous
`/api/v1/schema/swagger-ui/`.

> Postgres est exposé sur le port **5433** de l'hôte (pas 5432) pour éviter un conflit avec une
> instance locale. Redis reste sur 6379.

## Démarrage du frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173
```

## Développement backend sans Docker (optionnel)

Utile pour lancer `pytest`/`manage.py` directement, contre le Postgres/Redis exposés par
`docker compose up -d postgres redis` :

```bash
cd backend
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate      # macOS/Linux
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver
```

`backend/.env` doit alors pointer `DATABASE_URL`/`REDIS_URL` vers `localhost`.

## Tests, lint et qualité

```bash
cd backend
pytest                              # suite complète (dont étanchéité multi-tenant)
pytest --cov=apps --cov-report=term-missing
ruff check . && ruff format .
pip-audit -r requirements.txt
```

```bash
cd frontend
npm test                            # composants (Vitest) — voir frontend/README.md
npm run lint
npm run build
npm run audit
```

### Tests de bout en bout (Playwright)

```bash
docker compose up -d postgres redis web worker beat
docker compose exec web python manage.py load_anssi_referential

cd frontend
npm run test:e2e
```

## Comptes et authentification

- `POST /api/v1/auth/register/` : crée un compte et l'espace entreprise (tenant) associé, avec
  l'utilisateur comme administrateur.
- `POST /api/v1/auth/token/`, `/token/refresh/` : JWT (accès 15 min, refresh 7 jours, rotation +
  blacklist). Si la 2FA est activée, `token/` renvoie un challenge à usage unique — voir
  `POST /api/v1/auth/token/verify-2fa/`.
- `/auth/2fa/setup/`, `/2fa/confirm/`, `/2fa/disable/` : enrôlement TOTP (QR code + codes de
  récupération).
- `GET /api/v1/auth/me/`, `GET /api/v1/tenants/`, `GET /api/v1/tenants/members/` (en-tête
  `X-Tenant-Id: <uuid>` requis pour les ressources tenant-scopées).

Le multi-tenant est appliqué par un middleware qui résout le tenant depuis `X-Tenant-Id` et
l'appartenance réelle de l'utilisateur, puis par un manager qui **échoue fermé** : sans tenant
résolu, aucune ligne n'est renvoyée.

## Renseignement sur la menace (Breachsense)

Détection de fuites sur les actifs déclarés, via une licence **partagée par toute la plateforme**
(palier Essentials : 1000 requêtes/mois, 15 actifs monitorés, 1 req/s) — ADR-013.

- `BREACHSENSE_MODE` : `live` (appels réels), `replay` (cassettes enregistrées, aucun appel
  réseau), `null` (provider neutre), ou `auto`. La production est en `live` explicite ; le
  développement et la CI n'appellent jamais l'API réelle (ADR-015).
- **Webhook** : `POST /api/v1/webhooks/breachsense` (Basic Auth, temps constant, idempotent).
  Requiert une URL publique, donc non validé avant déploiement. Le pipeline complet reste
  vérifiable sans licence :
  ```bash
  docker compose exec web python manage.py simulate_breach_finding \
    --tenant-slug <slug> --asset-value <actif déclaré>
  ```

### Traitement des secrets de fuite

Point le plus sensible du produit, entièrement décrit par [ADR-014](docs/adr/014-secret-handling-breach-data.md) :

1. **Chiffré à l'ingestion** (Fernet, clé dédiée) — jamais écrit en clair, jamais journalisé.
2. **Révélable** par un administrateur du tenant, sous conditions cumulatives : ré-authentification
   fraîche à chaque accès (mot de passe ou code TOTP), étanchéité tenant stricte, rate limiting
   serré, et traçabilité intégrale de chaque tentative — accordée comme refusée.
3. **Purgé** automatiquement au-delà du délai de conservation : seule la valeur récupérable
   disparaît, l'historique de la fuite est conservé.
4. **Clé rotable** sans coupure (MultiFernet + commande de rotation idempotente).

## Sécurité

Revue complète (OWASP Top 10:2021) : [`docs/security_review.md`](docs/security_review.md).

- **Authentification** : JWT courts + rotation, 2FA TOTP, verrouillage progressif par compte et IP,
  politique de mot de passe (≥12 caractères + liste de mots de passe compromis), messages non
  énumérants.
- **Rate limiting** : par IP sur l'authentification, par tenant sur le reste, et seuil dédié plus
  strict sur la révélation de secret.
- **Multi-tenant** : défense en profondeur à trois niveaux (middleware, manager fail-closed,
  permissions DRF explicites), avec un test d'étanchéité par ressource exposée.
- **IA** : pseudonymisation systématique avant tout appel externe (ADR-005), vérifiée par un test
  de propriété qui inspecte le payload réellement transmis.
- **Clés de chiffrement** : une par usage, jamais partagées. La configuration de production est
  validée au démarrage — clé manquante, invalide ou réutilisée empêche le boot.
- **Chaîne d'approvisionnement** : `pip-audit`, `npm audit` (liste blanche documentée), scan Trivy,
  en CI à chaque push/PR.
- **Aucun secret committé** : `.env` gitignorés, `.env.example` sans valeurs réelles.

Pour signaler une vulnérabilité, contacter le mainteneur directement plutôt que d'ouvrir une issue
publique.
