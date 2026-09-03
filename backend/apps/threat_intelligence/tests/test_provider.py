"""Unit tests for BreachsenseProvider itself (mocked BreachsenseClient) —
distinct from test_services.py, which exercises business logic against
FakeProvider. These verify the thin translation layer between the HTTP
client's return shapes and the provider-interface dataclasses."""

from unittest.mock import Mock

import pytest

from apps.threat_intelligence.providers.base import ProviderPoolFullError
from apps.threat_intelligence.providers.breachsense.client import (
    QUERY_ENDPOINTS,
    BreachsenseForbiddenError,
)
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

    # Ces deux tests affirmaient l'inverse jusqu'au 03/09/2026 : ils
    # vérifiaient `domain=` et `email=`, c'est-à-dire NOTRE hypothèse, pas le
    # contrat du fournisseur. Ils sont donc restés verts pendant que chaque
    # scan réel échouait en production sur « 400 Request missing the
    # appropriate parameters ». Un test qui ne fait que répéter la supposition
    # du code ne teste rien.
    def test_queries_use_the_s_parameter_for_a_domain(self):
        provider, client = _provider_with_client()
        provider.scan_domain("example.com")
        client.stealer.assert_called_once_with(s="example.com")

    def test_queries_use_the_same_s_parameter_for_an_email(self):
        # `s` accepte indifféremment un domaine ou une adresse : il n'existe
        # pas de paramètre distinct pour l'email.
        provider, client = _provider_with_client()
        provider.scan_email("user@example.com")
        client.stealer.assert_called_once_with(s="user@example.com")

    def test_no_query_ever_sends_a_domain_parameter(self):
        """Garde de non-régression, sur les neuf endpoints à la fois."""
        provider, client = _provider_with_client()
        provider.scan_domain("example.com")
        for endpoint in QUERY_ENDPOINTS:
            _args, kwargs = getattr(client, endpoint).call_args
            assert "domain" not in kwargs and "email" not in kwargs, (
                f"{endpoint} envoie un paramètre inexistant côté Breachsense : {sorted(kwargs)}"
            )
            assert kwargs == {"s": "example.com"}


class TestRegisterMonitoredAsset:
    def test_returns_registration_with_provider_ref(self):
        provider, client = _provider_with_client()
        client.account_add.return_value = {"ref": "bs-123"}

        registration = provider.register_monitored_asset(asset_type="domain", value="example.com")

        assert registration.provider_ref == "bs-123"
        assert registration.value == "example.com"

    def test_falls_back_to_the_value_when_the_response_carries_no_reference(self):
        """Réponse réelle observée : `/account?action=list` ne renvoie que
        `ast`. Un ajout qui ne renvoie ni `ref` ni `id` doit donc rester
        désenregistrable — la valeur EST l'identifiant côté Breachsense."""
        provider, client = _provider_with_client()
        client.account_add.return_value = {}

        registration = provider.register_monitored_asset(asset_type="domain", value="example.com")

        assert registration.provider_ref == "example.com"


class TestListMonitoredAssets:
    def test_reads_the_ast_field(self):
        """`/account?action=list` renvoie `[{"ast": "..."}]` — les clés
        `ref`/`id`/`asset` lues jusqu'ici n'existent pas, et produisaient une
        liste de références « None », donc indésenregistrables."""
        provider, client = _provider_with_client()
        client.account_list.return_value = [{"ast": "exemple.fr"}, {"ast": "autre.fr"}]

        assets = provider.list_monitored_assets()

        assert [a.provider_ref for a in assets] == ["exemple.fr", "autre.fr"]
        assert [a.value for a in assets] == ["exemple.fr", "autre.fr"]

    def test_ignores_entries_without_an_asset(self):
        provider, client = _provider_with_client()
        client.account_list.return_value = [{"ast": "exemple.fr"}, {}]
        assert len(provider.list_monitored_assets()) == 1

    def test_forbidden_response_translates_to_pool_full_error(self):
        provider, client = _provider_with_client()
        client.account_add.side_effect = BreachsenseForbiddenError("403")

        with pytest.raises(ProviderPoolFullError):
            provider.register_monitored_asset(asset_type="domain", value="example.com")


