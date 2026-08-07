from unittest.mock import patch

import pytest

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset

pytestmark = pytest.mark.django_db


class TestInitialScanSignal:
    def test_declaring_a_website_asset_triggers_initial_scan(self, tenant, tenant_owner):
        with patch("apps.threat_intelligence.tasks.run_breach_scan_task.delay") as mock_delay:
            asset = monitoring_services.create_asset(
                tenant=tenant,
                user=tenant_owner,
                type=Asset.Type.WEBSITE,
                value="https://example.com",
                ownership_confirmed=True,
            )

        mock_delay.assert_called_once_with(
            tenant_id=str(tenant.id), asset_id=asset.id, triggered_by="initial"
        )

    def test_declaring_an_email_domain_asset_triggers_initial_scan(self, tenant, tenant_owner):
        with patch("apps.threat_intelligence.tasks.run_breach_scan_task.delay") as mock_delay:
            monitoring_services.create_asset(
                tenant=tenant,
                user=tenant_owner,
                type=Asset.Type.EMAIL_DOMAIN,
                value="example.com",
                ownership_confirmed=True,
            )

        mock_delay.assert_called_once()

    def test_updating_an_existing_asset_does_not_retrigger_scan(self, tenant, tenant_owner):
        asset = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.WEBSITE,
            value="https://example.com",
            ownership_confirmed=True,
        )
        with patch("apps.threat_intelligence.tasks.run_breach_scan_task.delay") as mock_delay:
            monitoring_services.set_asset_active(asset, False)

        mock_delay.assert_not_called()

    def test_scan_scheduling_failure_does_not_break_asset_creation(self, tenant, tenant_owner):
        with patch(
            "apps.threat_intelligence.tasks.run_breach_scan_task.delay",
            side_effect=RuntimeError("broker down"),
        ):
            asset = monitoring_services.create_asset(
                tenant=tenant,
                user=tenant_owner,
                type=Asset.Type.WEBSITE,
                value="https://example.com",
                ownership_confirmed=True,
            )

        assert asset.id is not None  # declaration itself must not fail
