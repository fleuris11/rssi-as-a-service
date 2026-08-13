"""Production overlay (cadrage §6, Phase 5). ``config.settings`` stays the
base module (dev-friendly defaults, e.g. DEBUG driven by an env var) — this
module is what production actually points ``DJANGO_SETTINGS_MODULE`` at
(``deploy/Caddyfile`` and the production Compose file set it explicitly).
It only adds hardening that would get in the way locally (forced HTTPS,
secure cookies, strict ALLOWED_HOSTS) — nothing here changes application
behaviour, only the security posture around it.
"""

import sys

from .settings import *  # noqa: F401,F403 - production is "dev settings + hardening", not a fork

DEBUG = False

# No default: an empty/missing DJANGO_ALLOWED_HOSTS must fail loudly in
# production rather than silently falling back to localhost.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# --- En-têtes et cookies (cadrage §6) ---------------------------------------
#
# Caddy (deploy/Caddyfile) already sets HSTS/X-Frame-Options/nosniff/CSP at
# the edge — these are defense in depth for anything served directly by
# Django (the admin, DRF's browsable API if ever enabled), and for the
# handful of headers only Django itself can compute correctly (e.g.
# SECURE_PROXY_SSL_HEADER-aware redirects).
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # behind Caddy, cadrage §4.1
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31_536_000)  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# CORS : liste stricte (pas de wildcard) — l'origine de production doit être
# explicitement listée dans CORS_ALLOWED_ORIGINS (voir backend/.env.example).
CORS_ALLOW_ALL_ORIGINS = False

# --- Mode CTI en production (ADR-015, tranché en Phase 8D) ------------------
#
# La question : une plateforme en production doit-elle pouvoir appeler
# réellement l'API Breachsense ? Oui — c'est la fonction même du produit, et
# un mode "replay" en production servirait des données fictives à des clients
# payants, ce qui serait pire qu'une panne (une panne se voit).
#
# Mais "live" est le seul mode où une erreur coûte du quota réel et non
# reconstituable (1000 requêtes/mois pour TOUTE la plateforme, ADR-013), d'où
# trois garde-fous conservés, aucun n'étant nouveau — ils existent déjà et
# c'est ici qu'on acte qu'ils sont la condition du passage en live :
#   1. le mode est EXPLICITE en production (pas de "auto") : un déploiement
#      doit dire ce qu'il fait, et un `.env` incomplet ne doit pas basculer
#      silencieusement en live sous prétexte qu'une licence est présente ;
#   2. QuotaManager refuse toute requête sous la marge de sécurité
#      (BREACHSENSE_QUOTA_SAFETY_MARGIN), donc un emballement s'arrête avant
#      d'épuiser le mois ;
#   3. le cooldown par tenant (BREACHSENSE_SCAN_COOLDOWN_HOURS) borne ce
#      qu'un même client peut consommer à lui seul.
#
# Reste volontairement surchargeable : un environnement de préproduction
# pointant sur cette configuration doit pouvoir repasser en "replay".
BREACHSENSE_MODE = env("BREACHSENSE_MODE", default="live")

# --- Garde-fou de démarrage (Phase 8D) --------------------------------------
#
# Validé À L'IMPORT, donc avant que Gunicorn ne serve la moindre requête : une
# clé de chiffrement manquante, invalide ou réutilisée d'un usage à l'autre
# fait échouer le démarrage, au lieu de laisser tourner une production dont la
# séparation des clés (ADR-005/009/014) est silencieusement annulée.
#
# Les system checks de Django ne suffisent pas ici : un serveur WSGI ne les
# exécute pas. Le même contrôle reste disponible via `manage.py check`.
from .startup_checks import validate_production_settings  # noqa: E402

validate_production_settings(sys.modules[__name__])
