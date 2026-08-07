"""Unit tests for BreachsenseProvider itself (mocked BreachsenseClient) —
distinct from test_services.py, which exercises business logic against
FakeProvider. These verify the thin translation layer between the HTTP
client's return shapes and the provider-interface dataclasses."""

from unittest.mock import Mock

import pytest

from apps.threat_intelligence.providers.base import ProviderPoolFullError
from apps.threat_intelligence.providers.breachsense.client import BreachsenseForbiddenError
from apps.threat_intelligence.providers.breachsense.provider import BreachsenseProvider
from apps.threat_intelligence.providers.null_provider import NullProvider


def _provider_with_client(**overrides):
    client = Mock()
    for endpoint in (
        "stealer",
        "combo",
        "creds",
        "sessions",
        "nhi",
        "darkweb",
        "docs",
        "asm",
        "radar",
    ):
        getattr(client, endpoint).return_value = ([], 1)
    for name, value in overrides.items():
        getattr(client, name).return_value = value
    return BreachsenseProvider(client=client), client


class TestScanDomain:
    def test_aggregates_findings_across_every_essentials_endpoint(self):
        provider, client = _provider_with_client(
            stealer=([{"email": "a@example.com"}], 2), creds=([{"email": "b@example.com"}], 1)
        )

        result = provider.scan_domain("example.com")

        endpoints_seen = {f.endpoint for f in result.findings}
        assert "stealer" in endpoints_seen
        assert "creds" in endpoints_seen
        assert result.requests_consumed == 2 + 1 + 7  # les 7 autres endpoints, 1 requête chacun

    def test_queries_by_domain_param(self):
        provider, client = _provider_with_client()
        provider.scan_domain("example.com")
        client.stealer.assert_called_once_with(domain="example.com")

    def test_scan_email_queries_by_email_param(self):
        provider, client = _provider_with_client()
        provider.scan_email("user@example.com")
        client.stealer.assert_called_once_with(email="user@example.com")


class TestRegisterMonitoredAsset:
    def test_returns_registration_with_provider_ref(self):
        provider, client = _provider_with_client()
        client.account_add.return_value = {"ref": "bs-123"}

        registration = provider.register_monitored_asset(asset_type="domain", value="example.com")

        assert registration.provider_ref == "bs-123"
        assert registration.value == "example.com"

    def test_forbidden_response_translates_to_pool_full_error(self):
        provider, client = _provider_with_client()
        client.account_add.side_effect = BreachsenseForbiddenError("403")

        with pytest.raises(ProviderPoolFullError):
            provider.register_monitored_asset(asset_type="domain", value="example.com")


class TestGetRemainingQuota:
    def test_parses_remaining_field(self):
        provider, client = _provider_with_client()
        client.account_remaining.return_value = {"remaining": 123}
        assert provider.get_remaining_quota() == 123

    def test_returns_none_on_client_error(self):
        provider, client = _provider_with_client()
        client.account_remaining.side_effect = RuntimeError("network down")
        assert provider.get_remaining_quota() is None


class TestNormalizeWebhookPayload:
    def test_extracts_ast_api_test_fields(self):
        provider, _client = _provider_with_client()
        payload = [{"ast": "example.com", "api": "stealer", "test": True, "email": "a@example.com"}]

        findings = provider.normalize_webhook_payload(payload)

        assert len(findings) == 1
        assert findings[0].asset_ref == "example.com"
        assert findings[0].endpoint == "stealer"
        assert findings[0].is_test is True
        assert findings[0].payload == {"email": "a@example.com"}

    def test_defaults_missing_test_field_to_false(self):
        provider, _client = _provider_with_client()
        findings = provider.normalize_webhook_payload([{"ast": "x", "api": "creds"}])
        assert findings[0].is_test is False


class TestSendTestAlert:
    def test_true_on_ok_response(self):
        provider, client = _provider_with_client()
        client.account_test.return_value = {"ok": True}
        assert provider.send_test_alert() is True

    def test_false_on_explicit_failure(self):
        provider, client = _provider_with_client()
        client.account_test.return_value = {"ok": False}
        assert provider.send_test_alert() is False


class TestNullProvider:
    def test_scan_domain_returns_empty_result(self):
        result = NullProvider().scan_domain("example.com")
        assert result.findings == []

    def test_get_remaining_quota_is_unknown(self):
        assert NullProvider().get_remaining_quota() is None

    def test_register_monitored_asset_raises_not_configured(self):
        from apps.threat_intelligence.providers.base import ProviderNotConfiguredError

        with pytest.raises(ProviderNotConfiguredError):
            NullProvider().register_monitored_asset(asset_type="domain", value="example.com")

    def test_send_test_alert_is_false(self):
        assert NullProvider().send_test_alert() is False

    def test_normalize_webhook_payload_is_empty(self):
        assert NullProvider().normalize_webhook_payload([{"ast": "x", "api": "y"}]) == []


class TestProviderFactory:
    def test_empty_license_key_returns_null_provider(self, settings):
        from apps.threat_intelligence.providers import get_provider

        settings.BREACHSENSE_LICENSE_KEY = ""
        assert isinstance(get_provider(), NullProvider)

    def test_configured_license_key_returns_breachsense_provider(self, settings):
        from apps.threat_intelligence.providers import get_provider

        settings.BREACHSENSE_LICENSE_KEY = "some-key"
        assert isinstance(get_provider(), BreachsenseProvider)
