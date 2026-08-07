from unittest.mock import patch

import pytest

from apps.threat_intelligence import services
from apps.threat_intelligence.models import BreachScanJob
from apps.threat_intelligence.tasks import run_breach_scan_task

pytestmark = pytest.mark.django_db


class TestRunBreachScanTask:
    def test_initial_trigger_without_job_still_scans(self, tenant, website_asset, fake_provider):
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            result = run_breach_scan_task(
                tenant_id=str(tenant.id), asset_id=website_asset.id, triggered_by="initial"
            )
        assert result["findings_created"] == 0

    def test_manual_trigger_with_job_marks_it_done(self, tenant, website_asset, fake_provider):
        job = services.create_scan_job(
            tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
        )
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            run_breach_scan_task(
                tenant_id=str(tenant.id),
                asset_id=website_asset.id,
                triggered_by="manual",
                job_id=job.id,
            )

        job.refresh_from_db()
        assert job.status == BreachScanJob.Status.DONE

    def test_redelivery_of_finished_job_is_a_noop(self, tenant, website_asset, fake_provider):
        job = services.create_scan_job(
            tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
        )
        services.mark_job_done(job)

        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            result = run_breach_scan_task(
                tenant_id=str(tenant.id),
                asset_id=website_asset.id,
                triggered_by="manual",
                job_id=job.id,
            )

        assert result is None

    def test_unknown_tenant_returns_none(self):
        result = run_breach_scan_task(tenant_id="00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_no_scannable_assets_marks_job_done_with_zero_findings(self, tenant):
        job = services.create_scan_job(tenant=tenant, triggered_by=services.TriggeredBy.MANUAL)

        run_breach_scan_task(tenant_id=str(tenant.id), triggered_by="manual", job_id=job.id)

        job.refresh_from_db()
        assert job.status == BreachScanJob.Status.DONE
        assert job.result_ref["findings_created"] == 0

    def test_failure_marks_job_failed_after_retries_exhausted(self, tenant, website_asset):
        job = services.create_scan_job(
            tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
        )
        # Simulates the task's own last attempt (retries == max_retries) via
        # Celery's request-context push, instead of mocking .retry() itself —
        # .retry() normally raises a control-flow Retry exception the worker
        # catches, so mocking it to raise plainly would misrepresent what
        # "retries exhausted" actually looks like to this code.
        run_breach_scan_task.push_request(retries=run_breach_scan_task.max_retries)
        try:
            with patch(
                "apps.threat_intelligence.services.execute_scan",
                side_effect=RuntimeError("boom"),
            ):
                run_breach_scan_task(
                    tenant_id=str(tenant.id),
                    asset_id=website_asset.id,
                    triggered_by="manual",
                    job_id=job.id,
                )
        finally:
            run_breach_scan_task.pop_request()

        job.refresh_from_db()
        assert job.status == BreachScanJob.Status.FAILED
        assert "boom" in job.error_message

    def test_transient_failure_retries_before_exhaustion(self, tenant, website_asset):
        job = services.create_scan_job(
            tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
        )
        with (
            patch(
                "apps.threat_intelligence.services.execute_scan",
                side_effect=RuntimeError("transient"),
            ),
            patch.object(
                run_breach_scan_task, "retry", side_effect=RuntimeError("retry-triggered")
            ) as mock_retry,
            pytest.raises(RuntimeError, match="retry-triggered"),
        ):
            run_breach_scan_task(
                tenant_id=str(tenant.id),
                asset_id=website_asset.id,
                triggered_by="manual",
                job_id=job.id,
            )

        mock_retry.assert_called_once()
        job.refresh_from_db()
        # Not marked failed yet — a retry is still pending, per CLAUDE.md's
        # idempotent/retryable task guidance.
        assert job.status == BreachScanJob.Status.RUNNING
