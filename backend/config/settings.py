"""Django settings for the RSSI as a Service backend.

Configuration is environment-driven (12-factor style): every value that
differs between dev, CI and production is read from an environment
variable, never branched on in code. See ``backend/.env.example`` for the
variables expected locally and by docker-compose.
"""

from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "apps.accounts",
    "apps.tenants",
    "apps.assessments",
    "apps.actions",
    "apps.monitoring",
    "apps.notifications",
    "apps.ai_assistant",
    "apps.threat_intelligence",
    "apps.platform_admin",
    "apps.marketing",
    "apps.billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Must run after authentication so it can resolve request.user, and
    # wraps the whole view so the tenant context is reset afterwards.
    "apps.tenants.middleware.TenantScopingMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        # Cadrage §6 : on privilégie la longueur à la complexité imposée.
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
    }
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"])
# X-Tenant-Id (frontend/src/api/client.js) isn't in django-cors-headers'
# default allow-list — without this, the browser's CORS preflight silently
# blocks every tenant-scoped request client-side (no server-side trace at
# all, since the request never leaves the browser), while auth endpoints
# that don't send the header keep working. Found via real-browser E2E
# testing (Playwright), not by any Django-test-client-based test, because
# the Django test client never enforces CORS.
CORS_ALLOW_HEADERS = [*default_headers, "x-tenant-id"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Registered globally, but both silently no-op without a resolved tenant
    # (see apps.tenants.throttling) — pre-tenant endpoints (register/login/
    # refresh/2FA) opt into apps.accounts.throttling.AuthRateThrottle
    # explicitly instead (cadrage §6 : rate limiting Redis par IP et par
    # tenant).
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.tenants.throttling.TenantRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "auth": "10/min",
        "tenant": "300/min",
        "tenant_ai": "20/min",
        # ADR-014 (mise à jour) : révélation de secret de fuite — seuil
        # volontairement strict (bien en-deçà du rythme d'usage humain
        # normal), pour limiter l'extraction massive même via un compte
        # admin compromis. Deux clés indépendantes (utilisateur + IP) :
        # un attaquant qui changerait de compte reste bloqué par l'IP, un
        # attaquant multi-IP reste bloqué par le compte.
        "breach_secret_reveal_user": "5/min",
        "breach_secret_reveal_ip": "10/min",
        # Formulaire public de demande de démonstration : seuil bas, aucun
        # usage légitime ne consiste à le remplir plus de 3 fois par heure.
        "demo_request": "3/hour",
    },
}

# Accès courts + rotation des refresh tokens (CLAUDE.md §"Sécurité").
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "RSSI as a Service API",
    "DESCRIPTION": (
        "API de la plateforme de conformité et de surveillance cybersécurité pour TPE/PME."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Celery : jamais d'appel réseau (IA, checks, emails) dans le cycle
# requête/réponse HTTP (CLAUDE.md). Broker/backend sur un index Redis
# distinct du cache pour éviter toute collision de clés.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_DEFAULT_QUEUE = "default"
# Files séparées par domaine de charge (cadrage §4.4) : un fournisseur IA en
# incident (Phase 4) ne doit pas retarder l'envoi d'une alerte, et
# inversement un pic de checks ne doit pas retarder les emails.
CELERY_TASK_ROUTES = {
    "apps.monitoring.tasks.*": {"queue": "monitoring"},
    "apps.notifications.tasks.*": {"queue": "emails"},
    "apps.ai_assistant.tasks.*": {"queue": "ai"},
    # Le CTI est un sous-domaine de la surveillance (ADR-013), pas de l'IA —
    # partage la file "monitoring", pas "ai".
    "apps.threat_intelligence.tasks.*": {"queue": "monitoring"},
}
# Un worker tué en cours de tâche doit la relivrer plutôt que la perdre —
# les tasks sont conçues pour être idempotentes (voir apps.monitoring.tasks
# et apps.notifications.tasks) précisément pour rendre ceci sûr.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# --- Email : backend console en dev, SMTP configurable par variables
# d'environnement en préproduction/production.
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL", default="RSSI as a Service <no-reply@rssiasservice.online>"
)

# Base URL used to build links in emails (dashboard link in the weather
# email) — the frontend's own origin, not the API's.
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:5173")

