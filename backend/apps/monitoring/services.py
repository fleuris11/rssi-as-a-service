"""Public interface of the monitoring app — other apps (and Celery tasks)
must go through here instead of importing apps.monitoring.models
directly. Like apps.assessments/apps.actions, every function is given an
already-resolved tenant/asset, so it consistently uses ``all_objects``
with an explicit ``tenant=`` filter rather than the request-scoped one.
"""

from datetime import timedelta
from urllib.parse import urlparse

from django.core.cache import cache
from django.db.models import Max, Q
from django.utils import timezone

from .checks.email_dns import check_email_dns
from .checks.http_uptime import check_http_uptime
from .checks.security_headers import check_security_headers
from .checks.ssl_certificate import check_ssl_certificate
from .models import Alert, Asset, CheckResult

# Written every minute by tasks.heartbeat (Beat + a worker on the
# monitoring queue), read by config.views.healthz_worker — proves the
# whole scheduling chain is alive end to end, not just that a process
# is running.
HEARTBEAT_CACHE_KEY = "monitoring:worker_heartbeat"
HEARTBEAT_CACHE_TIMEOUT_SECONDS = 180  # 3x the 1-minute beat schedule


class MonitoringError(Exception):
    """Base class for business-rule violations raised by this module."""


class InvalidAssetError(MonitoringError):
    pass


# CLAUDE.md: "Alerte monitoring : confirmer un DOWN par 3 échecs consécutifs
# avant d'alerter (anti faux positifs)."
CONSECUTIVE_FAILURES_FOR_DOWN = 3

# US-5.3: "alerte anticipée (30/14/7 jours)" — each is a distinct
# notification point on the same still-open alert, not three alert rows.
SSL_NOTIFY_THRESHOLDS = [30, 14, 7]

CHECK_INTERVALS = {
    CheckResult.CheckType.HTTP_UPTIME: timedelta(minutes=5),
    CheckResult.CheckType.SSL_CERTIFICATE: timedelta(hours=24),
    CheckResult.CheckType.SECURITY_HEADERS: timedelta(hours=24),
    CheckResult.CheckType.EMAIL_DNS: timedelta(hours=24),
}

CHECK_TYPES_BY_ASSET_TYPE = {
    Asset.Type.WEBSITE: [
        CheckResult.CheckType.HTTP_UPTIME,
        CheckResult.CheckType.SSL_CERTIFICATE,
        CheckResult.CheckType.SECURITY_HEADERS,
    ],
    Asset.Type.EMAIL_DOMAIN: [CheckResult.CheckType.EMAIL_DNS],
}


# --- Assets ------------------------------------------------------------


def create_asset(*, tenant, user, type: str, value: str, ownership_confirmed: bool) -> Asset:
    if not ownership_confirmed:
        raise InvalidAssetError(
            "La case d'engagement de propriété doit être cochée pour déclarer un actif."
        )
    return Asset.all_objects.create(
        tenant=tenant,
        type=type,
        value=value,
        ownership_confirmed=True,
        created_by=user,
    )


def list_assets(tenant):
    return Asset.all_objects.filter(tenant=tenant).order_by("-created_at")


def get_asset(*, tenant, asset_id):
    return Asset.all_objects.filter(tenant=tenant, id=asset_id).first()


def set_asset_active(asset: Asset, is_active: bool) -> Asset:
    asset.is_active = is_active
    asset.save(update_fields=["is_active"])
    return asset


def delete_asset(asset: Asset) -> None:
    asset.delete()


# --- Running checks ------------------------------------------------------


def list_due_assets(check_type: str):
    """Active assets of a type this check applies to, never checked (for
    this check_type) or last checked longer ago than its interval."""
    interval = CHECK_INTERVALS[check_type]
    cutoff = timezone.now() - interval
    applicable_asset_types = [
        asset_type
        for asset_type, check_types in CHECK_TYPES_BY_ASSET_TYPE.items()
        if check_type in check_types
    ]
    return list(
        Asset.all_objects.filter(is_active=True, type__in=applicable_asset_types)
        .annotate(
            last_checked_at=Max(
                "check_results__checked_at",
                filter=Q(check_results__check_type=check_type),
            )
        )
        .filter(Q(last_checked_at__isnull=True) | Q(last_checked_at__lte=cutoff))
    )


