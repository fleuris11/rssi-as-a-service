"""Interface publique de l'app billing : cycle de vie des abonnements.

Toute transition d'état est **explicite et tracée** (``SubscriptionEvent``) —
aucune ne se produit par effet de bord. Et toute opération qui augmente
l'engagement de la plateforme passe par ``capacity.ensure_*`` **avant**
l'écriture : refuser après avoir enregistré reviendrait à vendre puis à se
dédire.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import capacity
from .models import Payment, Plan, Subscription, SubscriptionEvent

logger = logging.getLogger(__name__)


class BillingError(Exception):
    """Violation d'une règle métier de facturation."""


# --- Catalogue --------------------------------------------------------------


def list_published_plans():
    return Plan.objects.filter(status=Plan.Status.PUBLISHED).order_by(
        "display_order", "price_monthly"
    )


def get_default_trial_plan() -> Plan | None:
    """Offre sur laquelle démarre un essai. Configurable : le jour où le
    catalogue change, on ne veut pas rechercher un code en dur dans le code."""
    code = getattr(settings, "BILLING_DEFAULT_TRIAL_PLAN_CODE", "") or ""
    if code:
        plan = Plan.objects.filter(code=code).first()
        if plan is not None:
            return plan
        logger.warning(
            "BILLING_DEFAULT_TRIAL_PLAN_CODE=%r ne correspond à aucune offre ; "
            "repli sur la première offre publiée.",
            code,
        )
    return list_published_plans().first()


# --- Journalisation des transitions ----------------------------------------


def _record_event(
    subscription, *, from_status, to_status, from_plan="", to_plan="", reason="", actor=None
):
    return SubscriptionEvent.objects.create(
        subscription=subscription,
        from_status=from_status or "",
        to_status=to_status,
        from_plan=from_plan,
        to_plan=to_plan,
        reason=reason[:255],
        actor=actor,
    )


# --- Cycle de vie -----------------------------------------------------------


@transaction.atomic
def start_trial(*, tenant, plan=None, actor=None, days=None) -> Subscription:
    """Ouvre un essai. Appelée à la création d'un tenant.

    L'essai engage les mêmes emplacements de surveillance qu'un abonnement
    payant : il passe donc par la même garde de capacité. Un essai gratuit qui
    ferait déborder la plateforme coûterait le service à un client payant.
    """
    if Subscription.objects.filter(tenant=tenant).exists():
        raise BillingError("Cette entreprise a déjà un abonnement.")

    plan = plan or get_default_trial_plan()
    if plan is None:
        raise BillingError("Aucune offre disponible pour démarrer un essai.")

    capacity.ensure_monitored_slots_available(additional=plan.monitored_assets)

    days = days if days is not None else settings.BILLING_TRIAL_DAYS
    now = timezone.now()
    subscription = Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=Subscription.Status.TRIAL,
        started_at=now,
        trial_ends_at=now + timedelta(days=days),
    )
    _record_event(
        subscription,
        from_status="",
        to_status=Subscription.Status.TRIAL,
        to_plan=plan.name,
        reason=f"Essai de {days} jours ouvert à la création de l'entreprise.",
        actor=actor,
    )
    capacity.check_alert_thresholds()
    return subscription


@transaction.atomic
def activate(*, subscription, period=None, actor=None, reason="") -> Subscription:
    """Passe un abonnement en actif (fin d'essai, réactivation, encaissement).

    Vérifie la capacité même si l'abonnement existait déjà : un abonnement
    suspendu ne compte plus dans l'engagement (il ne consomme rien), le
    réactiver ré-engage donc réellement des emplacements.
    """
    if subscription.status == Subscription.Status.ACTIVE:
        return subscription

    if not subscription.is_operational:
        capacity.ensure_monitored_slots_available(
            additional=subscription.monitored_assets_quota,
            excluding_subscription_id=subscription.id,
        )

    previous = subscription.status
    now = timezone.now()
    subscription.status = Subscription.Status.ACTIVE
    if period:
        subscription.period = period
    delta = timedelta(days=365 if subscription.period == Subscription.Period.YEARLY else 30)
    subscription.renews_at = now + delta
    subscription.ends_at = None
    subscription.save(update_fields=["status", "period", "renews_at", "ends_at", "updated_at"])

    _record_event(
        subscription,
        from_status=previous,
        to_status=Subscription.Status.ACTIVE,
        reason=reason or "Abonnement activé.",
        actor=actor,
    )
    capacity.check_alert_thresholds()
    return subscription