# --- IA (Phase 4, CLAUDE.md règle d'architecture n°3) : tout appel passe
# exclusivement par apps.ai_assistant.services, jamais dans le cycle
# requête/réponse HTTP (toujours via Celery, file "ai").
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
# Clé Fernet (32 octets urlsafe-base64) chiffrant la table de correspondance
# de pseudonymisation (ADR-005) ; générer avec
# `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
# Jamais commitée en clair — voir backend/.env.example.
AI_PSEUDONYMIZATION_KEY = env("AI_PSEUDONYMIZATION_KEY", default="")
# Durée de vie courte (cadrage §7) : la table de correspondance est
# rafraîchie à chaque réutilisation (conversation en cours), donc cette
# valeur borne l'inactivité tolérée, pas la durée totale d'une conversation.
AI_PSEUDONYMIZATION_TTL_HOURS = env.int("AI_PSEUDONYMIZATION_TTL_HOURS", default=24)
# Quota mensuel de tokens par défaut, par tenant (Green IT, cadrage §8) —
# override possible par tenant via AIUsageQuota.monthly_token_limit.
AI_DEFAULT_MONTHLY_TOKEN_LIMIT = env.int("AI_DEFAULT_MONTHLY_TOKEN_LIMIT", default=200_000)

# --- Threat intelligence / Breachsense (Phase 7, ADR-013/014) --------------
#
# Licence Essentials, unique et partagée par toute la plateforme (pas par
# tenant) : 1000 requêtes "query"/mois, 15 actifs monitorés (webhook) max,
# 1 req/s soutenue (bursts 5). Vide (pas d'appel réel possible) fait
# retomber apps.threat_intelligence.providers.get_provider() sur le
# NullProvider — utile en dev/CI sans licence.
BREACHSENSE_LICENSE_KEY = env("BREACHSENSE_LICENSE_KEY", default="")
BREACHSENSE_BASE_URL = env("BREACHSENSE_BASE_URL", default="https://api.breachsense.com")
# Mode de fourniture des données CTI (Phase 8A, ADR-015) :
#   - "live"   : appels réels à l'API Breachsense (consomme le quota précieux
#                de 1000 req/mois partagé) — JAMAIS le défaut, à activer
#                explicitement (record_breachsense_cassette, smoke test) ;
#   - "replay" : sert des cassettes enregistrées (tests/fixtures/breachsense/),
#                AUCUN appel réseau — mode voulu en dev/CI et pour la démo ;
#   - "null"   : NullProvider (aucune donnée, aucun appel).
# "auto" (défaut) : "replay" si des cassettes existent, sinon "null". JAMAIS
# "live" par défaut, même quand une licence est configurée — c'est
# précisément le point : le quota est précieux, aucun appel réel ne doit
# partir par accident en développement courant ni en test (ADR-015). Passer
# "live" doit être un acte explicite (variable d'environnement).
BREACHSENSE_MODE = env("BREACHSENSE_MODE", default="auto")
# Répertoire des cassettes (mode "replay"). Vide = emplacement par défaut,
# apps/threat_intelligence/tests/fixtures/breachsense/ — surchargé surtout
# par les tests, pour isoler chaque cas de son propre répertoire.
BREACHSENSE_CASSETTE_DIR = env("BREACHSENSE_CASSETTE_DIR", default="")
# Redis dédié au token-bucket (clé globale, pas par tenant — la licence est
# unique) ; par défaut le même index que le cache Django, namespacé par clé.
BREACHSENSE_THROTTLE_REDIS_URL = env(
    "BREACHSENSE_THROTTLE_REDIS_URL", default=env("REDIS_URL", default="redis://localhost:6379/0")
)
# Marge de sécurité (nombre de requêtes) sous laquelle QuotaManager refuse
# toute nouvelle requête "query" plutôt que de risquer un dépassement de
# licence en cours de mois.
BREACHSENSE_QUOTA_SAFETY_MARGIN = env.int("BREACHSENSE_QUOTA_SAFETY_MARGIN", default=50)
# Anti-abus (ADR-013) : délai minimal entre deux scans manuels déclenchés
# par le même tenant — ne s'applique pas au scan initial automatique.
BREACHSENSE_SCAN_COOLDOWN_HOURS = env.int("BREACHSENSE_SCAN_COOLDOWN_HOURS", default=24)
# Le produit raisonne en MINUTES de bout en bout (modèle, réglage de console,
# API, cache). La variable d'environnement reste en heures — c'est un contrat
# déjà déployé qu'on ne casse pas — et c'est ICI, en un seul endroit, qu'elle
# est convertie. Une seconde conversion ailleurs serait une occasion de
# multiplier ou diviser par 60 au mauvais moment, erreur d'autant plus
# coûteuse qu'elle produit un délai plausible.
BREACHSENSE_SCAN_COOLDOWN_MINUTES = BREACHSENSE_SCAN_COOLDOWN_HOURS * 60
# Taille du pool d'actifs monitorés en temps réel (webhook) — palier
# Essentials. À ajuster si la licence change de palier.
BREACHSENSE_MONITORED_ASSET_POOL_SIZE = env.int("BREACHSENSE_MONITORED_ASSET_POOL_SIZE", default=15)
# Identifiants HTTP Basic du webhook entrant (configurés côté Breachsense
# via /account?action=add&creds=...) — jamais de secret en dur dans le code.
BREACHSENSE_WEBHOOK_USERNAME = env("BREACHSENSE_WEBHOOK_USERNAME", default="")
BREACHSENSE_WEBHOOK_PASSWORD = env("BREACHSENSE_WEBHOOK_PASSWORD", default="")
# URL publique de POST /api/v1/webhooks/breachsense — n'existe qu'une fois
# la plateforme déployée (pas d'URL publique en dev local) ; tant qu'elle
# est vide, l'inscription au pool de 15 actifs monitorés refuse proprement
# (docs/journal.md : protocole de smoke test au déploiement).
BREACHSENSE_WEBHOOK_CALLBACK_URL = env("BREACHSENSE_WEBHOOK_CALLBACK_URL", default="")

