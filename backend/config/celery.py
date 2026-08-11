"""Celery application for the RSSI as a Service backend.

Workers never run AI calls or network checks inside the HTTP
request/response cycle (CLAUDE.md) — this is the entry point for
everything that does, split into dedicated queues (``monitoring``,
``emails``, ``ai``) so a slow/failing queue doesn't starve the others.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("rssi_as_service")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Static schedule (not django-celery-beat's DB-backed one): entries here are
# fixed application behaviour, not something a tenant or admin edits at
# runtime — a plain Python dict is simpler to read, review and test.
app.conf.beat_schedule = {
    "monitoring-dispatch-due-checks": {
        "task": "apps.monitoring.tasks.dispatch_due_checks",
        "schedule": crontab(minute="*/5"),
    },
    "monitoring-worker-heartbeat": {
        "task": "apps.monitoring.tasks.heartbeat",
        "schedule": crontab(minute="*"),
    },
    "notifications-send-due-weather-emails": {
        "task": "apps.notifications.tasks.send_due_weather_emails",
        "schedule": crontab(minute="*/15"),
    },
    # Politique de rétention des secrets de fuite (Phase 8C, ADR-014). Une
    # fois par jour suffit : le délai se compte en dizaines de jours, et la
    # tâche est idempotente (une seconde passe ne trouve plus rien).
    # Heure creuse volontairement, la purge fait un UPDATE de masse.
    "threat-intelligence-purge-expired-secrets": {
        "task": "apps.threat_intelligence.tasks.purge_expired_secrets_task",
        "schedule": crontab(hour="3", minute="30"),
    },
}
