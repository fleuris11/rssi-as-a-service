"""ADR-015: cassettes rejouables. La propriété qui compte n'est pas juste
« ça renvoie des données » mais « ça n'appelle jamais le réseau » — le quota
Breachsense (1000 req/mois, partagé par toute la plateforme) est précieux, et
un appel réel parti par accident depuis un test ou un dev serait invisible
jusqu'à l'épuisement du budget.
"""

import json
from unittest.mock import patch

import pytest

from apps.threat_intelligence.providers import ReplayProvider, get_provider, resolve_mode
from apps.threat_intelligence.providers.replay_provider import cassette_path


@pytest.fixture
def cassette_dir(settings, tmp_path):
    settings.BREACHSENSE_CASSETTE_DIR = str(tmp_path)
    return tmp_path


def _write_cassette(directory, domain, endpoints):
    path = directory / f"{domain}.json"
    path.write_text(
        json.dumps({"domain": domain, "secrets_masked": True, "endpoints": endpoints}),
        encoding="utf-8",
    )
    return path


class TestReplayProviderScan:
    def test_serves_findings_from_the_cassette(self, cassette_dir):
        _write_cassette(
            cassette_dir,
            "example.com",
            {"creds": [{"eml": "a@example.com", "pwd": "••••••23"}], "radar": [{"data": "x"}]},
        )

        result = ReplayProvider().scan_domain("example.com")

        assert {f.endpoint for f in result.findings} == {"creds", "radar"}
        assert len(result.findings) == 2

    def test_makes_no_network_call(self, cassette_dir):
        _write_cassette(cassette_dir, "example.com", {"creds": [{"eml": "a@example.com"}]})

        with patch("requests.Session.request") as mocked_request:
            ReplayProvider().scan_domain("example.com")

        mocked_request.assert_not_called()

    def test_consumes_no_quota(self, cassette_dir):
        """A replayed scan must not inflate QuotaManager's usage figures —
        nothing was actually spent."""
        _write_cassette(cassette_dir, "example.com", {"creds": [{"eml": "a@example.com"}]})
        assert ReplayProvider().scan_domain("example.com").requests_consumed == 0

    def test_unknown_domain_returns_empty_result_rather_than_raising(self, cassette_dir):
        result = ReplayProvider().scan_domain("jamais-enregistre.example")
        assert result.findings == []

    def test_cassette_path_is_derived_from_the_domain(self, cassette_dir):
        assert cassette_path("Example.COM").name == "example.com.json"


class TestReplayProviderPoolOperations:
    def test_register_returns_a_deterministic_synthetic_ref(self, cassette_dir):
        first = ReplayProvider().register_monitored_asset(asset_type="domain", value="example.com")
        second = ReplayProvider().register_monitored_asset(asset_type="domain", value="example.com")
        assert first.provider_ref == second.provider_ref
        assert "example.com" in first.provider_ref

    def test_reports_a_plausible_remaining_quota_for_the_back_office(self, cassette_dir):
        assert isinstance(ReplayProvider().get_remaining_quota(), int)


class TestModeResolution:
    def test_replay_mode_is_used_by_the_factory(self, settings, cassette_dir):
        settings.BREACHSENSE_MODE = "replay"
        assert isinstance(get_provider(), ReplayProvider)

    def test_auto_prefers_replay_when_a_cassette_exists(self, settings, cassette_dir):
        _write_cassette(cassette_dir, "example.com", {})
        settings.BREACHSENSE_MODE = "auto"
        assert resolve_mode() == "replay"

    def test_auto_falls_back_to_null_without_cassettes(self, settings, cassette_dir):
        settings.BREACHSENSE_MODE = "auto"
        assert resolve_mode() == "null"

    def test_auto_never_resolves_to_live_even_with_a_license(self, settings, cassette_dir):
        _write_cassette(cassette_dir, "example.com", {})
        settings.BREACHSENSE_MODE = "auto"
        settings.BREACHSENSE_LICENSE_KEY = "a-real-looking-key"
        assert resolve_mode() != "live"


class TestReplayIngestionEndToEnd:
    """The cassette must flow through the REAL ingestion pipeline (masking,
    encryption, dedup, alerting) — a fixture that bypassed it would silently
    stop representing production behaviour."""

    pytestmark = pytest.mark.django_db

    @pytest.mark.django_db
    def test_replayed_scan_creates_findings_through_the_real_pipeline(
        self, settings, cassette_dir, tenant, website_asset
    ):
        from apps.threat_intelligence import services

        settings.BREACHSENSE_MODE = "replay"
        _write_cassette(
            cassette_dir,
            "example.com",
            {"creds": [{"eml": "victime@example.com", "pwd": "••••••23"}]},
        )

        result = services.execute_scan(
            tenant=tenant, assets=[website_asset], triggered_by=services.TriggeredBy.MANUAL
        )

        assert result["findings_created"] == 1
        assert result["requests_consumed"] == 0

    @pytest.mark.django_db
    def test_replaying_the_same_cassette_twice_creates_no_duplicate(
        self, settings, cassette_dir, tenant, website_asset
    ):
        from apps.threat_intelligence import services

        settings.BREACHSENSE_MODE = "replay"
        _write_cassette(
            cassette_dir, "example.com", {"creds": [{"eml": "victime@example.com", "pwd": "x"}]}
        )

        services.execute_scan(
            tenant=tenant, assets=[website_asset], triggered_by=services.TriggeredBy.MANUAL
        )
        second = services.execute_scan(
            tenant=tenant, assets=[website_asset], triggered_by=services.TriggeredBy.MANUAL
        )

        assert second["findings_created"] == 0