# --- Rétention des secrets de fuite (Phase 8C, ADR-014) --------------------
#
# Au-delà de ce délai, le secret chiffré d'un BreachFinding est effacé et
# has_secret repasse à False — la FUITE, elle, est conservée (métadonnées,
# statut, historique de traitement) : c'est son secret qui expire, pas son
# existence. Compté depuis la détection.
BREACH_SECRET_RETENTION_DAYS = env.int("BREACH_SECRET_RETENTION_DAYS", default=90)
# Rétention du journal des révélations. Volontairement PLUS LONGUE que celle
# des secrets : c'est une piste d'audit de sécurité (qui a consulté quoi), sa
# valeur est justement de survivre à la donnée qu'elle protège. Ne contient
# aucun secret (ADR-014).
BREACH_REVEAL_AUDIT_RETENTION_DAYS = env.int("BREACH_REVEAL_AUDIT_RETENTION_DAYS", default=365)

# Destinataire des notifications de demande de démonstration (site vitrine).
# Vide = notification exploitant désactivée (l'accusé de réception au
# prospect, lui, part toujours).
DEMO_REQUEST_NOTIFICATION_EMAIL = env("DEMO_REQUEST_NOTIFICATION_EMAIL", default="")

# --- Offres et abonnements (Phase 10, ADR-019/020) --------------------------
#
# Plafonds PLATEFORME (pas par client) : la licence Breachsense Essentials
# borne toute la plateforme (ADR-013). Ils changeront au passage à un palier
# supérieur — d'où la configuration plutôt que des constantes en dur.
# BREACHSENSE_MONITORED_ASSET_POOL_SIZE (défini plus haut) est le second.
PLATFORM_MONTHLY_SCAN_CAP = env.int("PLATFORM_MONTHLY_SCAN_CAP", default=1000)
# Destinataire des alertes d'exploitation (80 % / 95 % d'une ressource rare).
# Vide = alertes désactivées.
PLATFORM_ALERT_EMAIL = env("PLATFORM_ALERT_EMAIL", default="")
# Essai ouvert automatiquement à la création d'une entreprise.
BILLING_TRIAL_DAYS = env.int("BILLING_TRIAL_DAYS", default=14)
# Offre de l'essai : une offre DÉDIÉE, pas une offre du catalogue (ADR-024).
# Aucune des deux ne convenait, et pour des raisons opposées. « Pilotage »
# engage 3 des 15 emplacements du pool partagé (ADR-013) : cinq essais au
# total, zéro une fois le jeu de démonstration en place. « Veille » n'en
# engage qu'un, mais son catalogue exclut le diagnostic ANSSI : la garde
# n'étant pas encore appliquée rien ne cassait, mais l'essai se serait cassé
# le jour où elle le serait.
# « Essai » sépare les deux contraintes : un emplacement, et les
# fonctionnalités qui donnent envie de payer.
# Réglable depuis la console sans redéploiement (settings_registry.TRIAL_PLAN_CODE).
BILLING_DEFAULT_TRIAL_PLAN_CODE = env("BILLING_DEFAULT_TRIAL_PLAN_CODE", default="essai")