@transaction.atomic
def suspend(*, subscription, actor=None, reason="") -> Subscription:
    """Suspend : plus d'analyse ni de surveillance, mais les données restent
    consultables (voir entitlements.ensure_operational)."""
    previous = subscription.status
    subscription.status = Subscription.Status.SUSPENDED
    subscription.save(update_fields=["status", "updated_at"])
    _record_event(
        subscription,
        from_status=previous,
        to_status=Subscription.Status.SUSPENDED,
        reason=reason or "Abonnement suspendu.",
        actor=actor,
    )
    return subscription


@transaction.atomic
def cancel(*, subscription, actor=None, reason="") -> Subscription:
    previous = subscription.status
    subscription.status = Subscription.Status.CANCELLED
    subscription.ends_at = timezone.now()
    subscription.save(update_fields=["status", "ends_at", "updated_at"])
    _record_event(
        subscription,
        from_status=previous,
        to_status=Subscription.Status.CANCELLED,
        reason=reason or "Abonnement résilié.",
        actor=actor,
    )
    return subscription


@transaction.atomic
def change_plan(*, subscription, plan, actor=None, reason="") -> Subscription:
    """Changement d'offre. Ne vérifie la capacité que si le nouveau quota est
    supérieur — une réduction libère, elle ne peut pas faire déborder."""
    if plan.id == subscription.plan_id:
        return subscription

    previous_plan = subscription.plan
    if subscription.is_operational:
        delta = plan.monitored_assets - subscription.monitored_assets_quota
        if delta > 0:
            capacity.ensure_monitored_slots_available(
                additional=plan.monitored_assets,
                excluding_subscription_id=subscription.id,
            )

    subscription.plan = plan
    # Les surcharges appartenaient à l'ancienne négociation : les conserver
    # ferait silencieusement suivre des quotas sur mesure sur une offre
    # standard. On repart des quotas de la nouvelle offre.
    subscription.override_monitored_assets = None
    subscription.override_monthly_scans = None
    subscription.override_max_users = None
    subscription.override_features = None
    subscription.save(
        update_fields=[
            "plan",
            "override_monitored_assets",
            "override_monthly_scans",
            "override_max_users",
            "override_features",
            "updated_at",
        ]
    )
    _record_event(
        subscription,
        from_status=subscription.status,
        to_status=subscription.status,
        from_plan=previous_plan.name,
        to_plan=plan.name,
        reason=reason or f"Changement d'offre : {previous_plan.name} vers {plan.name}.",
        actor=actor,
    )
    capacity.check_alert_thresholds()
    return subscription


@transaction.atomic
def expire_due_trials(*, now=None) -> int:
    """Bascule les essais échus en expiré. Idempotente (une seconde passe ne
    trouve plus rien) — appelée par une tâche planifiée."""
    now = now or timezone.now()
    due = Subscription.objects.filter(status=Subscription.Status.TRIAL, trial_ends_at__lte=now)
    count = 0
    for subscription in due:
        subscription.status = Subscription.Status.EXPIRED
        subscription.ends_at = now
        subscription.save(update_fields=["status", "ends_at", "updated_at"])
        _record_event(
            subscription,
            from_status=Subscription.Status.TRIAL,
            to_status=Subscription.Status.EXPIRED,
            reason="Fin de la période d'essai.",
        )
        count += 1
    return count


# --- Paiements (saisie manuelle, ADR-020) -----------------------------------


def record_payment(
    *, subscription, amount, received_at, reference="", note="", actor=None
) -> Payment:
    return Payment.objects.create(
        subscription=subscription,
        amount=amount,
        currency=subscription.plan.currency,
        received_at=received_at,
        reference=reference,
        note=note,
        recorded_by=actor,
    )


# --- Console d'administration (phase 11) ------------------------------------


@transaction.atomic
def set_trial_end(*, subscription, ends_at, actor=None, reason="") -> Subscription:
    """Prolonge ou raccourcit un essai.

    Raccourcir n'est pas anodin : porter l'échéance dans le passé revient à
    couper l'accès opérationnel du client à la prochaine passe de la tâche
    d'expiration. On l'autorise (c'est une décision commerciale légitime) mais
    on l'inscrit au journal comme tout le reste.
    """
    if subscription.status != Subscription.Status.TRIAL:
        raise BillingError("Seul un abonnement en période d'essai a une échéance d'essai.")

    previous = subscription.trial_ends_at
    subscription.trial_ends_at = ends_at
    subscription.save(update_fields=["trial_ends_at", "updated_at"])
    _record_event(
        subscription,
        from_status=subscription.status,
        to_status=subscription.status,
        reason=reason or f"Échéance d'essai portée au {ends_at:%d/%m/%Y}.",
        actor=actor,
    )
    return subscription


