"""Ressources rares de la PLATEFORME — la garde la plus importante de cette
phase.

La licence Breachsense Essentials plafonne **la plateforme entière** (ADR-013),
pas chaque client : 15 emplacements de surveillance continue et 1000 requêtes
d'analyse par mois, partagés par tous les tenants. Vendre à un client un quota
que la plateforme ne peut pas honorer produirait un engagement contractuel
intenable, découvert au pire moment — quand le client active sa surveillance.

Règle appliquée ici, sans exception : **on refuse AVANT d'enregistrer**. Toute
activation d'abonnement, tout changement de plan et tout ajout d'actif surveillé
passe par ``ensure_*`` et lève ``PlatformCapacityError`` si le plafond serait
dépassé. Un dépassement constaté après coup est un échec de conception, pas un
incident d'exploitation.

Les plafonds sont des réglages d'exploitation (``apps.platform_admin.
settings_registry``) : ils changeront au passage à un palier de licence
supérieur, et ce module ne doit pas être modifié ce jour-là. Tant qu'aucune
modification n'a été faite depuis la console, ils retombent sur les variables
d'environnement (``BREACHSENSE_MONITORED_ASSET_POOL_SIZE``,
``PLATFORM_MONTHLY_SCAN_CAP``).
"""

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

_ALERT_CACHE_KEY = "platform_capacity:alert:{resource}:{threshold}"


# Seuils d'alerte d'exploitation : on prévient l'administrateur plateforme
# AVANT la saturation, pas au moment où une vente devient impossible.
def alert_thresholds() -> tuple[float, ...]:
    """Seuils d'alerte, réglables depuis la console (phase 11). Triés et
    dédoublonnés : régler les deux seuils sur la même valeur ne doit pas
    envoyer deux fois la même alerte."""
    from apps.platform_admin import settings_registry

    ratios = {
        int(settings_registry.get(settings_registry.ALERT_WARNING_RATIO)) / 100,
        int(settings_registry.get(settings_registry.ALERT_CRITICAL_RATIO)) / 100,
    }
    return tuple(sorted(ratios))


class PlatformCapacityError(Exception):
    """Le plafond plateforme serait dépassé.

    **Deux messages, deux publics.** ``str(exc)`` porte le détail
    d'exploitation — combien d'emplacements, sur quel plafond, ce qu'il faut
    libérer : c'est ce que le back-office affiche, et un refus sans
    indication de sortie obligerait l'exploitant à aller lire le code.

    ``client_message`` est ce qu'un CLIENT a le droit de lire. Le détail
    d'exploitation n'est pas seulement inutile pour lui : « il reste 3
    emplacements sur 15 » lui apprend la taille du parc et la consommation
    des autres clients. Dans un produit dont l'argument est le cloisonnement,
    c'est une fuite entre locataires — et elle passait par un message
    d'erreur, l'endroit où personne ne pense à en chercher une.
    """

    #: Repli neutre : une indisponibilité temporaire, sans chiffre ni cause.
    DEFAULT_CLIENT_MESSAGE = (
        "Cette action n'est pas disponible pour le moment. Contactez-nous : "
        "nous la débloquons pour vous."
    )

    def __init__(self, operator_message: str, *, client_message: str | None = None):
        super().__init__(operator_message)
        self.operator_message = operator_message
        self.client_message = client_message or self.DEFAULT_CLIENT_MESSAGE


@dataclass
class ResourceUsage:
    resource: str
    label: str
    used: int
    capacity: int

    @property
    def remaining(self) -> int:
        return max(0, self.capacity - self.used)

    @property
    def ratio(self) -> float:
        return (self.used / self.capacity) if self.capacity else 0.0

    def as_dict(self) -> dict:
        return {
            "resource": self.resource,
            "label": self.label,
            "used": self.used,
            "capacity": self.capacity,
            "remaining": self.remaining,
            "ratio": round(self.ratio, 3),
        }


# --- Mesure -----------------------------------------------------------------


# Les plafonds sont désormais des RÉGLAGES d'exploitation (phase 11) : ils
# changent le jour où la licence change de palier, et cela ne doit demander ni
# accès au serveur ni redémarrage. Le registre retombe sur la variable
# d'environnement tant que le réglage n'a jamais été modifié — la plateforme
# démarre donc sans aucune ligne en base.
def monitored_slot_capacity() -> int:
    from apps.platform_admin import settings_registry

    return int(settings_registry.get(settings_registry.MONITORED_SLOT_POOL))


def monthly_scan_capacity() -> int:
    from apps.platform_admin import settings_registry

    return int(settings_registry.get(settings_registry.MONTHLY_SCAN_CAP))


def monitored_slots_used() -> int:
    """Emplacements réellement occupés auprès du fournisseur."""
    from apps.threat_intelligence.models import MonitoredAsset

    return MonitoredAsset.all_objects.filter(is_active=True).count()


def monitored_slots_committed() -> int:
    """Emplacements **engagés contractuellement** : la somme des quotas des
    abonnements opérationnels.

    C'est cette valeur — et non celle des emplacements occupés — qui doit être
    comparée au plafond avant de vendre. Un client qui n'a pas encore activé
    sa surveillance a malgré tout droit à ses emplacements ; les compter
    seulement à l'activation reviendrait à survendre la plateforme et à
    refuser le service au client le plus lent à s'installer.
    """
    # Une surcharge par abonnement (``override_monitored_assets``) ne
    # s'agrège pas en SQL simple : on parcourt en Python, le volume étant de
    # l'ordre de la dizaine d'abonnements. Si la plateforme atteignait un
    # ordre de grandeur supérieur, un COALESCE annoté remplacerait ceci.
    return projected_monitored_slots(additional=0)


