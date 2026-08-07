import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.threat_intelligence.models import BreachFinding

pytestmark = pytest.mark.django_db


class TestSimulateBreachFindingCommand:
    def test_creates_a_finding_for_declared_asset(self, tenant, website_asset):
        call_command(
            "simulate_breach_finding",
            tenant_slug=tenant.slug,
            asset_value=website_asset.value,
        )

        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1

    def test_unknown_tenant_raises(self):
        with pytest.raises(CommandError):
            call_command("simulate_breach_finding", tenant_slug="does-not-exist", asset_value="x")

    def test_unknown_asset_raises(self, tenant):
        with pytest.raises(CommandError):
            call_command(
                "simulate_breach_finding",
                tenant_slug=tenant.slug,
                asset_value="https://not-declared.example.com",
            )

    def test_does_not_persist_the_simulated_secret(self, tenant, website_asset):
        call_command(
            "simulate_breach_finding",
            tenant_slug=tenant.slug,
            asset_value=website_asset.value,
        )
        finding = BreachFinding.all_objects.get(tenant=tenant)
        assert "SimulatedP4ssw0rd!23" not in str(finding.raw_data)