# Surcharges négociées. ``None`` remet le quota de l'offre — c'est la seule
# façon de revenir en arrière sur un prix ou un quota négocié.
OVERRIDE_FIELDS = (
    "override_monitored_assets",
    "override_monthly_scans",
    "override_max_users",
    "override_features",
)


def snapshot_subscription(subscription) -> dict:
    return {
        "plan": subscription.plan.code,
        "status": subscription.status,
        "period": subscription.period,
        "trial_ends_at": subscription.trial_ends_at,
        "internal_notes": subscription.internal_notes,
        **{field: getattr(subscription, field) for field in OVERRIDE_FIELDS},
    }


@transaction.atomic
def set_quota_overrides(*, subscription, actor=None, **overrides) -> Subscription:
    """Applique des quotas négociés, indispensables pour un palier sur devis.

    Toute HAUSSE d'emplacements passe par la garde de capacité : un quota
    négocié engage la plateforme exactement comme une offre standard. C'est
    précisément le chemin par lequel on survendrait sans s'en apercevoir.
    """
    changed = {}
    for field in OVERRIDE_FIELDS:
        if field not in overrides:
            continue
        value = overrides[field]
        if value != getattr(subscription, field):
            changed[field] = value

    if not changed:
        return subscription

    if "override_monitored_assets" in changed:
        new_quota = changed["override_monitored_assets"]
        effective = (
            subscription.plan.monitored_assets if new_quota is None else int(new_quota)
        )
        if subscription.is_operational and effective > subscription.monitored_assets_quota:
            capacity.ensure_monitored_slots_available(
                additional=effective, excluding_subscription_id=subscription.id
            )

    for field, value in changed.items():
        setattr(subscription, field, value)
    subscription.save(update_fields=[*changed.keys(), "updated_at"])

    _record_event(
        subscription,
        from_status=subscription.status,
        to_status=subscription.status,
        reason="Quotas négociés modifiés.",
        actor=actor,
    )
    capacity.check_alert_thresholds()
    return subscription


def set_internal_notes(*, subscription, notes: str) -> Subscription:
    subscription.internal_notes = notes
    subscription.save(update_fields=["internal_notes", "updated_at"])
    return subscription


# --- Catalogue : administration complète ------------------------------------

EDITABLE_PLAN_FIELDS = (
    "name",
    "tagline",
    "description",
    "price_monthly",
    "price_yearly",
    "currency",
    "is_quote_only",
    "status",
    "display_order",
    "is_highlighted",
    "monitored_assets",
    "monthly_scans",
    "max_users",
    "features",
)

QUOTA_FIELDS = ("monitored_assets", "monthly_scans", "max_users")


def snapshot_plan(plan) -> dict:
    return {field: getattr(plan, field) for field in EDITABLE_PLAN_FIELDS}


def plan_subscriber_count(plan) -> int:
    return Subscription.objects.filter(plan=plan).count()


def plan_impact(*, plan, changes: dict) -> dict:
    """Ce qui changerait pour les clients existants si l'on appliquait
    ``changes`` à ``plan``.

    Affiché AVANT confirmation. Sans cet aperçu, modifier une offre revient à
    modifier tous ses clients à l'aveugle — et la question « combien de clients
    est-ce que j'impacte ? » n'a aucune réponse accessible depuis l'interface.
    """
    subscriptions = list(
        Subscription.objects.filter(plan=plan).select_related("tenant", "plan")
    )
    rows = []
    lowered = []

    for field in QUOTA_FIELDS:
        if field not in changes:
            continue
        new_value = int(changes[field])
        old_value = getattr(plan, field)
        if new_value >= old_value and not (old_value == 0 and new_value != 0):
            continue
        # 0 signifie « illimité » : passer de 0 à une valeur finie est une
        # BAISSE, quel que soit le nombre.
        lowered.append(field)

    for subscription in subscriptions:
        affected = {}
        for field in QUOTA_FIELDS:
            if field not in changes:
                continue
            override = getattr(subscription, f"override_{field}")
            current = (
                override if override is not None else getattr(plan, field)
            )
            affected[field] = {
                "current": current,
                "after": current if override is not None else int(changes[field]),
                "frozen_by_override": override is not None,
            }
        rows.append(
            {
                "tenant_id": str(subscription.tenant_id),
                "tenant_name": subscription.tenant.name,
                "status": subscription.status,
                "quotas": affected,
            }
        )

    return {
        "subscriber_count": len(subscriptions),
        "lowered_quotas": lowered,
        "will_freeze_existing": bool(lowered) and bool(subscriptions),
        "tenants": rows,
    }


