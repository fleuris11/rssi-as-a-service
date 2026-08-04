"""Celery tasks for the monitoring queue. Orchestration only — the actual
check/alert logic lives in services.py and checks/*.py, both directly
unit-testable without Celery.

Idempotency: each check simply records a new timestamped CheckResult:
running the same (asset, check_type) task twice produces two close-in-time
observations, not a corrupted or duplicated *state* — an at-least-once
redelivery (ACKS_LATE) is harmless here, unlike e.g. sending an email
twice. list_due_assets() also naturally stops re-dispatching an asset
once a fresh-enough result exists for it.
"""

import logging

from celery import shared_task

from . import services
from .models import Asset, CheckResult

logger = logging.getLogger(__name__)


@shared_task
def heartbeat():
    """Proves Beat *and* a worker on the monitoring queue are both alive —
    see config.views.healthz_worker."""
    services.record_heartbeat()


@shared_task
def dispatch_due_checks():
    """Beat-triggered: for each check type, finds assets due for it and
    enqueues one run_single_check task per asset — never runs the network
    check itself (keeps this task fast and queue-agnostic)."""
    dispatched = 0
    for check_type in CheckResult.CheckType.values:
        for asset in services.list_due_assets(check_type):
            run_single_check.delay(asset.id, check_type)
            dispatched += 1
    return dispatched


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def run_single_check(self, asset_id: int, check_type: str):
    """Runs one check for one asset. Retries on unexpected errors (e.g. a
    transient DB hiccup) — network failures of the check *itself* are
    caught inside checks/*.py and recorded as a CRITICAL CheckResult, not
    raised, so they never land here."""
    asset = Asset.all_objects.filter(id=asset_id).first()
    if asset is None or not asset.is_active:
        return None

    try:
        _check_result, alert = services.run_check(asset, check_type)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: retry on anything unexpected
        logger.warning("Échec du check %s pour l'actif %s : %s", check_type, asset_id, exc)
        raise self.retry(exc=exc) from exc

    if alert is not None:
        from apps.notifications.tasks import send_realtime_alert_email

        send_realtime_alert_email.delay(alert.id)
