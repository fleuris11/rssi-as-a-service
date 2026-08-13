"""Contrôles de configuration au démarrage (Phase 8D).

Deux niveaux, volontairement :

1. ``validate_production_settings()`` est appelée **à l'import** de
   ``config.settings_production``. Une erreur y lève ``ImproperlyConfigured``,
   donc Gunicorn refuse de démarrer. C'est le seul niveau qui garantit qu'une
   production mal configurée ne serve jamais de trafic : les *system checks*
   de Django ne sont pas exécutés par un serveur WSGI, uniquement par les
   commandes de gestion.
2. Le même corps est exposé comme *system check* Django, pour que
   ``manage.py check --deploy`` le rapporte proprement en CI et dans un script
   de déploiement, avant même de lancer le serveur.

Ce qui est vérifié tient en une phrase : **aucune clé manquante, aucune clé
réutilisée d'un usage à l'autre, aucun réglage de développement laissé actif.**
La réutilisation d'une clé entre deux usages est le défaut le plus facile à
introduire (copier-coller d'une variable dans un `.env`) et le plus coûteux :
elle annule la séparation des clés Fernet posée par ADR-005/009/014, où
compromettre l'une ne doit pas compromettre les autres.
"""

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

# (nom de réglage, libellé) — les clés Fernet qui doivent être présentes,
# valides, et toutes différentes les unes des autres.
FERNET_KEY_SETTINGS = (
    ("AI_PSEUDONYMIZATION_KEY", "pseudonymisation IA (ADR-005)"),
    ("TOTP_ENCRYPTION_KEY", "secret 2FA (ADR-009)"),
    ("BREACH_SECRET_ENCRYPTION_KEY", "secrets de fuite (ADR-014)"),
)

INSECURE_SECRET_KEY_MARKERS = ("change-me", "changeme", "insecure", "dev-secret")


def _collect_breach_keys(settings) -> list[str]:
    """La rotation (ADR-014 §5) autorise une liste ordonnée ; on valide alors
    la clé courante (la première), les anciennes n'ayant plus à être
    distinctes des autres usages une fois la rotation terminée."""
    keys = [k for k in getattr(settings, "BREACH_SECRET_ENCRYPTION_KEYS", []) if k]
    if keys:
        return keys
    single = getattr(settings, "BREACH_SECRET_ENCRYPTION_KEY", "")
    return [single] if single else []


def collect_production_errors(settings) -> list[str]:
    """Renvoie la liste des problèmes de configuration — vide si tout va bien.
    Séparée de la levée d'exception pour être réutilisable par le system check
    et testable sans manipuler l'import des settings."""
    errors: list[str] = []

    # --- Clés de chiffrement -------------------------------------------------
    resolved: dict[str, str] = {}
    for name, purpose in FERNET_KEY_SETTINGS:
        if name == "BREACH_SECRET_ENCRYPTION_KEY":
            keys = _collect_breach_keys(settings)
            value = keys[0] if keys else ""
        else:
            value = getattr(settings, name, "") or ""

        if not value:
            errors.append(f"{name} est absente ou vide (chiffrement : {purpose}).")
            continue
        try:
            Fernet(value.encode() if isinstance(value, str) else value)
        except (ValueError, TypeError):
            errors.append(
                f"{name} n'est pas une clé Fernet valide "
                "(32 octets encodés en base64 url-safe attendus)."
            )
            continue
        resolved[name] = value

    seen: dict[str, str] = {}
    for name, value in resolved.items():
        if value in seen:
            errors.append(
                f"{name} réutilise la même clé que {seen[value]}. Chaque usage doit avoir "
                "sa propre clé : compromettre l'une ne doit pas compromettre les autres "
                "(ADR-005/009/014)."
            )
        else:
            seen[value] = name

    # --- Réglages de développement laissés actifs ---------------------------
    if getattr(settings, "DEBUG", False):
        errors.append("DEBUG est actif : interdit en production.")

    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", []) or []
    if not allowed_hosts:
        errors.append("DJANGO_ALLOWED_HOSTS est vide : renseignez les domaines servis.")
    elif "*" in allowed_hosts:
        errors.append("DJANGO_ALLOWED_HOSTS contient « * » : trop permissif en production.")

    secret_key = getattr(settings, "SECRET_KEY", "") or ""
    if any(marker in secret_key.lower() for marker in INSECURE_SECRET_KEY_MARKERS):
        errors.append("DJANGO_SECRET_KEY semble être la valeur d'exemple : générez-en une vraie.")

    return errors


def validate_production_settings(settings) -> None:
    """Lève ``ImproperlyConfigured`` si la configuration de production est
    incorrecte — appelée à l'import des settings, donc avant tout trafic."""
    errors = collect_production_errors(settings)
    if errors:
        raise ImproperlyConfigured(
            "Configuration de production invalide :\n  - " + "\n  - ".join(errors)
        )
