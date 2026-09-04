"""Réglages d'exploitation modifiables depuis la console.

Un réglage est déclaré **en code** (ici) et sa valeur vit **en base**. Le code
reste la référence de ce qui existe, de son type et de ses bornes ; la base ne
porte que la valeur courante. Conséquence : un réglage inconnu en base est
ignoré, et un réglage jamais modifié retombe sur la valeur du fichier
d'environnement — la plateforme démarre donc sans aucune ligne en base.

Ce qui n'est PAS ici : les secrets. Une clé de chiffrement en base serait
exposée par la moindre sauvegarde et la moindre injection SQL. Ils restent en
variables d'environnement, et la console n'en montre que la présence et la
validité.
"""

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache

CACHE_KEY = "platform_settings:v1"
CACHE_TTL = 300


@dataclass(frozen=True)
class SettingSpec:
    key: str
    label: str
    help_text: str
    kind: str  # "int" | "bool" | "text"
    django_setting: str = ""  # valeur de repli, lue dans settings.py
    default: Any = None
    minimum: int | None = None
    maximum: int | None = None
    group: str = "Général"
    # Un réglage sensible demande une confirmation explicite dans la console :
    # le baisser peut mettre la plateforme en dépassement immédiat.
    sensitive: bool = False


MONITORED_SLOT_POOL = "monitored_slot_pool"
MONTHLY_SCAN_CAP = "monthly_scan_cap"
TRIAL_DAYS = "trial_days"
TRIAL_PLAN_CODE = "trial_plan_code"
SECRET_RETENTION_DAYS = "secret_retention_days"
REVEAL_AUDIT_RETENTION_DAYS = "reveal_audit_retention_days"
ALERT_WARNING_RATIO = "alert_warning_ratio"
ALERT_CRITICAL_RATIO = "alert_critical_ratio"
SIGNUP_OPEN = "signup_open"
MAINTENANCE_MESSAGE = "maintenance_message"
TRASH_RETENTION_DAYS = "trash_retention_days"
CTI_MODE = "cti_mode"
SCAN_COOLDOWN_HOURS = "scan_cooldown_hours"

REGISTRY: dict[str, SettingSpec] = {
    spec.key: spec
    for spec in [
        SettingSpec(
            MONITORED_SLOT_POOL,
            "Emplacements de surveillance continue",
            "Plafond de la licence pour TOUTE la plateforme, pas par client. "
            "Le baisser en dessous de ce qui est déjà engagé ne retire rien aux "
            "clients en cours, mais bloque toute nouvelle activation.",
            "int",
            django_setting="BREACHSENSE_MONITORED_ASSET_POOL_SIZE",
            minimum=0,
            maximum=10000,
            group="Licence de renseignement",
            sensitive=True,
        ),
        SettingSpec(
            SCAN_COOLDOWN_HOURS,
            "Délai entre deux analyses manuelles (heures)",
            "Temps d'attente imposé à un client entre deux analyses lancées "
            "depuis son espace. Il protège le budget de requêtes partagé, pas "
            "le client. Un client précis peut recevoir sa propre valeur depuis "
            "sa fiche — celle-ci ne s'applique qu'à défaut. 0 = aucun délai.",
            "int",
            django_setting="BREACHSENSE_SCAN_COOLDOWN_HOURS",
            minimum=0,
            maximum=8760,
            group="Licence de renseignement",
        ),
        SettingSpec(
            MONTHLY_SCAN_CAP,
            "Analyses ponctuelles par mois",
            "Plafond mensuel de requêtes d'analyse pour toute la plateforme.",
            "int",
            django_setting="PLATFORM_MONTHLY_SCAN_CAP",
            minimum=0,
            maximum=1000000,
            group="Licence de renseignement",
            sensitive=True,
        ),
        SettingSpec(
            TRIAL_DAYS,
            "Durée d'essai par défaut (jours)",
            "S'applique aux essais ouverts après la modification ; les essais "
            "en cours gardent leur échéance.",
            "int",
            django_setting="BILLING_TRIAL_DAYS",
            minimum=0,
            maximum=365,
            group="Offres et essais",
        ),
        SettingSpec(
            TRIAL_PLAN_CODE,
            "Offre attribuée à l'ouverture d'un essai",
            "Code de l'offre sur laquelle démarre un essai créé sans offre "
            "explicite (inscription libre notamment).",
            "text",
            django_setting="BILLING_DEFAULT_TRIAL_PLAN_CODE",
            group="Offres et essais",
        ),
        SettingSpec(
            SECRET_RETENTION_DAYS,
            "Conservation des mots de passe fuités (jours)",
            "Au-delà, le secret chiffré est effacé ; la fuite, elle, reste. "
            "Cette valeur est annoncée dans la politique de confidentialité : "
            "la modifier oblige à mettre cette page à jour.",
            "int",
            django_setting="BREACH_SECRET_RETENTION_DAYS",
            minimum=1,
            maximum=3650,
            group="Conservation des données",
            sensitive=True,
        ),
        SettingSpec(
            REVEAL_AUDIT_RETENTION_DAYS,
            "Conservation du journal des consultations (jours)",
            "Piste d'audit des révélations de mot de passe. Volontairement plus "
            "longue que la conservation des secrets eux-mêmes.",
            "int",
            django_setting="BREACH_REVEAL_AUDIT_RETENTION_DAYS",
            minimum=1,
            maximum=3650,
            group="Conservation des données",
            sensitive=True,
        ),
        SettingSpec(
            ALERT_WARNING_RATIO,
            "Seuil d'alerte « attention » (%)",
            "Taux d'occupation d'une ressource rare à partir duquel une alerte "
            "est envoyée à l'exploitant.",
            "int",
            default=80,
            minimum=1,
            maximum=100,
            group="Alertes de consommation",
        ),
        SettingSpec(
            ALERT_CRITICAL_RATIO,
            "Seuil d'alerte « critique » (%)",
            "Second seuil, plus haut : la plateforme est proche de la saturation.",
            "int",
            default=95,
            minimum=1,
            maximum=100,
            group="Alertes de consommation",
        ),
        SettingSpec(
            SIGNUP_OPEN,
            "Inscription libre ouverte",
            "Fermée, la vitrine n'accepte plus de création de compte autonome : "
            "seule la console peut créer un client. Utile quand la capacité est "
            "presque épuisée.",
            "bool",
            default=True,
            group="Accès à la plateforme",
        ),
        SettingSpec(
            MAINTENANCE_MESSAGE,
            "Message affiché aux clients",
            "Bandeau affiché dans l'espace client. Vide = aucun bandeau. "
            "N'interrompt aucun service : c'est une information, pas un blocage.",
            "text",
            default="",
            group="Accès à la plateforme",
        ),
        SettingSpec(
            CTI_MODE,
            "Source du renseignement sur les fuites",
            "« live » interroge réellement l'API du fournisseur et consomme "
            "votre quota mensuel, non reconstituable. « replay » rejoue des "
            "données enregistrées : rien n'est consommé, mais les résultats "
            "sont fictifs — à ne jamais servir à un client payant. « null » "
            "ne renvoie aucune donnée. « auto » choisit replay si des données "
            "enregistrées existent, sinon null : jamais live.",
            "text",
            django_setting="BREACHSENSE_MODE",
            group="Licence de renseignement",
            sensitive=True,
        ),
        SettingSpec(
            TRASH_RETENTION_DAYS,
            "Durée de conservation en corbeille (jours)",
            "Un objet archivé reste restaurable pendant cette durée avant de "
            "pouvoir être supprimé définitivement.",
            "int",
            default=30,
            minimum=1,
            maximum=365,
            group="Conservation des données",
        ),
    ]
}