class TestGetRemainingQuota:
    def test_parses_the_capitalised_remaining_field(self):
        """L'API répond `{"Remaining": 985}`. La clé minuscule était seule
        lue : le quota restait donc toujours « inconnu », et la garde de
        budget laissait passer sans jamais protéger la licence."""
        provider, client = _provider_with_client()
        client.account_remaining.return_value = {"Remaining": 985}
        assert provider.get_remaining_quota() == 985

    def test_parses_remaining_field(self):
        provider, client = _provider_with_client()
        client.account_remaining.return_value = {"remaining": 123}
        assert provider.get_remaining_quota() == 123

    def test_returns_none_on_empty_body(self):
        """Ce que renvoyait `action=remaining` : 200 avec un corps vide. Le
        quota devient inconnu — pas une erreur, mais plus jamais silencieux
        maintenant que la requête est correcte."""
        provider, client = _provider_with_client()
        client.account_remaining.return_value = {}
        assert provider.get_remaining_quota() is None

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
    """Phase 8A (ADR-015): the mode, not the mere presence of a licence key,
    decides which provider is in use — a configured licence is a capability,
    not an instruction to spend the shared query budget."""

    def test_explicit_live_mode_with_license_returns_breachsense_provider(self, settings):
        from apps.threat_intelligence.providers import get_provider

        settings.BREACHSENSE_MODE = "live"
        settings.BREACHSENSE_LICENSE_KEY = "some-key"
        assert isinstance(get_provider(), BreachsenseProvider)

    def test_live_mode_without_license_degrades_to_null_not_error(self, settings):
        from apps.threat_intelligence.providers import get_provider

        settings.BREACHSENSE_MODE = "live"
        settings.BREACHSENSE_LICENSE_KEY = ""
        assert isinstance(get_provider(), NullProvider)

    def test_replay_mode_returns_replay_provider(self, settings):
        from apps.threat_intelligence.providers import ReplayProvider, get_provider

        settings.BREACHSENSE_MODE = "replay"
        settings.BREACHSENSE_LICENSE_KEY = "some-key"
        assert isinstance(get_provider(), ReplayProvider)

    def test_null_mode_returns_null_provider(self, settings):
        from apps.threat_intelligence.providers import get_provider

        settings.BREACHSENSE_MODE = "null"
        settings.BREACHSENSE_LICENSE_KEY = "some-key"
        assert isinstance(get_provider(), NullProvider)

    def test_auto_mode_never_goes_live_even_with_a_license(self, settings, tmp_path):
        """The whole point of ADR-015: a licensed environment must not start
        spending the shared 1000 req/month budget by default."""
        from apps.threat_intelligence.providers import get_provider

        settings.BREACHSENSE_MODE = "auto"
        settings.BREACHSENSE_LICENSE_KEY = "some-key"
        settings.BREACHSENSE_CASSETTE_DIR = str(tmp_path)
        assert not isinstance(get_provider(), BreachsenseProvider)

    def test_auto_mode_uses_replay_when_cassettes_exist(self, settings, tmp_path):
        from apps.threat_intelligence.providers import ReplayProvider, get_provider

        (tmp_path / "example.com.json").write_text('{"endpoints": {}}', encoding="utf-8")
        settings.BREACHSENSE_MODE = "auto"
        settings.BREACHSENSE_CASSETTE_DIR = str(tmp_path)
        assert isinstance(get_provider(), ReplayProvider)

    def test_auto_mode_falls_back_to_null_without_cassettes(self, settings, tmp_path):
        from apps.threat_intelligence.providers import get_provider

        settings.BREACHSENSE_MODE = "auto"
        settings.BREACHSENSE_CASSETTE_DIR = str(tmp_path / "vide")
        assert isinstance(get_provider(), NullProvider)

    def test_unknown_mode_is_treated_as_auto_never_live(self, settings, tmp_path):
        from apps.threat_intelligence.providers import get_provider

        settings.BREACHSENSE_MODE = "n-importe-quoi"
        settings.BREACHSENSE_LICENSE_KEY = "some-key"
        settings.BREACHSENSE_CASSETTE_DIR = str(tmp_path / "vide")
        assert isinstance(get_provider(), NullProvider)
