# ADR 007 — Docker Compose sur VPS + Caddy

- **Statut** : Adopté
- **Date** : 2026-08-05
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

Le produit doit être déployé en production sur `rssiasservice.online`, opéré par une seule personne,
avec un budget d'infrastructure minimal (cadrage §9), tout en restant démontrable de bout en bout
pour le dossier Bloc 3 (« maîtrise complète de la chaîne » — valeur pédagogique explicite de la
certification). L'architecture est un monolithe modulaire (ADR-001) : un service web Django/Gunicorn,
des workers Celery (files `ai`/`monitoring`/`emails`), un beat scheduler, PostgreSQL, Redis, et un
frontend React statique — six à sept processus à orchestrer ensemble, avec TLS et des en-têtes de
sécurité devant la SPA et l'API.

## Options étudiées

1. **Kubernetes** (self-managed ou managé). Écarté : complexité opérationnelle et coût
   disproportionnés pour six-sept processus sur une infrastructure mono-nœud ; aucun besoin
   d'auto-scaling horizontal identifié pour la cible TPE/PME du MVP.
2. **PaaS** (Railway, Render, Fly.io). Écarté : simplifie l'opérationnel mais retire la valeur
   pédagogique Bloc 3 de « maîtriser la chaîne de déploiement » (réseau, TLS, reverse proxy, secrets),
   et introduit une dépendance à la tarification et aux garanties d'un tiers pour un produit dont le
   cadrage vise justement l'autonomie infrastructure.
3. **Docker Compose sur un VPS unique + Caddy en reverse proxy.**

## Décision

`docker-compose.yml` (dev) et `docker-compose.prod.yml` (production) orchestrent l'ensemble des
services sur un seul VPS : `postgres`, `redis`, `web` (Gunicorn), `worker` (Celery), `beat` (Celery
Beat), et `caddy`. Caddy (`deploy/Caddyfile`, servi par l'image construite via
`deploy/Dockerfile.caddy`) joue un double rôle :

1. **Reverse proxy applicatif** : sert les fichiers statiques buildés du frontend React (build
   multi-stage — étage `node:22-alpine` puis copie dans `caddy:2-alpine`, avec repli SPA
   `try_files {path} /index.html`) et route `/api/*` vers le service `web`.
2. **Terminaison TLS automatique** via Let's Encrypt (fonctionnalité native de Caddy — aucune
   configuration ACME manuelle), et émission des en-têtes de sécurité HTTP (HSTS, X-Frame-Options,
   X-Content-Type-Options, Referrer-Policy, CSP, Permissions-Policy — voir `deploy/Caddyfile` et
   `docs/security_review.md`, catégorie A05).

En production, `docker-compose.prod.yml` n'expose que les ports 80/443 du service `caddy` sur
l'hôte ; `postgres` et `redis` restent uniquement accessibles sur le réseau Docker interne. Le service
`web`/`worker`/`beat` charge `DJANGO_SETTINGS_MODULE=config.settings_production` (voir ADR séparé sur
le durcissement — `docs/security_review.md`), qui impose `DEBUG=False`, des cookies sécurisés et un
`ALLOWED_HOSTS` explicite.

## Conséquences

**Positives**
- Coût minimal : un seul VPS, pas de facturation par service séparé, cohérent avec le budget freelance
  du cadrage.
- Chaîne de déploiement entièrement maîtrisée et documentée (`docker-compose.prod.yml`,
  `deploy/Caddyfile`, `deploy/Dockerfile.caddy`) — exploitable directement comme preuve Bloc 3.
- TLS et en-têtes de sécurité gérés déclarativement dans un unique `Caddyfile`, versionné et revu comme
  n'importe quel autre fichier du dépôt (contrairement à une configuration cliquée dans une console
  PaaS).
- Le multi-stage build (`deploy/Dockerfile.caddy`) garantit que l'image de production ne contient
  jamais les sources ni les `node_modules` du frontend — seul le résultat du `npm run build` est
  copié dans l'image finale.

**Négatives / points de vigilance**
- Aucune haute disponibilité : un VPS unique est un point de défaillance unique. Acceptable pour la
  cible TPE/PME et le stade du projet ; documenté comme limite connue plutôt que masqué.
- Le scaling reste vertical (VPS plus gros) tant que le monolithe n'est pas éclaté — cohérence avec
  ADR-001.
- La rotation des certificats Let's Encrypt et la persistance de l'état ACME de Caddy dépendent des
  volumes Docker nommés `caddy_data`/`caddy_config` (`docker-compose.prod.yml`) : une perte de ces
  volumes sans sauvegarde entraînerait une nouvelle émission de certificat (dégradation temporaire,
  pas une perte de données métier) — à couvrir par le runbook de sauvegarde de la Phase 6.
