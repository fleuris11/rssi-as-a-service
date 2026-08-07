"""Celery tasks for the monitoring queue (ADR-013: le CTI est un
sous-domaine de la surveillance, pas de l'IA). Orchestration only — the
actual scan/ingestion logic lives in services.py, independently
unit-testable without Celery (CLAUDE.md: "les tasks Celery... orchestrent,
les services.py contiennent la logique").

Idempotency: guards on the job's current status (mirrors
apps.ai_assistant.tasks) so a redelivery of an already-finished job is a
no-op — a scan is neither free (it burns query quota) nor safely
repeatable to redo silently.

The webhook itself (POST /api/v1/webhooks/breachsense) is handled
synchronously in the view, not via a task: ingestion here makes no
outbound network call (we're the receiver), and idempotency is already
guaranteed at the DB level by BreachFinding's unique dedup_hash
constraint — routing it through Celery would only add latency to
Breachsense's delivery without any correctness benefit.
"""

import logging

from celery import shared_task

from apps.monitoring.models import Asset
from apps.tenants import services as tenants_services

from . import services
from .models import BreachScanJob

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def run_breach_scan_task(self, tenant_id, asset_id=None, triggered_by="manual", job_id=None):
    tenant = tenants_services.get_tenant(tenant_id)
    if tenant is None:
        return None

    job = None
    if job_id is not None:
        job = BreachScanJob.all_objects.filter(id=job_id).first()
        if job is None or job.status in (BreachScanJob.Status.DONE, BreachScanJob.Status.FAILED):
            return None
        services.mark_job_running(job)

    asset = Asset.all_objects.filter(id=asset_id).first() if asset_id else None
    assets = services.scannable_assets(tenant, asset=asset)
    if not assets:
        if job is not None:
            services.mark_job_done(job, {"findings_created": 0})
        return None

    try:
        result = services.execute_scan(tenant=tenant, assets=assets, triggered_by=triggered_by)
    except Exception as exc:  # noqa: BLE001 - retry on anything unexpected
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        logger.warning(
            "Échec définitif du scan Breachsense pour le tenant %s : %s",
            tenant_id,
            exc,
            exc_info=True,
        )
        if job is not None:
            services.mark_job_failed(job, str(exc))
        return None

    if job is not None:
        services.mark_job_done(job, result)
    return result
