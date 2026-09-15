"""Celery tasks for the emails queue.

Idempotency: send_weather_email_for_tenant relies on
services._already_sent_today (backed by EmailLog) to make a redelivered
or duplicate-dispatched task a no-op instead of a second email — unlike
monitoring's checks, sending the same email twice would be a real user-
visible bug, not just a harmless extra data point.
"""

from celery import shared_task
from django.utils import timezone

from apps.tenants import services as tenants_services

from . import services


@shared_task
def send_due_weather_emails():
    """Beat-triggered every 15 minutes: finds tenants whose chosen weather
    time falls in the current window and enqueues one send per tenant."""
    now = timezone.localtime()
    dispatched = 0
    for prefs in services.list_preferences_due_for_weather(now):
        send_weather_email_for_tenant.delay(prefs.tenant_id)
        dispatched += 1
    return dispatched


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_weather_email_for_tenant(self, tenant_id):
    tenant = tenants_services.get_tenant(tenant_id)
    if tenant is None:
        return None
    try:
        message = services.send_weather_email(tenant)
    except Exception as exc:  # noqa: BLE001 - retry on anything unexpected
        raise self.retry(exc=exc) from exc
    return bool(message)


@shared_task
def notify_committee_reports():
    """Le 1er du mois : le rapport de comité du mois écoulé est prêt.

    Lot C, point 20. Le rapport existait (V2-3) mais personne n'était prévenu
    qu'il était temps de le présenter. Idempotent par construction : la clé
    ``comite:<client>:<mois>`` fait qu'une tâche relivrée, ou lancée deux fois
    à la main, ne prévient personne deux fois.
    """
    from . import inbox

    aujourd_hui = timezone.localdate()
    mois_ecoule = (aujourd_hui.replace(day=1) - timezone.timedelta(days=1)).replace(day=1)
    libelle = MOIS_FR[mois_ecoule.month - 1]
    prevenus = 0
    for tenant in tenants_services.list_active_tenants():
        prevenus += inbox.notify_tenant_admins(
            tenant,
            kind=inbox.Kind.COMMITTEE_REPORT_READY,
            title=f"Votre rapport de comité de {libelle} {mois_ecoule.year} est prêt",
            body=(
                "Les chiffres du mois écoulé, comparés à la période précédente, avec les faits "
                "marquants et ce qui reste à arbitrer. Prêt à présenter en PDF."
            ),
            link="/rapports",
            dedupe_key=f"comite:{tenant.id}:{mois_ecoule:%Y-%m}",
        )
    return prevenus


MOIS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_realtime_alert_email(self, alert_id):
    from apps.monitoring import services as monitoring_services

    alert = monitoring_services.get_alert(alert_id)
    if alert is None:
        return None
    try:
        message = services.send_realtime_alert_email(alert)
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc) from exc
    return bool(message)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_pre_incident_signal_email(self, finding_id):
    from apps.threat_intelligence.models import BreachFinding

    finding = (
        BreachFinding.all_objects.filter(id=finding_id).select_related("asset", "tenant").first()
    )
    if finding is None:
        return None
    try:
        message = services.send_pre_incident_signal_email(finding)
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc) from exc
    return bool(message)