# --- Score d'exposition par actif (Phase 8B, ADR-016) ----------------------
#
# Seuils des quatre niveaux, en configuration et non en dur : ce sont des
# curseurs produit, susceptibles d'être ajustés après retours clients sans
# toucher au code de calcul. Un score STRICTEMENT inférieur au seuil suivant
# reste dans le niveau courant (calme < 20 <= à surveiller < 50 <=
# préoccupant < 75 <= critique).
EXPOSURE_LEVEL_THRESHOLDS = {
    "watch": env.int("EXPOSURE_THRESHOLD_WATCH", default=20),
    "concerning": env.int("EXPOSURE_THRESHOLD_CONCERNING", default=50),
    "critical": env.int("EXPOSURE_THRESHOLD_CRITICAL", default=75),
}
# Délai minimal entre deux générations de synthèse IA d'exposition pour un
# même tenant (anti-rebond du bouton « Actualiser l'analyse » — le quota IA
# par tenant reste le plafond réel, ceci évite juste les clics répétés).
EXPOSURE_SYNTHESIS_COOLDOWN_MINUTES = env.int("EXPOSURE_SYNTHESIS_COOLDOWN_MINUTES", default=10)

# --- 2FA TOTP (Phase 5, US-1.3, cadrage §6) : clé Fernet chiffrant le
# secret TOTP au repos — dédiée, distincte de AI_PSEUDONYMIZATION_KEY
# (compromettre l'une ne doit pas compromettre l'autre). Générer avec
# `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
TOTP_ENCRYPTION_KEY = env("TOTP_ENCRYPTION_KEY", default="")

# --- Secrets de fuite Breachsense (ADR-014, mise à jour) : clé Fernet
# dédiée chiffrant au repos le secret (mot de passe/token/cookie/carte)
# d'un BreachFinding — distincte de TOTP_ENCRYPTION_KEY et
# AI_PSEUDONYMIZATION_KEY (compromettre l'une ne doit pas compromettre les
# autres). Seul le endpoint de révélation privilégié et ré-authentifié
# (BreachFindingRevealView) déchiffre, en mémoire, jamais persisté ni
# journalisé. Générer avec :
# `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
BREACH_SECRET_ENCRYPTION_KEY = env("BREACH_SECRET_ENCRYPTION_KEY", default="")
# Rotation (Phase 8C) : liste ORDONNÉE de clés, la première chiffre, toutes
# déchiffrent (MultiFernet). Permet de tourner la clé sans coupure — on
# ajoute la nouvelle en tête, on lance `rotate_breach_secret_key`, puis on
# retire l'ancienne une fois la commande terminée. Vide => on retombe sur
# BREACH_SECRET_ENCRYPTION_KEY seule (déploiements existants inchangés).
BREACH_SECRET_ENCRYPTION_KEYS = env.list("BREACH_SECRET_ENCRYPTION_KEYS", default=[])

# --- Journalisation (Phase 5, docs/security_review.md A09) ------------------
#
# Sans cette config, Django ne journalise rien de façon actionnable en
# production : ni les 5xx serveur, ni les événements "django.security"
# (hôte non autorisé, verrouillage de compte déclenché — voir
# apps.accounts.services.security_logger). Sortie console uniquement (pas
# de fichier/rotation, pas de service tiers) : cohérent avec la sobriété du
# projet et avec l'interdiction CLAUDE.md d'envoyer des données
# personnelles à un service de suivi d'erreurs externe — seuls des
# identifiants internes ou des empreintes hashées sont journalisés par le
# code applicatif (voir apps.accounts.services._hashed_ident).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "structured"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
