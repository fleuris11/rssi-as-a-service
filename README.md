# RSSI as a Service

Plateforme SaaS multi-tenant de conformité et de surveillance cybersécurité pour TPE/PME
françaises. Voir [`docs/cadrage_rssi_as_a_service.md`](docs/cadrage_rssi_as_a_service.md) pour le
cadrage complet du projet et [`CLAUDE.md`](CLAUDE.md) pour les règles d'architecture et de
conventions.

**État actuel (Phase 7 — renseignement sur la menace)** : socle (auth JWT + 2FA TOTP, multi-tenancy,
RBAC), diagnostic de maturité ANSSI et plan d'action, surveillance d'actifs avec météo cyber
quotidienne, génération documentaire et assistant par IA, durcissement sécurité/qualité/accessibilité
(rate limiting, verrouillage progressif, en-têtes de sécurité, chaîne d'approvisionnement, tests
E2E), et détection de compromissions (fuites de données/identifiants) via Breachsense (scan +
monitoring webhook, section « Compromissions »). Reste à faire avant la Phase 6/production :
déploiement effectif sur `rssiasservice.online` (le webhook Breachsense en particulier n'est
testable en conditions réelles qu'une fois une URL publique disponible — voir la section dédiée
ci-dessous). Voir §11 du cadrage pour le détail des phases et
[`docs/security_review.md`](docs/security_review.md) pour la revue de sécurité complète.

## Structure du dépôt

```
backend/     Django 5 + DRF (apps : accounts, tenants, assessments, actions, monitoring,
             ai_assistant, notifications, threat_intelligence, platform_admin)
frontend/    React 18 + Vite + Tailwind CSS
frontend/e2e/  Tests de bout en bout Playwright (parcours critiques + accessibilité)
deploy/      Caddyfile (reverse proxy + TLS + en-têtes de sécurité) et Dockerfile de production
docs/        Documentation vivante (cadrage, ADR, journal, revue de sécurité)
docker-compose.yml       Stack de développement (postgres, redis, web, worker, beat)
docker-compose.prod.yml  Stack de production (+ caddy, sans ports hôte sur postgres/redis)
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
   démarre le serveur de développement Django sur http://localhost:8000. `worker` et `beat`
   démarrent les files Celery séparées (`ai`, `monitoring`, `emails` — cadrage §4.4) : les checks
   de surveillance, l'IA et la météo cyber quotidienne n'avancent pas sans eux.

3. Créer un compte administrateur Django (optionnel, pour `/admin/`) :
   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

4. Charger le référentiel ANSSI (nécessaire pour le diagnostic de maturité) :
   ```bash
   docker compose exec web python manage.py load_anssi_referential
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
pip-audit -r requirements.txt       # audit des dépendances
```
> Les tests d'export PDF (`TestRenderDocumentPdf`, `test_export_pdf_returns_a_pdf_attachment`)
> nécessitent les bibliothèques système de WeasyPrint (Pango/Cairo/GDK-Pixbuf — voir
> `backend/Dockerfile`), absentes d'un environnement Windows nu. Ils s'exécutent dans le conteneur
> `web` (`docker compose exec web pytest -k pdf`) ou en CI.

```bash
cd frontend
npm run lint
npm run build
npm run audit                       # npm audit avec liste blanche des risques acceptés documentés
```

### Tests de bout en bout (Playwright)

```bash
docker compose up -d postgres redis web worker beat   # stack backend réelle
docker compose exec web python manage.py load_anssi_referential  # si pas déjà fait

