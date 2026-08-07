import pytest
from django.core.cache import cache

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset
from apps.threat_intelligence.providers.base import (
    BreachIntelligenceProvider,
    MonitoredAssetRegistration,
    RawFinding,
    ScanResult,
)
from apps.threat_intelligence.throttle import get_redis_client


@pytest.fixture(autouse=True)
def _reset_breachsense_state():
    """The token-bucket key and the cached remaining-quota figure both live
    outside Django's test-transaction rollback (Redis, not Postgres) — without
    this, one test's throttle/quota state would bleed into the next, exactly
    like the project-wide ``_clear_cache`` fixture does for DRF throttling."""
    from apps.threat_intelligence.throttle import BUCKET_KEY

    get_redis_client().delete(BUCKET_KEY)
    cache.clear()
    yield
    get_redis_client().delete(BUCKET_KEY)
    cache.clear()


@pytest.fixture
def other_tenant(user_factory, tenant_factory):
    owner = user_factory(email="other-tenant-owner@example.com")
    return tenant_factory(owner, name="Autre Entreprise")


@pytest.fixture
def website_asset(tenant, tenant_owner):
    return monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://example.com",
        ownership_confirmed=True,
    )


class FakeProvider(BreachIntelligenceProvider):
    """Test double for the provider interface — lets services/views tests
    exercise the real business logic (quota, dedup, alerting, pool
    management) without touching BreachsenseClient or Redis-backed
    throttling internals, which have their own dedicated tests."""

    def __init__(self, *, scan_findings=None, remaining_quota=1000, pool_capacity_error=None):
        self.scan_findings = scan_findings or []
        self.remaining_quota = remaining_quota
        self.pool_capacity_error = pool_capacity_error
        self.registered = []
        self.unregistered = []

    def scan_domain(self, domain):
        return ScanResult(
            findings=list(self.scan_findings), requests_consumed=len(self.scan_findings) or 1
        )

    def scan_email(self, email):
        return ScanResult(findings=[], requests_consumed=1)

    def register_monitored_asset(self, *, asset_type, value):
        if self.pool_capacity_error:
            raise self.pool_capacity_error
        self.registered.append(value)
        return MonitoredAssetRegistration(
            provider_ref=f"ref-{value}", asset_type=asset_type, value=value
        )

    def unregister_monitored_asset(self, provider_ref):
        self.unregistered.append(provider_ref)

    def list_monitored_assets(self):
        return []

    def get_remaining_quota(self):
        return self.remaining_quota

    def send_test_alert(self):
        return True

    def normalize_webhook_payload(self, payload):
        findings = []
        for item in payload:
            item = dict(item)
            asset_ref = str(item.pop("ast", ""))
            endpoint = str(item.pop("api", "webhook"))
            is_test = bool(item.pop("test", False))
            findings.append(
                RawFinding(endpoint=endpoint, payload=item, is_test=is_test, asset_ref=asset_ref)
            )
        return findings


@pytest.fixture
def fake_provider():
    return FakeProvider()
