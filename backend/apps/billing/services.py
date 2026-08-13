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


def render_payment_receipt_pdf(payment: Payment) -> bytes:
    """Justificatif simple. Import différé de WeasyPrint : la bibliothèque
    tire des dépendances système lourdes, et rien d'autre dans ce module n'en
    a besoin (même raison que apps.ai_assistant.services.render_document_pdf)."""
    import weasyprint
    from django.template.loader import render_to_string

    html = render_to_string("billing/payment_receipt.html", {"payment": payment})
    return weasyprint.HTML(string=html).write_pdf()
