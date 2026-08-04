from unittest.mock import patch

import pytest
from django.core.cache import cache

from apps.monitoring import services, tasks
from apps.monitoring.models import Asset, CheckResult

pytestmark = pytest.mark.django_db


@pytest.fixture
def website_asset(tenant, tenant_owner):
    return services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://example.com",
        ownership_confirmed=True,
    )


class TestHeartbeat:
    def test_writes_a_recent_timestamp(self):
        cache.delete(services.HEARTBEAT_CACHE_KEY)
        assert services.is_worker_healthy() == (False, None)

        tasks.heartbeat()

        healthy, last_seen = services.is_worker_healthy()
        assert healthy is True
        assert last_seen is not None


class TestDispatchDueChecks:
    def test_dispatches_one_task_per_due_asset_and_check_type(self, website_asset):
        with patch("apps.monitoring.tasks.run_single_check.delay") as mock_delay:
            dispatched = tasks.dispatch_due_checks()

        # A never-checked website asset is due for all 3 of its check types.
        assert dispatched == 3
        dispatched_types = {call.args[1] for call in mock_delay.call_args_list}
        assert dispatched_types == {
            CheckResult.CheckType.HTTP_UPTIME,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.CheckType.SECURITY_HEADERS,
        }

    def test_does_not_redispatch_a_freshly_checked_asset(self, website_asset):
        for check_type in [
            CheckResult.CheckType.HTTP_UPTIME,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.CheckType.SECURITY_HEADERS,
        ]:
            CheckResult.all_objects.create(
                tenant=website_asset.tenant,
                asset=website_asset,
                check_type=check_type,
                status=CheckResult.Status.OK,
            )

        with patch("apps.monitoring.tasks.run_single_check.delay") as mock_delay:
            dispatched = tasks.dispatch_due_checks()

        assert dispatched == 0
        mock_delay.assert_not_called()


class TestRunSingleCheck:
    def test_records_a_check_result(self, website_asset):
        fake_result = {"status": CheckResult.Status.OK, "latency_ms": 42.0, "details": {}}
        with patch("apps.monitoring.services.check_http_uptime", return_value=fake_result):
            tasks.run_single_check(website_asset.id, CheckResult.CheckType.HTTP_UPTIME)

        assert CheckResult.all_objects.filter(
            asset=website_asset, check_type=CheckResult.CheckType.HTTP_UPTIME
        ).exists()

    def test_skips_inactive_asset(self, website_asset):
        services.set_asset_active(website_asset, False)
        with patch("apps.monitoring.services.check_http_uptime") as mock_check:
            tasks.run_single_check(website_asset.id, CheckResult.CheckType.HTTP_UPTIME)

        mock_check.assert_not_called()

    def test_notifies_when_a_new_alert_opens(self, website_asset):
        for _ in range(2):
            CheckResult.all_objects.create(
                tenant=website_asset.tenant,
                asset=website_asset,
                check_type=CheckResult.CheckType.HTTP_UPTIME,
                status=CheckResult.Status.CRITICAL,
            )
        fake_result = {
            "status": CheckResult.Status.CRITICAL,
            "latency_ms": None,
            "details": {"error": "refused"},
        }
        with (
            patch("apps.monitoring.services.check_http_uptime", return_value=fake_result),
            patch("apps.notifications.tasks.send_realtime_alert_email.delay") as mock_notify,
        ):
            tasks.run_single_check(website_asset.id, CheckResult.CheckType.HTTP_UPTIME)

        mock_notify.assert_called_once()
