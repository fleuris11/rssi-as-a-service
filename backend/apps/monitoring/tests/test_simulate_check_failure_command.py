from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.monitoring import services
from apps.monitoring.models import Alert, Asset

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


class TestSimulateCheckFailureCommand:
    def test_opens_a_down_alert_for_the_declared_asset(self, tenant, website_asset):
        out = StringIO()
        call_command(
            "simulate_check_failure",
            "--tenant-slug",
            tenant.slug,
            "--asset-value",
            website_asset.value,
            stdout=out,
        )
        assert Alert.all_objects.filter(
            asset=website_asset, alert_type=Alert.AlertType.DOWN, is_open=True
        ).exists()
        assert "Alerte ouverte" in out.getvalue()

    def test_raises_for_an_unknown_tenant(self):
        with pytest.raises(CommandError):
            call_command(
                "simulate_check_failure",
                "--tenant-slug",
                "does-not-exist",
                "--asset-value",
                "https://example.com",
            )

    def test_raises_for_an_undeclared_asset(self, tenant):
        with pytest.raises(CommandError):
            call_command(
                "simulate_check_failure",
                "--tenant-slug",
                tenant.slug,
                "--asset-value",
                "https://not-declared.example.com",
            )
