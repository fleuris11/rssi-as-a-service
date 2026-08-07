import pytest
from django.core.cache import cache

from apps.threat_intelligence import quota as quota_module
from apps.threat_intelligence.models import BreachIntelligenceUsage
from apps.threat_intelligence.quota import QuotaExceededError, QuotaManager

pytestmark = pytest.mark.django_db


class _StubProvider:
    def __init__(self, remaining):
        self.remaining = remaining
        self.calls = 0

    def get_remaining_quota(self):
        self.calls += 1
        return self.remaining


class TestQuotaManagerCaching:
    def test_get_remaining_caches_across_calls(self):
        provider = _StubProvider(500)
        manager = QuotaManager(provider=provider)

        first = manager.get_remaining()
        second = manager.get_remaining()

        assert first == second == 500
        assert provider.calls == 1  # second call served from cache, not re-queried

    def test_force_refresh_bypasses_cache(self):
        provider = _StubProvider(500)
        manager = QuotaManager(provider=provider)
        manager.get_remaining()

        provider.remaining = 200
        refreshed = manager.get_remaining(force_refresh=True)

        assert refreshed == 200
        assert provider.calls == 2


class TestEnsureQueryBudgetAvailable:
    def test_passes_when_above_margin(self, settings):
        settings.BREACHSENSE_QUOTA_SAFETY_MARGIN = 50
        manager = QuotaManager(provider=_StubProvider(200))
        manager.ensure_query_budget_available()  # no raise

    def test_raises_when_at_or_below_margin(self, settings):
        settings.BREACHSENSE_QUOTA_SAFETY_MARGIN = 50
        manager = QuotaManager(provider=_StubProvider(50))
        with pytest.raises(QuotaExceededError):
            manager.ensure_query_budget_available()

    def test_explicit_margin_overrides_setting(self):
        manager = QuotaManager(provider=_StubProvider(80))
        with pytest.raises(QuotaExceededError):
            manager.ensure_query_budget_available(margin=100)

    def test_unknown_remaining_does_not_block(self):
        # NullProvider / lookup failure -> can't determine a ceiling ->
        # don't false-positive-block a tenant because of a transient issue.
        manager = QuotaManager(provider=_StubProvider(None))
        manager.ensure_query_budget_available()  # no raise


class TestRecordUsage:
    def test_creates_usage_row_and_updates_cache(self, tenant):
        manager = QuotaManager(provider=_StubProvider(999))
        manager.record_usage(
            tenant=tenant,
            endpoint="scan",
            requests_consumed=9,
            remaining_after=991,
            triggered_by="manual",
            findings_created=2,
        )

        usage = BreachIntelligenceUsage.all_objects.get(tenant=tenant)
        assert usage.requests_consumed == 9
        assert usage.findings_created == 2
        assert cache.get(quota_module.REMAINING_CACHE_KEY) == 991


class TestQuotaSummary:
    def test_summary_sums_current_month_usage(self, tenant, other_tenant):
        BreachIntelligenceUsage.all_objects.create(
            tenant=tenant, requests_consumed=10, triggered_by="manual"
        )
        BreachIntelligenceUsage.all_objects.create(
            tenant=other_tenant, requests_consumed=5, triggered_by="initial"
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(QuotaManager, "get_remaining", lambda self, **kw: 900)
            summary = quota_module.get_quota_summary()

        assert summary["monthly_requests_used"] == 15
        assert summary["remaining"] == 900
