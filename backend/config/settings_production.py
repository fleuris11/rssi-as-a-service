"""Production overlay (cadrage §6, Phase 5). ``config.settings`` stays the
base module (dev-friendly defaults, e.g. DEBUG driven by an env var) — this
module is what production actually points ``DJANGO_SETTINGS_MODULE`` at
(``deploy/Caddyfile`` and the production Compose file set it explicitly).
It only adds hardening that would get in the way locally (forced HTTPS,
secure cookies, strict ALLOWED_HOSTS) — nothing here changes application
behaviour, only the security posture around it.
"""

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
