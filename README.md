# RSSI as a Service

Plateforme SaaS multi-tenant de conformité et de surveillance cybersécurité pour TPE/PME
françaises. Voir [`docs/cadrage_rssi_as_a_service.md`](docs/cadrage_rssi_as_a_service.md) pour le
cadrage complet du projet et [`CLAUDE.md`](CLAUDE.md) pour les règles d'architecture et de
conventions.

**État actuel (Phase 1 — socle)** : structure du monorepo, authentification JWT, multi-tenancy
(`Tenant` / `Membership`), RBAC (admin / contributeur / lecteur), CI. Le diagnostic ANSSI, le plan
d'action, la surveillance et l'IA arrivent dans les phases suivantes (voir §11 du cadrage).

## Structure du dépôt

```
backend/     Django 5 + DRF (apps : accounts, tenants, platform_admin)
frontend/    React 18 + Vite + Tailwind CSS
docs/        Documentation vivante (cadrage, ADR, journal)
docker-compose.yml
```

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

2. Lancer la stack :
   ```bash
   docker compose up --build
   ```
   Le service `web` attend que Postgres et Redis soient prêts, applique les migrations, puis
   démarre le serveur de développement Django sur http://localhost:8000.

3. Créer un compte administrateur Django (optionnel, pour `/admin/`) :
   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

L'API est servie sous `/api/v1/`, la santé du service sous `/healthz`, et le schéma OpenAPI
(Swagger) sous `/api/v1/schema/swagger-ui/`.

> Le service Postgres est exposé sur le port **5433** de l'hôte (et non 5432) pour éviter tout
> conflit avec une instance PostgreSQL locale déjà installée. Redis reste sur le port standard
> 6379.

## Démarrage du frontend

```bash
cd frontend
npm install
npm run dev
```
Le frontend démarre sur http://localhost:5173 et cible l'API sur http://localhost:8000 (CORS
déjà configuré côté backend pour cette origine).

## Développement backend sans Docker (optionnel)

Utile pour lancer `pytest`/`manage.py` directement, en pointant vers le Postgres/Redis exposés
par `docker compose up -d postgres redis` :

```bash
cd backend
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate      # macOS/Linux
pip install -r requirements-dev.txt

python manage.py migrate
python manage.py runserver
```

`backend/.env` doit alors pointer `DATABASE_URL`/`REDIS_URL` vers `localhost` (voir les
commentaires dans `backend/.env.example`), pas vers les noms de service Docker.

## Tests, lint et qualité

```bash
cd backend
pytest                              # suite de tests (dont les tests d'étanchéité multi-tenant)
pytest --cov=apps --cov-report=term-missing
ruff check .                        # lint
ruff format .                       # formatage
```

```bash
cd frontend
npm run lint
npm run build
```

La CI GitHub Actions (`.github/workflows/ci.yml`) exécute lint puis tests pour le backend
(avec Postgres/Redis en services) et lint puis build pour le frontend, à chaque push et pull
request sur `main`.

## Comptes et authentification

- `POST /api/v1/auth/register/` : crée un compte et l'espace entreprise (tenant) associé, avec
  l'utilisateur comme administrateur de ce tenant.
- `POST /api/v1/auth/token/`, `POST /api/v1/auth/token/refresh/` : JWT (accès 15 min, refresh
  7 jours, rotation + blacklist des refresh tokens à chaque utilisation).
- `GET /api/v1/auth/me/` : profil de l'utilisateur connecté et liste de ses entreprises.
- `GET /api/v1/tenants/` : entreprises de l'utilisateur connecté (pour un sélecteur de tenant).
- `GET /api/v1/tenants/members/` : membres de l'entreprise sélectionnée — nécessite l'en-tête
  `X-Tenant-Id: <uuid du tenant>`.

Le multi-tenant est appliqué par un middleware (`apps.tenants.middleware.TenantScopingMiddleware`)
qui résout le tenant depuis l'en-tête `X-Tenant-Id` et l'appartenance de l'utilisateur, puis par
un manager (`TenantScopedManager`) qui échoue fermé : sans tenant résolu dans le contexte de la
requête, aucune ligne n'est renvoyée.
