from apps.threat_intelligence.models import BreachFinding
from apps.threat_intelligence.providers.breachsense import normalizer


class TestMaskPayload:
    def test_masks_password_field(self):
        masked, secret_seen, secret_masked = normalizer.mask_payload(
            {"email": "a@example.com", "password": "SuperSecret123"}
        )
        assert masked["password"] == "••••••23"
        assert masked["email"] == "a@example.com"
        assert secret_seen is True
        assert secret_masked == "••••••23"

    def test_masks_secret_nested_anywhere_in_the_tree(self):
        masked, secret_seen, _ = normalizer.mask_payload(
            {"session": {"cookie": "abc123XYZ"}, "meta": [{"api_key": "sk-verysecret"}]}
        )
        assert masked["session"]["cookie"].endswith("YZ")
        assert "abc123XYZ" not in str(masked)
        assert masked["meta"][0]["api_key"].endswith("et")
        assert "sk-verysecret" not in str(masked)
        assert secret_seen is True

    def test_no_secret_key_present_leaves_secret_seen_false(self):
        masked, secret_seen, secret_masked = normalizer.mask_payload(
            {"email": "a@example.com", "date": "2026-01-01"}
        )
        assert secret_seen is False
        assert secret_masked == ""
        assert masked == {"email": "a@example.com", "date": "2026-01-01"}

    def test_masking_is_non_reversible_short_tail_only(self):
        _masked, _seen, secret_masked = normalizer.mask_payload({"token": "abcdefghijklmnop"})
        assert secret_masked == "••••••op"
        assert "abcdefghijklmn" not in secret_masked


class TestMaskIdentifier:
    def test_masks_email_local_and_domain_parts(self):
        assert normalizer.mask_identifier("johndoe@example.fr") == "jo••••@ex••••.fr"

    def test_masks_bare_username(self):
        assert normalizer.mask_identifier("johndoe") == "jo••••"

    def test_short_values_fully_masked(self):
        assert normalizer.mask_identifier("jo") == "••••"


class TestNormalizeFinding:
    def test_severity_mapping_per_endpoint(self):
        cases = {
            "stealer": "critical",
            "sessions": "critical",
            "nhi": "critical",
            "darkweb": "critical",
            "creds": "high",
            "combo": "high",
            "docs": "high",
            "radar": "attention",
            "asm": "attention",
        }
        for endpoint, expected_severity in cases.items():
            result = normalizer.normalize_finding(endpoint, {"email": "x@example.com"})
            assert result["severity"] == expected_severity

    def test_identifier_kept_in_clear_only_for_tenant_email(self):
        tenant_emails = {"owner@example.com"}
        result = normalizer.normalize_finding(
            "creds", {"email": "owner@example.com", "password": "x"}, tenant_emails=tenant_emails
        )
        assert result["identifier_plain"] == "owner@example.com"
        assert result["identifier_masked"] == ""

    def test_third_party_identifier_is_masked_not_stored_in_clear(self):
        result = normalizer.normalize_finding(
            "creds",
            {"email": "customer@other.com", "password": "x"},
            tenant_emails={"owner@example.com"},
        )
        assert result["identifier_plain"] == ""
        assert result["identifier_masked"] != ""
        assert "customer@other.com" not in result["identifier_masked"]

    def test_unknown_endpoint_falls_back_to_webhook_source(self):
        result = normalizer.normalize_finding("some-new-endpoint", {})
        assert result["source_endpoint"] == "webhook"

    def test_dedup_hash_stable_for_identical_input(self):
        payload = {"email": "a@example.com", "password": "x", "date": "2026-01-01", "id": "42"}
        first = normalizer.normalize_finding("creds", payload)
        second = normalizer.normalize_finding("creds", dict(payload))
        assert first["dedup_hash"] == second["dedup_hash"]

    def test_dedup_hash_differs_for_different_findings(self):
        a = normalizer.normalize_finding("creds", {"email": "a@example.com", "id": "1"})
        b = normalizer.normalize_finding("creds", {"email": "b@example.com", "id": "2"})
        assert a["dedup_hash"] != b["dedup_hash"]

    def test_breach_date_parsed_from_common_field_names(self):
        result = normalizer.normalize_finding("stealer", {"date": "2025-12-01T00:00:00Z"})
        assert str(result["breach_date"]) == "2025-12-01"

    def test_result_severity_values_match_model_choices(self):
        result = normalizer.normalize_finding("stealer", {})
        assert result["severity"] in BreachFinding.Severity.values
