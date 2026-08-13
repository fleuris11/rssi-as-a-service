"""Service central d'autorisation par fonctionnalité et par quota.

**Point unique** : aucune vue, aucune tâche Celery, aucun service ne doit
tester un droit autrement qu'en passant par ici. Une vérification dispersée
en dur (« si le plan vaut Pilotage alors... ») devient fausse au premier
changement de catalogue, et l'oubli d'une seule garde crée une porte ouverte
qu'aucun test ne signale.

Deux natures de droits, à ne pas confondre :

- **fonctionnalité** : incluse ou non dans l'offre. Un refus est commercial
  (« votre offre ne comprend pas ceci ») et doit être présenté comme tel ;
- **quota** : inclus mais épuisé. Un refus est temporel (« vous avez utilisé
  vos 20 analyses du mois »).

Troisième cas, transverse : l'abonnement n'est pas opérationnel (suspendu,
expiré, résilié). Dans ce cas on bloque **ce qui consomme une ressource**
(analyse, surveillance) mais jamais la lecture des données déjà présentes —
on ne prend pas les données d'un client en otage.
"""

from django.utils import timezone

from . import features as feature_registry
from .models import Subscription


class EntitlementError(Exception):
    """Erreur métier, jamais un 500. Porte de quoi construire un message
    utile côté interface : ce qui manque, et ce qu'il faudrait pour l'avoir."""

    def __init__(self, message, *, feature_key="", required_plan="", reason="feature"):
        super().__init__(message)
        self.message = message
        self.feature_key = feature_key
        self.required_plan = required_plan
        self.reason = reason


def get_subscription(tenant) -> Subscription | None:
    return Subscription.objects.filter(tenant=tenant).select_related("plan").first()


def cheapest_plan_with(feature_key: str):
    """L'offre publiée la moins chère qui inclut cette fonctionnalité — ce
    qu'on propose au client quand il bute dessus. Sans cela, le message ne
    dirait que « non », ce qui n'aide personne.

    Les offres **sur devis** sont écartées : leur prix stocké vaut zéro, ce
    qui les ferait remonter en tête du classement et conduirait à proposer
    « contactez-nous » là où une offre standard suffisait. Elles ne sont
    reprises que si aucune offre à prix affiché ne convient.
    """
    from .models import Plan

    published = [
        plan
        for plan in Plan.objects.filter(status=Plan.Status.PUBLISHED).order_by(
            "price_monthly", "display_order"
        )
        if plan.has_feature(feature_key)
    ]
    priced = [plan for plan in published if not plan.is_quote_only]
    return (priced or published)[0] if published else None


def has_feature(tenant, feature_key: str) -> bool:
    subscription = get_subscription(tenant)
    if subscription is None:
        return False
    return feature_key in subscription.effective_features


def ensure_feature(tenant, feature_key: str) -> None:
    """Lève ``EntitlementError`` si l'offre du tenant n'inclut pas la
    fonctionnalité."""
    if has_feature(tenant, feature_key):
        return
    feature = feature_registry.get(feature_key)
    label = feature.label if feature else feature_key
    plan = cheapest_plan_with(feature_key)
    if plan is not None:
        message = (
            f"« {label} » n'est pas comprise dans votre offre. "
            f"Elle est incluse à partir de l'offre {plan.name}."
        )
    else:
        message = f"« {label} » n'est pas comprise dans votre offre."
    raise EntitlementError(
        message,
        feature_key=feature_key,
        required_plan=plan.name if plan else "",
        reason="feature",
    )


def ensure_operational(tenant, *, action="Cette action") -> None:
    """Bloque ce qui consomme une ressource quand l'abonnement ne l'est plus.
    N'est **jamais** appelée sur un chemin de lecture."""
    subscription = get_subscription(tenant)
    if subscription is None:
        raise EntitlementError(f"{action} nécessite un abonnement actif.", reason="no_subscription")
    if subscription.is_operational:
        return
    raise EntitlementError(
        f"{action} est suspendue : votre abonnement est "
        f"{subscription.get_status_display().lower()}. Vos données restent consultables.",
        reason="not_operational",
    )


# --- Quotas -----------------------------------------------------------------


def monthly_scans_used(tenant) -> int:
    from apps.threat_intelligence.models import BreachIntelligenceUsage

    period_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return BreachIntelligenceUsage.all_objects.filter(
        tenant=tenant, created_at__gte=period_start
    ).count()


def ensure_scan_quota(tenant) -> None:
    subscription = get_subscription(tenant)
    if subscription is None:
        raise EntitlementError("Aucun abonnement actif.", reason="no_subscription")
    quota = subscription.monthly_scans_quota
    if quota == 0:  # illimité
        return
    used = monthly_scans_used(tenant)
    if used >= quota:
        raise EntitlementError(
            f"Vous avez utilisé les {quota} analyses comprises dans votre offre ce mois-ci. "
            "Le compteur repart au premier jour du mois prochain.",
            reason="quota",
        )


def ensure_monitored_asset_quota(tenant) -> None:
    """Quota CLIENT. La garde plateforme (capacity.py) est distincte et
    s'ajoute : un client peut avoir du quota alors que la plateforme est
    saturée, et inversement."""
    from apps.threat_intelligence.models import MonitoredAsset

    subscription = get_subscription(tenant)
    if subscription is None:
        raise EntitlementError("Aucun abonnement actif.", reason="no_subscription")
    quota = subscription.monitored_assets_quota
    used = MonitoredAsset.all_objects.filter(tenant=tenant, is_active=True).count()
    if quota and used >= quota:
        raise EntitlementError(
            f"Votre offre comprend {quota} actif(s) surveillé(s) en continu, tous utilisés. "
            "Retirez-en un ou changez d'offre pour en surveiller davantage.",
            reason="quota",
        )


def user_limit_reached(tenant) -> bool:
    from apps.tenants.models import Membership

    subscription = get_subscription(tenant)
    if subscription is None:
        return True
    quota = subscription.max_users_quota
    if quota == 0:  # illimité
        return False
    return Membership.all_objects.filter(tenant=tenant).count() >= quota


def summary(tenant) -> dict:
    """Ce que le frontend consomme pour afficher les fonctionnalités hors
    offre en **désactivé** plutôt que masquées : il lui faut la liste
    complète, ce qui est inclus, et le plan requis pour le reste."""
    from apps.threat_intelligence.models import MonitoredAsset

    subscription = get_subscription(tenant)
    included = set(subscription.effective_features) if subscription else set()

    features = []
    for key, feature in feature_registry.REGISTRY.items():
        if key in included:
            features.append({"key": key, "label": feature.label, "included": True})
            continue
        plan = cheapest_plan_with(key)
        features.append(
            {
                "key": key,
                "label": feature.label,
                "included": False,
                "teaser": feature.teaser,
                "required_plan": plan.name if plan else "",
            }
        )

    if subscription is None:
        return {"subscription": None, "features": features}

    return {
        "subscription": {
            "plan_name": subscription.plan.name,
            "plan_code": subscription.plan.code,
            "status": subscription.status,
            "status_label": subscription.get_status_display(),
            "is_operational": subscription.is_operational,
            "trial_ends_at": subscription.trial_ends_at,
            "renews_at": subscription.renews_at,
        },
        "quotas": {
            "monitored_assets": {
                "quota": subscription.monitored_assets_quota,
                "used": MonitoredAsset.all_objects.filter(tenant=tenant, is_active=True).count(),
            },
            "monthly_scans": {
                "quota": subscription.monthly_scans_quota,
                "used": monthly_scans_used(tenant),
            },
        },
        "features": features,
    }