@transaction.atomic
def update_plan(*, plan, actor=None, **changes) -> tuple[Plan, dict, list[str]]:
    """Modifie une offre. Renvoie (offre, champs modifiés, clients gelés).

    **Décision (ADR-021) : une baisse de quota ne retire rien aux clients
    existants.** Chaque abonnement en cours reçoit une surcharge figeant son
    quota actuel ; le nouveau quota ne vaut que pour les futurs clients. Le
    raisonnement : un client a souscrit sur la foi d'un quota annoncé, et le
    lui reprendre sans préavis est une rupture unilatérale — alors qu'un
    tableau de bord soudain au-dessus de son quota est un incident que
    personne ne sait expliquer au support. Une hausse, elle, profite
    immédiatement à tout le monde.
    """
    from apps.platform_admin.services import diff_fields

    before = snapshot_plan(plan)
    impact = plan_impact(plan=plan, changes=changes)

    frozen = []
    if impact["will_freeze_existing"]:
        for subscription in Subscription.objects.filter(plan=plan).select_related("tenant"):
            fields_to_freeze = []
            for field in impact["lowered_quotas"]:
                if getattr(subscription, f"override_{field}") is None:
                    setattr(subscription, f"override_{field}", getattr(plan, field))
                    fields_to_freeze.append(f"override_{field}")
            if fields_to_freeze:
                subscription.save(update_fields=[*fields_to_freeze, "updated_at"])
                frozen.append(subscription.tenant.name)

    for field, value in changes.items():
        if field in EDITABLE_PLAN_FIELDS:
            setattr(plan, field, value)
    plan.save()

    return plan, diff_fields(before, snapshot_plan(plan)), frozen


@transaction.atomic
def duplicate_plan(*, plan, code: str, name: str) -> Plan:
    """Copie une offre en brouillon. Le point de départ le plus fréquent d'une
    nouvelle offre est une offre existante, pas une page blanche."""
    if Plan.objects.filter(code=code).exists():
        raise BillingError(f"Le code « {code} » est déjà utilisé par une autre offre.")

    clone = Plan.objects.get(pk=plan.pk)
    clone.pk = None
    clone.code = code
    clone.name = name
    # Une copie n'est jamais publiée ni mise en avant : on ne veut pas la voir
    # apparaître sur la vitrine avant d'avoir été relue.
    clone.status = Plan.Status.DRAFT
    clone.is_highlighted = False
    clone.display_order = plan.display_order + 1
    clone.save()
    return clone


def can_delete_plan(plan) -> tuple[bool, str]:
    """Un plan utilisé ne se supprime pas : ses abonnements y font référence,
    et l'historique de facturation deviendrait illisible. Il se RETIRE de la
    vente — invisible sur la vitrine, conservé pour les clients en cours."""
    count = plan_subscriber_count(plan)
    if count:
        return False, (
            f"{count} client(s) sont sur cette offre. Une offre utilisée ne peut pas être "
            "supprimée : retirez-la de la vente. Elle disparaîtra de la vitrine et "
            "restera valable pour ses clients actuels."
        )
    return True, ""


@transaction.atomic
def delete_plan(*, plan) -> str:
    allowed, message = can_delete_plan(plan)
    if not allowed:
        raise BillingError(message)
    name = plan.name
    plan.delete()
    return name


def render_payment_receipt_pdf(payment: Payment) -> bytes:
    """Justificatif simple. Import différé de WeasyPrint : la bibliothèque
    tire des dépendances système lourdes, et rien d'autre dans ce module n'en
    a besoin (même raison que apps.ai_assistant.services.render_document_pdf)."""
    import weasyprint
    from django.template.loader import render_to_string

    html = render_to_string("billing/payment_receipt.html", {"payment": payment})
    return weasyprint.HTML(string=html).write_pdf()
