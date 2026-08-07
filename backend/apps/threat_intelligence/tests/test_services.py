from unittest.mock import patch

import pytest

from apps.monitoring.models import Alert
from apps.threat_intelligence import services
from apps.threat_intelligence.models import BreachFinding, BreachScanJob, MonitoredAsset
from apps.threat_intelligence.providers.base import ProviderPoolFullError, RawFinding
from apps.threat_intelligence.quota import QuotaExceededError

pytestmark = pytest.mark.django_db


class TestIngestRawFindings:
    def test_creates_finding_and_opens_alert(self, tenant, website_asset):
        raw = RawFinding(endpoint="stealer", payload={"email": "a@example.com", "password": "x"})

        created = services.ingest_raw_findings(
            tenant=tenant, asset=website_asset, raw_findings=[raw]
        )

        assert len(created) == 1
        finding = created[0]
        assert finding.severity == BreachFinding.Severity.CRITICAL
        assert finding.alert is not None
        assert finding.alert.alert_type == Alert.AlertType.BREACH_COMPROMISE
        assert finding.alert.severity == Alert.Severity.CRITICAL

    def test_attention_severity_maps_to_warning_alert(self, tenant, website_asset):
        raw = RawFinding(endpoint="radar", payload={"email": "a@example.com"})
        created = services.ingest_raw_findings(
            tenant=tenant, asset=website_asset, raw_findings=[raw]
        )
        assert created[0].alert.severity == Alert.Severity.WARNING

    def test_duplicate_finding_is_not_created_twice(self, tenant, website_asset):
        raw = RawFinding(endpoint="creds", payload={"email": "a@example.com", "id": "42"})

        first = services.ingest_raw_findings(tenant=tenant, asset=website_asset, raw_findings=[raw])
        second = services.ingest_raw_findings(
            tenant=tenant, asset=website_asset, raw_findings=[raw]
        )

        assert len(first) == 1
        assert len(second) == 0
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1

    def test_test_flagged_findings_are_skipped(self, tenant, website_asset):
        raw = RawFinding(endpoint="stealer", payload={"email": "a@example.com"}, is_test=True)
        created = services.ingest_raw_findings(
            tenant=tenant, asset=website_asset, raw_findings=[raw]
        )
        assert created == []
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 0


class TestExecuteScan:
    def test_records_usage_and_returns_summary(self, tenant, website_asset, fake_provider):
        fake_provider.scan_findings = [
            RawFinding(endpoint="stealer", payload={"email": "a@example.com"})
        ]
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            result = services.execute_scan(
                tenant=tenant, assets=[website_asset], triggered_by=services.TriggeredBy.INITIAL
            )

        assert result["findings_created"] == 1
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1

    def test_manual_scan_sets_cooldown(self, tenant, website_asset, fake_provider):
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            services.execute_scan(
                tenant=tenant, assets=[website_asset], triggered_by=services.TriggeredBy.MANUAL
            )
        with pytest.raises(services.CooldownActiveError):
            services.ensure_scan_cooldown_elapsed(tenant)

    def test_initial_scan_does_not_set_cooldown(self, tenant, website_asset, fake_provider):
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            services.execute_scan(
                tenant=tenant, assets=[website_asset], triggered_by=services.TriggeredBy.INITIAL
            )
        services.ensure_scan_cooldown_elapsed(tenant)  # no raise


class TestCreateScanJob:
    def test_manual_trigger_blocked_by_active_cooldown(self, tenant, website_asset):
        services.mark_scan_cooldown(tenant)
        with pytest.raises(services.CooldownActiveError):
            services.create_scan_job(
                tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
            )

    def test_manual_trigger_blocked_by_low_quota(self, tenant, website_asset, settings):
        settings.BREACHSENSE_QUOTA_SAFETY_MARGIN = 50
        with patch(
            "apps.threat_intelligence.quota.QuotaManager._get_provider",
            return_value=type("P", (), {"get_remaining_quota": lambda self: 10})(),
        ):
            with pytest.raises(QuotaExceededError):
                services.create_scan_job(
                    tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
                )

    def test_successful_manual_trigger_creates_job(self, tenant, website_asset):
        job = services.create_scan_job(
            tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
        )
        assert job.status == BreachScanJob.Status.PENDING
        assert job.asset_id == website_asset.id


