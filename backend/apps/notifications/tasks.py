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