def run_check(asset: Asset, check_type: str) -> tuple[CheckResult, Alert | None]:
    """Runs one check for ``asset``, records the result, and evaluates the
    alert engine. Returns ``(check_result, alert)`` — ``alert`` is only set
    when a *new* alert opened or an SSL threshold was newly crossed, i.e.
    when a real-time notification (US-5.6) is warranted."""
    if check_type == CheckResult.CheckType.HTTP_UPTIME:
        result = check_http_uptime(asset.value)
    elif check_type == CheckResult.CheckType.SSL_CERTIFICATE:
        hostname = urlparse(asset.value).hostname or asset.value
        result = check_ssl_certificate(hostname)
    elif check_type == CheckResult.CheckType.SECURITY_HEADERS:
        result = check_security_headers(asset.value)
    elif check_type == CheckResult.CheckType.EMAIL_DNS:
        result = check_email_dns(asset.value)
    else:
        raise MonitoringError(f"Type de check inconnu : {check_type!r}")

    check_result = CheckResult.all_objects.create(
        tenant=asset.tenant,
        asset=asset,
        check_type=check_type,
        status=result["status"],
        details=result.get("details", {}),
        latency_ms=result.get("latency_ms"),
    )
    notify_alert = evaluate_alerts(asset=asset, check_type=check_type, latest_result=check_result)
    return check_result, notify_alert


def simulate_check_result(
    asset: Asset, *, check_type: str, status: str, details: dict | None = None
) -> tuple[CheckResult, Alert | None]:
    """Injects a CheckResult without performing a live network check, then
    runs it through the same alert engine as ``run_check``. Used by the
    ``simulate_check_failure`` management command (E2E tests, demos) to
    exercise the alerting pipeline without depending on a real external
    target being actually down."""
    check_result = CheckResult.all_objects.create(
        tenant=asset.tenant,
        asset=asset,
        check_type=check_type,
        status=status,
        details=details or {},
    )
    alert = evaluate_alerts(asset=asset, check_type=check_type, latest_result=check_result)
    return check_result, alert


# --- Alert engine ----------------------------------------------------------


def _open_or_update_alert(asset: Asset, alert_type: str, severity: str, details: dict):
    """Returns (alert, created) — "created" also True when severity/details
    changed on an already-open alert (an escalation), so callers can treat
    both as "state changed, maybe notify"."""
    alert = Alert.all_objects.filter(asset=asset, alert_type=alert_type, is_open=True).first()
    if alert is None:
        alert = Alert.all_objects.create(
            tenant=asset.tenant,
            asset=asset,
            alert_type=alert_type,
            severity=severity,
            details=details,
        )
        return alert, True
    changed = alert.severity != severity or alert.details != details
    if changed:
        alert.severity = severity
        alert.details = details
        alert.save(update_fields=["severity", "details", "updated_at"])
    return alert, changed


def open_or_update_alert(*, asset: Asset, alert_type: str, severity: str, details: dict) -> Alert:
    """Public entry point for other apps that need to open/escalate an
    alert on a tenant's asset through this module's dedup/escalation
    engine, without duplicating it (Phase 7, ADR-013:
    apps.threat_intelligence calls this for breach-compromise alerts). The
    check-specific ``evaluate_alerts``/``_evaluate_*`` functions above stay
    private — they're only ever driven by this module's own CheckResults —
    this wrapper is for alert types with no CheckResult behind them."""
    alert, _created = _open_or_update_alert(asset, alert_type, severity, details)
    return alert


def _resolve_alert(asset: Asset, alert_type: str) -> None:
    Alert.all_objects.filter(asset=asset, alert_type=alert_type, is_open=True).update(
        is_open=False, resolved_at=timezone.now()
    )


def evaluate_alerts(*, asset: Asset, check_type: str, latest_result: CheckResult) -> Alert | None:
    if check_type == CheckResult.CheckType.HTTP_UPTIME:
        return _evaluate_down_alert(asset)
    if check_type == CheckResult.CheckType.SSL_CERTIFICATE:
        return _evaluate_ssl_alert(asset, latest_result)
    if check_type == CheckResult.CheckType.SECURITY_HEADERS:
        return _evaluate_headers_alert(asset, latest_result)
    if check_type == CheckResult.CheckType.EMAIL_DNS:
        return _evaluate_email_alert(asset, latest_result)
    return None


def _evaluate_down_alert(asset: Asset) -> Alert | None:
    recent = list(
        CheckResult.all_objects.filter(
            tenant=asset.tenant, asset=asset, check_type=CheckResult.CheckType.HTTP_UPTIME
        ).order_by("-checked_at")[:CONSECUTIVE_FAILURES_FOR_DOWN]
    )
    if not recent:
        return None

    if recent[0].status == CheckResult.Status.OK:
        _resolve_alert(asset, Alert.AlertType.DOWN)
        return None

    if len(recent) < CONSECUTIVE_FAILURES_FOR_DOWN:
        return None  # not enough history yet — anti-false-positive

    if all(r.status == CheckResult.Status.CRITICAL for r in recent):
        alert, created = _open_or_update_alert(
            asset,
            Alert.AlertType.DOWN,
            Alert.Severity.CRITICAL,
            {
                "consecutive_failures": CONSECUTIVE_FAILURES_FOR_DOWN,
                "last_error": recent[0].details.get("error"),
            },
        )
        return alert if created else None
    return None


