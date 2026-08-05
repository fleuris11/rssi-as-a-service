"""Public interface of the notifications app — other apps must go through
here instead of importing apps.notifications.models directly. Like
apps.monitoring, every function uses ``all_objects`` with an explicit
tenant filter, since Celery tasks have no ambient request context.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.ai_assistant import services as ai_assistant_services
from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Alert, CheckResult
from apps.tenants import services as tenants_services
from apps.tenants.models import Membership

from .models import EmailLog, NotificationPreferences

WEATHER_TIME_BUCKET_MINUTES = 15

_STATUS_RANK = {
    CheckResult.Status.OK: 0,
    CheckResult.Status.WARNING: 1,
    CheckResult.Status.CRITICAL: 2,
}
_MOOD_EMOJI = {
    CheckResult.Status.OK: "☀️",
    CheckResult.Status.WARNING: "⚠️",
    CheckResult.Status.CRITICAL: "🔴",
}
_MOOD_LABEL = {
    CheckResult.Status.OK: "Tout va bien",
    CheckResult.Status.WARNING: "Points à surveiller",
    CheckResult.Status.CRITICAL: "Action requise",
}


# --- Preferences -----------------------------------------------------------


def get_or_create_preferences(tenant) -> NotificationPreferences:
    prefs, _created = NotificationPreferences.all_objects.get_or_create(tenant=tenant)
    return prefs


def update_preferences(tenant, **fields) -> NotificationPreferences:
    prefs = get_or_create_preferences(tenant)
    for key, value in fields.items():
        setattr(prefs, key, value)
    prefs.save()
    return prefs


def list_preferences_due_for_weather(now):
    """Preferences whose chosen weather_time falls in the current
    ~15-minute dispatch window — a once-a-day digest doesn't need
    to-the-minute precision."""
    due = []
    for prefs in NotificationPreferences.all_objects.filter(weather_enabled=True).select_related(
        "tenant"
    ):
        same_hour = prefs.weather_time.hour == now.hour
        same_bucket = (
            prefs.weather_time.minute // WEATHER_TIME_BUCKET_MINUTES
            == now.minute // WEATHER_TIME_BUCKET_MINUTES
        )
        if same_hour and same_bucket:
            due.append(prefs)
    return due


def list_recipient_emails(tenant) -> list[str]:
    """Weather/alert emails go to the tenant's admins — the account
    owner(s) — not every contributor/reader, to avoid flooding inboxes."""
    return list(
        tenants_services.list_members(tenant)
        .filter(role=Membership.Role.ADMIN)
        .values_list("user__email", flat=True)
    )


# --- Sending -----------------------------------------------------------------


def _already_sent_today(tenant, kind: str) -> bool:
    return EmailLog.all_objects.filter(
        tenant=tenant, kind=kind, sent_at__date=timezone.localdate()
    ).exists()


def _send_email(*, tenant, kind: str, recipients, subject, text_body, html_body, details=None):
    if not recipients:
        return None
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        to=recipients,
        from_email=settings.DEFAULT_FROM_EMAIL,
    )
    message.attach_alternative(html_body, "text/html")
    message.send()
    for recipient in recipients:
        EmailLog.all_objects.create(
            tenant=tenant, kind=kind, recipient=recipient, subject=subject, details=details or {}
        )
    return message


# --- Météo cyber quotidienne -------------------------------------------------


def build_weather_context(tenant) -> dict:
    dashboard = monitoring_services.get_tenant_dashboard(tenant)
    open_alerts = list(monitoring_services.list_open_alerts(tenant))

    asset_rows = []
    worst = CheckResult.Status.OK
    for row in dashboard:
        checks_summary = []
        for result in row["latest_checks"].values():
            if result is None:
                continue
            checks_summary.append(
                {
                    "label": CheckResult.CheckType(result.check_type).label,
                    "status_label": CheckResult.Status(result.status).label,
                    "status": result.status,
                }
            )
            if _STATUS_RANK[result.status] > _STATUS_RANK[worst]:
                worst = result.status
        asset_rows.append(
            {
                "value": row["asset"].value,
                "type_label": row["asset"].get_type_display(),
                "uptime_24h": row["uptime_24h"],
                "checks": checks_summary,
            }
        )

    if open_alerts:
        if any(a.severity == Alert.Severity.CRITICAL for a in open_alerts):
            worst = CheckResult.Status.CRITICAL
        elif _STATUS_RANK[worst] < _STATUS_RANK[CheckResult.Status.WARNING]:
            worst = CheckResult.Status.WARNING

    alert_rows = [
        {
            "asset_value": alert.asset.value,
            "type_label": alert.get_alert_type_display(),
            "severity_label": alert.get_severity_display(),
        }
        for alert in open_alerts
    ]

    context = {
        "tenant_name": tenant.name,
        "date": timezone.localdate(),
        "mood_emoji": _MOOD_EMOJI[worst],
        "mood_label": _MOOD_LABEL[worst],
        "assets": asset_rows,
        "open_alerts": alert_rows,
        "dashboard_url": f"{settings.FRONTEND_BASE_URL}/surveillance",
    }
    context["enriched_summary"] = _maybe_enrich_weather_summary(tenant, context)
    return context


def _maybe_enrich_weather_summary(tenant, context: dict) -> str | None:
    """Cas d'usage 3 (optionnel par tenant) : reformulation Haiku du résumé
    déterministe via le pipeline de pseudonymisation d'ai_assistant. Renvoie
    toujours ``None`` proprement (jamais d'exception) si désactivé, si le
    tenant n'a pas activé l'IA, si le quota est dépassé ou si l'appel
    échoue — apps.notifications.services.enrich_weather_summary garantit
    déjà ce comportement, mais le template déterministe (déjà construit
    dans ``context``) reste dans tous les cas le contenu envoyé si ce champ
    est vide : la météo part toujours (CLAUDE.md)."""
    prefs = get_or_create_preferences(tenant)
    if not prefs.weather_enrichment_enabled:
        return None
    deterministic_context = {
        "synthese": context["mood_label"],
        "actifs": [
            {
                "type": asset["type_label"],
                "valeur": asset["value"],
                "disponibilite_24h": asset["uptime_24h"],
                "checks": asset["checks"],
            }
            for asset in context["assets"]
        ],
        "alertes_ouvertes": context["open_alerts"],
    }
    return ai_assistant_services.enrich_weather_summary(
        tenant=tenant, deterministic_context=deterministic_context
    )


def send_weather_email(tenant):
    if _already_sent_today(tenant, EmailLog.Kind.WEATHER):
        return None
    recipients = list_recipient_emails(tenant)
    if not recipients:
        return None

    context = build_weather_context(tenant)
    subject = f"{context['mood_emoji']} Météo cyber — {tenant.name} — {context['date']:%d/%m/%Y}"
    text_body = render_to_string("notifications/weather_email.txt", context)
    html_body = render_to_string("notifications/weather_email.html", context)

    return _send_email(
        tenant=tenant,
        kind=EmailLog.Kind.WEATHER,
        recipients=recipients,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        details={"mood": context["mood_label"], "ai_enriched": bool(context["enriched_summary"])},
    )


# --- Alertes temps réel (US-5.6) ---------------------------------------------


def send_realtime_alert_email(alert: Alert):
    tenant = alert.tenant
    prefs = get_or_create_preferences(tenant)
    if not prefs.realtime_alerts_enabled:
        return None
    recipients = list_recipient_emails(tenant)
    if not recipients:
        return None

    context = {
        "tenant_name": tenant.name,
        "asset_value": alert.asset.value,
        "alert_type_label": alert.get_alert_type_display(),
        "severity_label": alert.get_severity_display(),
        "details": alert.details,
        "dashboard_url": f"{settings.FRONTEND_BASE_URL}/surveillance",
    }
    subject = f"🔴 Alerte — {alert.asset.value} — {alert.get_alert_type_display()}"
    text_body = render_to_string("notifications/realtime_alert_email.txt", context)
    html_body = render_to_string("notifications/realtime_alert_email.html", context)

    return _send_email(
        tenant=tenant,
        kind=EmailLog.Kind.REALTIME_ALERT,
        recipients=recipients,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        details={"alert_id": alert.id, "alert_type": alert.alert_type},
    )