cd frontend
npm run test:e2e                    # ou : npx playwright test
```
Les tests (`frontend/e2e/`) couvrent les 3 parcours critiques (inscription → diagnostic → plan
d'action ; déclaration d'actif → check simulé → alerte visible ; génération de charte IA (API
mockée) → relecture → validation) contre la vraie stack Docker Compose, plus un balayage
d'accessibilité (`@axe-core/playwright`) sur les pages principales.

La CI GitHub Actions (`.github/workflows/ci.yml`) exécute, à chaque push et pull request sur
`main` : lint + tests + audit de dépendances (backend), lint + build + audit de dépendances
(frontend), la suite Playwright complète contre la stack Docker Compose (job `e2e`), et un scan
Trivy de l'image backend (job `container-scan`).

## Comptes et authentification

- `POST /api/v1/auth/register/` : crée un compte et l'espace entreprise (tenant) associé, avec
  l'utilisateur comme administrateur de ce tenant.
- `POST /api/v1/auth/token/`, `POST /api/v1/auth/token/refresh/` : JWT (accès 15 min, refresh
  7 jours, rotation + blacklist des refresh tokens à chaque utilisation). Si la 2FA est activée,
  `token/` renvoie un jeton de challenge à usage unique plutôt que des jetons d'accès directement —
  voir `POST /api/v1/auth/token/verify-2fa/`.
- `GET/POST /api/v1/auth/2fa/setup/`, `/2fa/confirm/`, `/2fa/disable/` : enrôlement TOTP (QR code +
  codes de récupération), confirmation, désactivation sécurisée (US-1.3).
- `GET /api/v1/auth/me/` : profil de l'utilisateur connecté et liste de ses entreprises.
- `GET /api/v1/tenants/` : entreprises de l'utilisateur connecté (pour un sélecteur de tenant).
- `GET /api/v1/tenants/members/` : membres de l'entreprise sélectionnée — nécessite l'en-tête
  `X-Tenant-Id: <uuid du tenant>`.

Le multi-tenant est appliqué par un middleware (`apps.tenants.middleware.TenantScopingMiddleware`)
qui résout le tenant depuis l'en-tête `X-Tenant-Id` et l'appartenance de l'utilisateur, puis par
un manager (`TenantScopedManager`) qui échoue fermé : sans tenant résolu dans le contexte de la
requête, aucune ligne n'est renvoyée.

## Renseignement sur la menace (Breachsense)

Détection de compromissions (fuites de données/identifiants) sur les actifs déclarés, via une
licence Breachsense unique et **partagée par toute la plateforme** (palier Essentials : 1000
requêtes « query »/mois, 15 actifs monitorés en temps réel, 1 req/s) — voir ADR-013/ADR-014.

- `BREACHSENSE_LICENSE_KEY` (dans `backend/.env`) : sans elle, la plateforme bascule automatiquement
  sur un provider neutre (aucun appel réel, findings vides) — utile en dev/CI sans licence. Le reste
  de la configuration (`BREACHSENSE_QUOTA_SAFETY_MARGIN`, `BREACHSENSE_SCAN_COOLDOWN_HOURS`,
  `BREACHSENSE_MONITORED_ASSET_POOL_SIZE`, `BREACHSENSE_WEBHOOK_USERNAME`/`PASSWORD`,
  `BREACHSENSE_WEBHOOK_CALLBACK_URL`) est documentée dans `backend/.env.example`.
- **Webhook** : `POST /api/v1/webhooks/breachsense` (Basic Auth) reçoit les notifications temps réel
  de la licence. `BREACHSENSE_WEBHOOK_CALLBACK_URL` doit pointer vers une URL **publique** — non
  disponible en développement local, donc non testable en conditions réelles avant déploiement.
  D'ici là, le pipeline d'ingestion complet est vérifiable avec des payloads simulés reproduisant le
  format exact de la doc (`apps/threat_intelligence/tests/test_webhook.py`) et avec la commande de
  gestion `simulate_breach_finding` (mêmes chemins de code que la production, sans dépendre d'une
  licence réelle) :
  ```bash
  docker compose exec web python manage.py simulate_breach_finding \
    --tenant-slug <slug> --asset-value <url-ou-domaine-déclaré>
  ```
- Aucun secret renvoyé par Breachsense (mot de passe, token, cookie) n'est jamais stocké — masquage
  non réversible dès la normalisation (ADR-014), vérifié par un test de propriété dédié.

## Sécurité

Revue complète (OWASP Top 10:2021, mesures en place et risques résiduels acceptés) :
[`docs/security_review.md`](docs/security_review.md). Décisions d'architecture associées :
ADR-009 (JWT/RBAC/2FA), ADR-010 (surveillance passive uniquement), ADR-007 (Caddy/TLS/en-têtes),
ADR-008 (chaîne d'approvisionnement en CI) — voir [`docs/adr/`](docs/adr/).

Points clés :
- **Authentification** : JWT courts + rotation, 2FA TOTP optionnelle, verrouillage progressif par
  compte et IP après échecs répétés, politique de mot de passe (≥12 caractères + liste de mots de
  passe compromis courants), messages d'erreur non énumérants.
- **Rate limiting** : throttling DRF par IP sur les endpoints d'authentification et par tenant sur
  le reste de l'API (`apps/accounts/throttling.py`, `apps/tenants/throttling.py`).
- **Multi-tenant** : défense en profondeur à trois niveaux — middleware, manager fail-closed,
  permissions DRF explicites sur chaque vue (voir ci-dessus).
- **IA** : pseudonymisation systématique avant tout appel externe (ADR-005), clé de chiffrement
  dédiée et distincte de celle du 2FA.
- **Infrastructure** : `DEBUG=False` et cookies sécurisés en production
  (`backend/config/settings_production.py`), en-têtes de sécurité HTTP (HSTS, CSP, etc.) au niveau
  du reverse proxy (`deploy/Caddyfile`).
- **Chaîne d'approvisionnement** : `pip-audit`, `npm audit` (avec liste blanche documentée des
  risques acceptés) et scan Trivy de l'image backend, exécutés en CI à chaque push/PR.
- **Aucun secret n'est jamais committé** : `.env`/`backend/.env` sont gitignorés,
  `backend/.env.example` ne contient que des placeholders vides.
- **Renseignement sur la menace** : throttle Redis anti-429 sur la licence Breachsense partagée,
  webhook en Basic Auth (comparaison en temps constant) et idempotent, secrets de fuite jamais
  persistés (ADR-014).

Pour signaler une vulnérabilité, contacter le mainteneur du dépôt directement plutôt que d'ouvrir
une issue publique.
