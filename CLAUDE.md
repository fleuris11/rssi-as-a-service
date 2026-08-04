# CLAUDE.md — RSSI as a Service

## Ce qu'est ce projet
Plateforme SaaS multi-tenant de conformité et de surveillance cybersécurité pour TPE/PME françaises :
diagnostic de maturité (référentiel ANSSI 42 mesures), plan d'action kanban, génération documentaire
et assistant par IA (API Claude), surveillance continue d'actifs (uptime, SSL, headers, SPF/DKIM/DMARC)
avec « météo cyber » quotidienne par email.

**Finalité double** : produit réel déployé sur https://rssiasservice.online ET support de certification
RNCP38822 niveau 7 (Blocs 2, 3, 4). Conséquence : la qualité de la documentation, des tests et la
traçabilité des décisions comptent autant que le code. Le document de référence est
`docs/cadrage_rssi_as_a_service.md` — le lire avant toute décision structurante, s'y conformer.

## Stack imposée (ne pas dévier sans ADR)
- **Backend** : Python 3.12, Django 5 + Django REST Framework, monolithe modulaire
- **Frontend** : React 18 + Vite, JavaScript (pas de TypeScript pour l'instant), Tailwind CSS
- **Données** : PostgreSQL 16 (schéma partagé multi-tenant), Redis (cache, broker, rate limiting)
- **Asynchrone** : Celery + Celery Beat, files séparées : `ai`, `monitoring`, `emails`
- **IA** : API Anthropic — claude-haiku pour tâches courtes (météo, classification),
  claude-sonnet pour génération documentaire. JAMAIS d'appel IA dans le cycle requête HTTP.
- **Infra** : Docker Compose (web, worker, beat, postgres, redis, caddy), CI GitHub Actions, VPS

## Architecture — règles non négociables
1. **Apps Django par domaine** : `accounts`, `tenants`, `assessments`, `actions`, `monitoring`,
   `ai_assistant`, `notifications`, `platform_admin`. Une app n'importe JAMAIS les modèles d'une
   autre app directement : passer par les fonctions de `services.py` de l'app concernée.
2. **Multi-tenancy** : toute table métier porte `tenant_id`. Utiliser le manager `TenantScopedManager`
   et le middleware de scoping. Toute nouvelle ressource exposée par l'API DOIT avoir un test
   d'étanchéité (un tenant A ne peut pas lire/écrire les données d'un tenant B).
3. **Pipeline IA** : tout appel passe par `ai_assistant/services.py` → pseudonymisation
   (aucun nom d'entreprise, de personne, email, IP, domaine réel envoyé à l'API) → appel →
   ré-injection → journalisation (tenant, cas d'usage, tokens, coût). Aucun appel direct à
   l'API Anthropic ailleurs dans le code.
4. **Surveillance** : checks passifs uniquement (GET HTTP, lecture TLS, requêtes DNS publiques).
   Protection SSRF : résolution DNS validée contre les plages IP privées avant tout check.
   Un actif n'est vérifié que s'il est déclaré par le tenant.
5. **Sécurité** : JWT courts + refresh rotation, RBAC (permissions DRF sur chaque vue),
   rate limiting, secrets uniquement via variables d'environnement, en-têtes de sécurité via Caddy.
   Jamais de secret, de clé ou de .env commité.

## Conventions
- **Langue** : code, identifiants, commits en **anglais** ; UI, docstrings métier et documentation
  utilisateur en **français**.
- **Commits** : Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`).
  Petits commits atomiques.
- **Branches** : trunk-based — `main` protégée, branches courtes `feat/xxx`, PR avec CI verte.
- **Tests** : pytest + pytest-django. Tout nouveau service/endpoint arrive AVEC ses tests
  (unitaires + intégration). Couverture cible ≥ 80 % sur le cœur métier. Mocker l'API Anthropic
  et les checks réseau en test. Frontend : tests des composants critiques (Vitest).
- **Qualité** : ruff (lint+format), mypy sur les services critiques, eslint côté front.
  La CI doit rester verte : ne jamais merger avec des tests rouges.
- **API** : REST sous `/api/v1/`, schéma OpenAPI généré (drf-spectacular), pagination systématique.
- **Migrations** : rétro-compatibles (pattern expand/contract), jamais de perte de données.

## Documentation vivante (aussi importante que le code)
- `docs/adr/NNN-titre.md` : un ADR pour TOUTE décision structurante (format : Contexte →
  Options → Décision → Conséquences). En créer un nouveau plutôt que dévier silencieusement.
- `docs/journal.md` : à la fin de chaque session de travail, y consigner : date, ce qui a été fait,
  décisions prises, difficultés rencontrées et solutions, reste à faire. Ce journal alimente les
  dossiers de certification — être précis et factuel.
- `README.md` : instructions de démarrage local toujours à jour (`docker compose up` doit suffire).

## Green IT (exigence de certification, transversale Bloc 2/3)
Choisir systématiquement l'option sobre : Haiku par défaut (Sonnet seulement si nécessaire),
cache des réponses IA stables, quotas de tokens par tenant, rollups des séries temporelles,
périodicités de checks raisonnées, emails légers, budget de performance frontend.

## Pièges connus à éviter
- Ne pas mettre de logique métier dans les vues DRF ni dans les tasks Celery : elles orchestrent,
  les `services.py` contiennent la logique (testable isolément).
- Les tasks Celery doivent être idempotentes (clé d'idempotence) et retryables (backoff).
- Ne jamais stocker de données personnelles dans les logs ni les envoyer à Sentry.
- Alerte monitoring : confirmer un DOWN par 3 échecs consécutifs avant d'alerter (anti faux positifs).

## Phasage (résumé — détail dans docs/cadrage §11)
Phase 1 (socle : Docker, CI, auth, tenants, RBAC) → Phase 2 (diagnostic ANSSI, scoring, plan
d'action) → Phase 3 (surveillance + météo) → Phase 4 (IA documentaire + assistant) →
Phase 5 (durcissement) → Phase 6 (production).
Toujours livrer un état démontrable en fin de phase.
