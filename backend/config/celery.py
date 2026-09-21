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
    # Lot C, point 20 : le 1er du mois à 7 h, le rapport de comité du mois
    # écoulé est signalé dans l'application. Idempotent (clé par client et
    # par mois) : une relivraison ne prévient personne deux fois.
    "notifications-committee-reports": {
        "task": "apps.notifications.tasks.notify_committee_reports",
        "schedule": crontab(day_of_month="1", hour="7", minute="0"),
    },
    # Politique de rétention des secrets de fuite (Phase 8C, ADR-014). Une
    # fois par jour suffit : le délai se compte en dizaines de jours, et la
    # tâche est idempotente (une seconde passe ne trouve plus rien).
    # Heure creuse volontairement, la purge fait un UPDATE de masse.
    # Veille réglementaire (V2-7). Une fois par semaine, le lundi matin :
    # les autorités publient à la journée, pas à la minute, et promettre du
    # temps réel serait mentir (ADR-034 §6). Un passage hebdomadaire suffit
    # à ne rien manquer et coûte cinq requêtes HTTP.
    "regulatory-watch-poll-sources": {
        "task": "apps.regulatory_watch.tasks.poll_sources_task",
        "schedule": crontab(day_of_week="1", hour="6", minute="15"),
    },
    "threat-intelligence-purge-expired-secrets": {
        "task": "apps.threat_intelligence.tasks.purge_expired_secrets_task",
        "schedule": crontab(hour="3", minute="30"),
    },
    # Formation (F3). Les relances partent une fois par jour, en milieu de
    # matinée : un message de formation reçu à 3 h du matin se lit mal, et une
    # relance se compte en jours, jamais en heures. Idempotente — la
    # contrainte d'unicité en base empêche un second envoi le même jour.
    "training-envoyer-les-relances": {
        "task": "apps.training.tasks.envoyer_les_relances",
        "schedule": crontab(hour="9", minute="30"),
    },
    # Les propositions de preuve pour le diagnostic, et les trois événements
    # du centre de notifications. Rien n'est coché automatiquement (ADR-041).
    "training-proposer-les-preuves": {
        "task": "apps.training.tasks.proposer_les_preuves",
        "schedule": crontab(hour="6", minute="45"),
    },
    "training-surveiller-les-campagnes": {
        "task": "apps.training.tasks.surveiller_les_campagnes",
        "schedule": crontab(hour="7", minute="15"),
    },
    # Durée de conservation des résultats détaillés (ADR-041). Une fois par
    # mois : c'est une obligation de rétention, pas une urgence.
    "training-purger-les-resultats": {
        "task": "apps.training.tasks.purger_les_resultats",
        "schedule": crontab(day_of_month="2", hour="4", minute="0"),
    },
}