def monthly_scans_used() -> int:
    from apps.threat_intelligence.models import BreachIntelligenceUsage

    period_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        BreachIntelligenceUsage.all_objects.filter(created_at__gte=period_start).aggregate(
            total=Sum("requests_consumed")
        )["total"]
        or 0
    )


def snapshot() -> list[ResourceUsage]:
    """État courant des ressources rares — ce que le back-office affiche en
    permanence."""
    return [
        ResourceUsage(
            resource="monitored_slots",
            label="Emplacements de surveillance continue",
            used=monitored_slots_committed(),
            capacity=monitored_slot_capacity(),
        ),
        ResourceUsage(
            resource="monthly_scans",
            label="Analyses ponctuelles ce mois-ci",
            used=monthly_scans_used(),
            capacity=monthly_scan_capacity(),
        ),
    ]


# --- Gardes (refus AVANT enregistrement) ------------------------------------


def projected_monitored_slots(*, additional: int, excluding_subscription_id=None) -> int:
    """Combien d'emplacements seraient engagés si l'on ajoutait ``additional``.

    ``excluding_subscription_id`` sert au changement de plan : l'abonnement
    qu'on modifie ne doit pas être compté deux fois (une fois dans l'existant,
    une fois dans le nouveau quota).
    """
    from .models import Subscription

    committed = 0
    queryset = Subscription.objects.filter(
        status__in=[Subscription.Status.TRIAL, Subscription.Status.ACTIVE]
    ).select_related("plan")
    if excluding_subscription_id is not None:
        queryset = queryset.exclude(id=excluding_subscription_id)
    for subscription in queryset:
        committed += subscription.monitored_assets_quota
    return committed + additional


def ensure_monitored_slots_available(*, additional: int, excluding_subscription_id=None) -> None:
    """Refuse si l'engagement dépasserait le pool plateforme."""
    if additional <= 0:
        return
    capacity = monitored_slot_capacity()
    projected = projected_monitored_slots(
        additional=additional, excluding_subscription_id=excluding_subscription_id
    )
    if projected > capacity:
        already = projected - additional
        remaining = max(0, capacity - already)
        raise PlatformCapacityError(
            f"Cette opération engagerait {projected} emplacements de surveillance continue "
            f"pour un plafond plateforme de {capacity}. Il en reste {remaining} disponible(s). "
            "Libérez des emplacements (suspension ou changement de plan d'un client existant) "
            "ou passez à un palier de licence supérieur avant de poursuivre.",
            client_message=(
                "La surveillance continue ne peut pas être activée pour le "
                "moment. Contactez-nous : nous l'activons pour vous."
            ),
        )


def ensure_scan_budget_available(*, additional: int = 1) -> None:
    """Refuse si le budget mensuel d'analyses de la plateforme serait dépassé.

    Distinct de ``QuotaManager.ensure_query_budget_available`` (ADR-013), qui
    interroge le fournisseur pour le budget *réellement restant* côté licence.
    Ici on raisonne sur la consommation mesurée côté plateforme : les deux
    gardes se complètent, l'une protège la licence, l'autre l'engagement
    commercial.
    """
    if additional <= 0:
        return
    capacity = monthly_scan_capacity()
    used = monthly_scans_used()
    if used + additional > capacity:
        raise PlatformCapacityError(
            f"Le budget d'analyses de la plateforme pour ce mois est atteint "
            f"({used}/{capacity}). Il reste {max(0, capacity - used)} analyse(s). "
            "Attendez le mois suivant ou passez à un palier de licence supérieur.",
            # Vu du client, c'est une indisponibilité passagère : ni le
            # compteur du parc, ni notre palier de licence ne le concernent.
            client_message=(
                "Les analyses sont momentanément indisponibles. Réessayez "
                "d'ici quelques heures ; contactez-nous si c'est urgent."
            ),
        )


def check_alert_thresholds() -> list[str]:
    """Prévient l'administrateur plateforme à 80 % et 95 % d'une ressource.

    Une alerte par seuil et par ressource et par mois : sans cette mémoire,
    chaque analyse au-dessus du seuil enverrait un email, et l'exploitant
    cesserait de les lire — le pire résultat possible pour une alerte.
    """
    from django.core.cache import cache

    sent = []
    recipient = getattr(settings, "PLATFORM_ALERT_EMAIL", "") or ""
    if not recipient:
        return sent

    period = timezone.now().strftime("%Y-%m")
    for usage in snapshot():
        for threshold in alert_thresholds():
            if usage.ratio < threshold:
                continue
            key = _ALERT_CACHE_KEY.format(
                resource=f"{usage.resource}:{period}", threshold=int(threshold * 100)
            )
            if cache.get(key):
                continue
            try:
                send_mail(
                    subject=(
                        f"[Plateforme] {usage.label} à {int(usage.ratio * 100)} % "
                        f"({usage.used}/{usage.capacity})"
                    ),
                    message=(
                        f"La ressource « {usage.label} » atteint "
                        f"{int(usage.ratio * 100)} % de sa capacité plateforme.\n\n"
                        f"Consommé : {usage.used}\n"
                        f"Capacité : {usage.capacity}\n"
                        f"Restant : {usage.remaining}\n\n"
                        "Au-delà du plafond, toute nouvelle activation d'abonnement sera "
                        "refusée. Envisagez un palier de licence supérieur."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient],
                    fail_silently=False,
                )
                cache.set(key, True, timeout=40 * 24 * 3600)
                sent.append(f"{usage.resource}@{int(threshold * 100)}")
            except Exception:  # noqa: BLE001 - une alerte non partie ne doit rien bloquer
                logger.warning(
                    "Alerte de capacité non envoyée pour %s", usage.resource, exc_info=True
                )
    return sent