class SettingError(ValueError):
    """Valeur refusée pour un réglage."""


def _fallback(spec: SettingSpec) -> Any:
    if spec.django_setting:
        return getattr(settings, spec.django_setting, spec.default)
    return spec.default


def _stored() -> dict[str, Any]:
    """Valeurs en base, mises en cache : ces réglages sont lus à chaque
    vérification de capacité, soit plusieurs fois par requête."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    from .models import PlatformSetting

    values = {row.key: row.value for row in PlatformSetting.objects.all()}
    cache.set(CACHE_KEY, values, CACHE_TTL)
    return values


def invalidate_cache() -> None:
    cache.delete(CACHE_KEY)


def get(key: str) -> Any:
    """Valeur courante : la base si elle a été modifiée, sinon l'environnement."""
    spec = REGISTRY.get(key)
    if spec is None:
        raise SettingError(f"Réglage inconnu : {key}")
    stored = _stored()
    if key in stored:
        return stored[key]
    return _fallback(spec)


def coerce(spec: SettingSpec, raw: Any) -> Any:
    """Valide et convertit une valeur saisie. Une seule règle métier, côté
    serveur : la console la réutilise, elle ne la redéfinit pas."""
    if spec.kind == "int":
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise SettingError(f"« {spec.label} » attend un nombre entier.") from None
        if spec.minimum is not None and value < spec.minimum:
            raise SettingError(f"« {spec.label} » ne peut pas être inférieur à {spec.minimum}.")
        if spec.maximum is not None and value > spec.maximum:
            raise SettingError(f"« {spec.label} » ne peut pas dépasser {spec.maximum}.")
        return value

    if spec.kind == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.lower() in {"true", "false", "1", "0"}:
            return raw.lower() in {"true", "1"}
        raise SettingError(f"« {spec.label} » attend oui ou non.")

    value = "" if raw is None else str(raw).strip()

    if spec.key == CTI_MODE:
        modes = ("live", "replay", "null", "auto")
        if value.lower() not in modes:
            raise SettingError(
                f"« {spec.label} » accepte uniquement : {', '.join(modes)}. Reçu : {value!r}."
            )
        return value.lower()

    if len(value) > 2000:
        raise SettingError(f"« {spec.label} » est trop long (2000 caractères maximum).")
    return value


def describe() -> list[dict]:
    """Le catalogue complet, pour l'écran de configuration."""
    stored = _stored()
    return [
        {
            "key": spec.key,
            "label": spec.label,
            "help_text": spec.help_text,
            "kind": spec.kind,
            "group": spec.group,
            "sensitive": spec.sensitive,
            "value": stored.get(spec.key, _fallback(spec)),
            "default": _fallback(spec),
            "is_overridden": spec.key in stored,
            "minimum": spec.minimum,
            "maximum": spec.maximum,
        }
        for spec in REGISTRY.values()
    ]