def _evaluate_ssl_alert(asset: Asset, latest_result: CheckResult) -> Alert | None:
    days_left = latest_result.details.get("days_left")
    if days_left is None:
        return None  # certificate fetch failed — no expiry-specific alert to raise

    if days_left > max(SSL_NOTIFY_THRESHOLDS):
        _resolve_alert(asset, Alert.AlertType.SSL_EXPIRING)
        return None

    severity = (
        Alert.Severity.CRITICAL
        if days_left <= min(SSL_NOTIFY_THRESHOLDS)
        else Alert.Severity.WARNING
    )

    existing = Alert.all_objects.filter(
        asset=asset, alert_type=Alert.AlertType.SSL_EXPIRING, is_open=True
    ).first()
    already_notified = set(existing.details.get("notified_thresholds", [])) if existing else set()
    newly_crossed = {t for t in SSL_NOTIFY_THRESHOLDS if days_left <= t} - already_notified
    if not newly_crossed:
        return None  # already alerted for this threshold, don't re-notify

    notified_thresholds = sorted(already_notified | newly_crossed)
    alert, _created = _open_or_update_alert(
        asset,
        Alert.AlertType.SSL_EXPIRING,
        severity,
        {
            "days_left": days_left,
            "expires_at": latest_result.details.get("expires_at"),
            "notified_thresholds": notified_thresholds,
        },
    )
    return alert


def _evaluate_headers_alert(asset: Asset, latest_result: CheckResult) -> Alert | None:
    missing = latest_result.details.get("missing", [])
    if not missing:
        _resolve_alert(asset, Alert.AlertType.SECURITY_HEADERS)
        return None
    alert, created = _open_or_update_alert(
        asset,
        Alert.AlertType.SECURITY_HEADERS,
        Alert.Severity.WARNING,
        {"missing": [m["header"] for m in missing]},
    )
    return alert if created else None


def _evaluate_email_alert(asset: Asset, latest_result: CheckResult) -> Alert | None:
    issues = latest_result.details.get("issues", [])
    if not issues:
        _resolve_alert(asset, Alert.AlertType.EMAIL_MISCONFIGURED)
        return None
    severity = (
        Alert.Severity.CRITICAL
        if latest_result.status == CheckResult.Status.CRITICAL
        else Alert.Severity.WARNING
    )
    alert, created = _open_or_update_alert(
        asset, Alert.AlertType.EMAIL_MISCONFIGURED, severity, {"issues": issues}
    )
    return alert if created else None


# --- Dashboard / reporting -------------------------------------------------


def list_open_alerts(tenant):
    return (
        Alert.all_objects.filter(tenant=tenant, is_open=True)
        .select_related("asset")
        .order_by("-opened_at")
    )


def get_alert(alert_id):
    """Looked up by primary key alone (no tenant filter) — for the
    notifications Celery task, which receives only an alert_id and hasn't
    resolved a tenant yet at that point."""
    return Alert.all_objects.filter(id=alert_id).select_related("asset", "tenant").first()


def get_latest_check(asset: Asset, check_type: str) -> CheckResult | None:
    return (
        CheckResult.all_objects.filter(tenant=asset.tenant, asset=asset, check_type=check_type)
        .order_by("-checked_at")
        .first()
    )


def compute_uptime_percentage(asset: Asset, *, hours: int = 24) -> float | None:
    since = timezone.now() - timedelta(hours=hours)
    results = CheckResult.all_objects.filter(
        tenant=asset.tenant,
        asset=asset,
        check_type=CheckResult.CheckType.HTTP_UPTIME,
        checked_at__gte=since,
    )
    total = results.count()
    if total == 0:
        return None
    ok = results.filter(status=CheckResult.Status.OK).count()
    return round(100 * ok / total, 1)


def get_asset_dashboard(asset: Asset) -> dict:
    latest_checks = {
        check_type: get_latest_check(asset, check_type)
        for check_type in CHECK_TYPES_BY_ASSET_TYPE.get(asset.type, [])
    }
    return {
        "asset": asset,
        "latest_checks": latest_checks,
        "uptime_24h": compute_uptime_percentage(asset, hours=24)
        if asset.type == Asset.Type.WEBSITE
        else None,
        "open_alerts": list(
            Alert.all_objects.filter(tenant=asset.tenant, asset=asset, is_open=True)
        ),
    }


def get_tenant_dashboard(tenant) -> list[dict]:
    return [get_asset_dashboard(asset) for asset in list_assets(tenant)]


# --- Worker health -----------------------------------------------------------


def record_heartbeat() -> None:
    cache.set(
        HEARTBEAT_CACHE_KEY, timezone.now().isoformat(), timeout=HEARTBEAT_CACHE_TIMEOUT_SECONDS
    )


def is_worker_healthy() -> tuple[bool, str | None]:
    """(healthy, last_seen_iso). Unhealthy if Beat/the monitoring worker
    haven't produced a heartbeat recently enough — proves the whole
    scheduling chain end to end, not just that a process exists."""
    last_seen = cache.get(HEARTBEAT_CACHE_KEY)
    return last_seen is not None, last_seen