class TestMonitoredAssetPool:
    def test_register_creates_monitored_asset(self, tenant, website_asset, fake_provider, settings):
        settings.BREACHSENSE_WEBHOOK_CALLBACK_URL = "https://api.example.com/webhook"
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            monitored = services.register_monitored_asset(tenant=tenant, asset=website_asset)

        assert monitored.asset_id == website_asset.id
        assert fake_provider.registered == ["example.com"]

    def test_register_refuses_without_webhook_url_configured(
        self, tenant, website_asset, fake_provider, settings
    ):
        settings.BREACHSENSE_WEBHOOK_CALLBACK_URL = ""
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            with pytest.raises(services.WebhookNotConfiguredError):
                services.register_monitored_asset(tenant=tenant, asset=website_asset)

    def test_register_refuses_when_already_monitored(
        self, tenant, website_asset, fake_provider, settings
    ):
        settings.BREACHSENSE_WEBHOOK_CALLBACK_URL = "https://api.example.com/webhook"
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            services.register_monitored_asset(tenant=tenant, asset=website_asset)
            with pytest.raises(services.AssetAlreadyMonitoredError):
                services.register_monitored_asset(tenant=tenant, asset=website_asset)

    def test_register_refuses_when_pool_full_locally(
        self, tenant, website_asset, fake_provider, settings
    ):
        settings.BREACHSENSE_WEBHOOK_CALLBACK_URL = "https://api.example.com/webhook"
        settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE = 0
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            with pytest.raises(services.PoolFullError):
                services.register_monitored_asset(tenant=tenant, asset=website_asset)
        assert fake_provider.registered == []  # refused before calling the provider

    def test_register_translates_provider_pool_full_error(self, tenant, website_asset, settings):
        settings.BREACHSENSE_WEBHOOK_CALLBACK_URL = "https://api.example.com/webhook"
        provider = type(
            "P",
            (),
            {
                "register_monitored_asset": lambda self, **kw: (_ for _ in ()).throw(
                    ProviderPoolFullError("full")
                )
            },
        )()
        with patch("apps.threat_intelligence.services.get_provider", return_value=provider):
            with pytest.raises(services.PoolFullError):
                services.register_monitored_asset(tenant=tenant, asset=website_asset)

    def test_unregister_deactivates_and_calls_provider(
        self, tenant, website_asset, fake_provider, settings
    ):
        settings.BREACHSENSE_WEBHOOK_CALLBACK_URL = "https://api.example.com/webhook"
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            monitored = services.register_monitored_asset(tenant=tenant, asset=website_asset)
            services.unregister_monitored_asset(monitored)

        monitored.refresh_from_db()
        assert monitored.is_active is False
        assert fake_provider.unregistered == [monitored.provider_ref]
        assert services.pool_capacity_remaining() == settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE


class TestWebhookIngestion:
    # ingest_webhook_payload() calls get_provider().normalize_webhook_payload()
    # to parse the transport format (ast/api/test) — NullProvider (the
    # default with no license configured in tests) always returns [], so
    # these tests patch get_provider onto fake_provider, whose
    # normalize_webhook_payload mirrors BreachsenseProvider's real parsing.

    def test_ingest_resolves_tenant_via_monitored_asset(self, tenant, website_asset, fake_provider):
        MonitoredAsset.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            provider_ref="example.com",
            provider_asset_type="domain",
        )
        payload = [
            {"ast": "example.com", "api": "stealer", "email": "a@example.com", "password": "x"}
        ]

        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            result = services.ingest_webhook_payload(payload)

        assert result["findings_created"] == 1
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1

    def test_ingest_ignores_unmatched_asset_ref(self, tenant, website_asset, fake_provider):
        payload = [{"ast": "unknown-domain.com", "api": "stealer", "email": "a@example.com"}]
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            result = services.ingest_webhook_payload(payload)
        assert result["findings_created"] == 0
        assert result["unmatched_refs"] == ["unknown-domain.com"]

    def test_ingest_is_idempotent_across_redeliveries(self, tenant, website_asset, fake_provider):
        MonitoredAsset.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            provider_ref="example.com",
            provider_asset_type="domain",
        )
        payload = [{"ast": "example.com", "api": "stealer", "email": "a@example.com", "id": "abc"}]

        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            services.ingest_webhook_payload(payload)
            services.ingest_webhook_payload(payload)

        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1

    def test_ingest_skips_test_payloads(self, tenant, website_asset, fake_provider):
        MonitoredAsset.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            provider_ref="example.com",
            provider_asset_type="domain",
        )
        payload = [{"ast": "example.com", "api": "stealer", "test": True}]
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            result = services.ingest_webhook_payload(payload)
        assert result["findings_created"] == 0


class TestFindingStatus:
    def test_set_status_treated_records_user_and_timestamp(
        self, tenant, website_asset, tenant_owner
    ):
        raw = RawFinding(endpoint="creds", payload={"email": "a@example.com"})
        finding = services.ingest_raw_findings(
            tenant=tenant, asset=website_asset, raw_findings=[raw]
        )[0]

        updated = services.set_finding_status(
            finding, status=BreachFinding.Status.TREATED, user=tenant_owner
        )

        assert updated.status == BreachFinding.Status.TREATED
        assert updated.treated_by_id == tenant_owner.id
        assert updated.treated_at is not None
