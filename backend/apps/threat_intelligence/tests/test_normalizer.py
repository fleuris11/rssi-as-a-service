from apps.threat_intelligence.models import BreachFinding
from apps.threat_intelligence.providers.breachsense import normalizer

# Payloads réalistes par endpoint, schéma réel Breachsense (palier
# Essentials) — fournis directement, pas devinés. Un objet par endpoint,
# réutilisé par plusieurs tests ci-dessous pour éviter la duplication.
REALISTIC_PAYLOADS = {
    "stealer": {
        "usr": "jdupont",
        "pwd": "SuperSecret123",
        "src": "RedLine Stealer log 2026-01",
        "fle": "passwords.txt",
        "fnd": "2026-01-15",
        "nme": "DESKTOP-JD01",
        "iip": "203.0.113.5",
        "inf": "2026-01-10",
        "mal": "RedLine",
        "os": "Windows 10",
        "hid": "HWID-ABC123",
        "bid": "build-42",
        "mac": "AA:BB:CC:DD:EE:FF",
        "pth": "C:/Users/jdupont/Documents/passwords.txt",
        "ccn": "4111111111111111",
        "ccx": "12/27",
        "cwa": "bc1qxyz0000000000000000000000000000000",
    },
    "combo": {
        "usr": "jdupont",
        "pwd": "SuperSecret123",
        "src": "Combo list 2026-Q1",
        "fle": "combo.txt",
        "fnd": "2026-01-15",
        "cnt": 3,
    },
    "creds": {
        "eml": "j.dupont@example.com",
        "pwd": "SuperSecret123",
        "src": "Breach XYZ 2025",
        "fnd": "2026-01-15",
        "atr": "APT-Fake",
        "hash": 0,
    },
    "sessions": {
        "dom": "example.com",
        "cookie_name": "session_id",
        "cookie_path": "/account",
        "val": "eyJhbGciOiJIUzI1NiJ9.SECRETCOOKIEVALUE",
        "expires": "2026-06-01",
        "user_name": "jdupont",
        "iip": "203.0.113.5",
        "inf": "2026-01-10",
        "mal": "Vidar",
        "malware_path": "C:/temp/vidar.exe",
        "bid": "build-7",
        "fnd": "2026-01-15",
    },
    "nhi": {
        "token": "sk-live-abcdef1234567890",
        "token_type": "api_key",
        "platform": "GitHub",
        "category": "service-account",
        "source_type": "stealer",
        "prefix": "sk-live-",
        "src": "RedLine Stealer log 2026-01",
        "pth": "C:/Users/svc/.env",
        "ip": "203.0.113.5",
        "usr": "svc-deploy-bot",
        "fnd": "2026-01-15",
        "bid": "build-42",
        "hid": "HWID-ABC123",
        "mal": "RedLine",
        "os": "Windows 10",
        "av": "Windows Defender",
    },
    "darkweb": {
        "data": "example.com",
        "name": "Example SAS",
        "desc": "Mention sur un forum spécialisé",
        "site": "ShadowForum",
        "tadesc": "Groupe opportuniste",
        "src": "forum-scrape",
        "found": "2026-01-15",
    },
    "radar": {
        "data": "example.com",
        "src": "radar-scan",
        "found": "2026-01-15",
    },
    "docs": {
        "doc_id": "doc-9f8e7d",
        "file_name": "contrat_confidentiel.pdf",
        "file_hash": "5e884898da28047151d0e56f8dc6292",
        "file_size": 204800,
        "content_type": "application/pdf",
        "extraction_timestamp": "2026-01-16T08:00:00Z",
        "leak_date": "2026-01-15",
        "threat_actor": "LeakSite42",
        "company_name": "Example SAS",
        "domain_name": "example.com",
        "url_main_post": "https://leaksite.example/post/1",
        "url_for_breach": "https://leaksite.example/breach/1",
        "password": "ZipArchiveSecret42",
    },
    "asm": {
        "dom": "mail.example.com",
        "type": "mx",
        "cname": "",
        "ip": "203.0.113.10",
        "found": "2026-01-15",
    },
}


class TestMaskPayload:
    def test_masks_password_field(self):
        masked, secret_seen, secret_masked, secret_plain = normalizer.mask_payload(
            {"email": "a@example.com", "password": "SuperSecret123"}
        )
        assert masked["password"] == "••••••23"
        assert masked["email"] == "a@example.com"
        assert secret_seen is True
        assert secret_masked == "••••••23"
        assert secret_plain == "SuperSecret123"

    def test_masks_secret_nested_anywhere_in_the_tree(self):
        masked, secret_seen, _, _plain = normalizer.mask_payload(
            {"outer": {"token": "abc123XYZ"}, "meta": [{"api_key": "sk-verysecret"}]}
        )
        assert masked["outer"]["token"].endswith("YZ")
        assert "abc123XYZ" not in str(masked)
        assert masked["meta"][0]["api_key"].endswith("et")
        assert "sk-verysecret" not in str(masked)
        assert secret_seen is True

    def test_no_secret_key_present_leaves_secret_seen_false(self):
        masked, secret_seen, secret_masked, secret_plain = normalizer.mask_payload(
            {"email": "a@example.com", "date": "2026-01-01"}
        )
        assert secret_seen is False
        assert secret_masked == ""
        assert secret_plain == ""
        assert masked == {"email": "a@example.com", "date": "2026-01-01"}

    def test_masking_is_non_reversible_short_tail_only(self):
        _masked, _seen, secret_masked, _plain = normalizer.mask_payload(
            {"token": "abcdefghijklmnop"}
        )
        assert secret_masked == "••••••op"
        assert "abcdefghijklmn" not in secret_masked

    def test_first_secret_plain_feeds_encryption_not_display(self):
        """secret_plain is the in-memory-only counterpart of secret_masked —
        never itself displayed, only handed to services.encrypt_secret
        (ADR-014 update) before being discarded."""
        _masked, _seen, secret_masked, secret_plain = normalizer.mask_payload(
            {"token": "abcdefghijklmnop"}
        )
        assert secret_plain == "abcdefghijklmnop"
        assert secret_plain not in secret_masked

    def test_exact_field_secrets_masked_val_ccn_ccx_cwa(self):
        payload = {
            "val": "cookie-secret",
            "ccn": "4111111111111111",
            "ccx": "12/27",
            "cwa": "bc1qxyz",
        }
        masked, secret_seen, _, _plain = normalizer.mask_payload(payload)
        assert secret_seen is True
        for key in ("val", "ccn", "ccx", "cwa"):
            assert masked[key].startswith("••••••")
            assert masked[key] != payload[key]

    def test_cookie_name_and_path_are_not_masked_only_val_is(self):
        """Regression: "cookie" used to be a generic marker and would have
        wrongly masked cookie_name/cookie_path (structural metadata, not
        secrets) — only the actual cookie value ("val") is a secret."""
        masked, _seen, _, _plain = normalizer.mask_payload(REALISTIC_PAYLOADS["sessions"])
        assert masked["cookie_name"] == "session_id"
        assert masked["cookie_path"] == "/account"
        assert masked["val"] != REALISTIC_PAYLOADS["sessions"]["val"]

    def test_file_hash_and_creds_hash_flag_are_not_masked(self):
        """Regression: "hash" used to be a generic marker and would have
        wrongly masked docs.file_hash (a checksum, not a secret) and
        creds.hash (a 0/1 "hashed vs decrypted" indicator, not a secret)."""
        docs_masked, _seen, _, _plain = normalizer.mask_payload(REALISTIC_PAYLOADS["docs"])
        assert docs_masked["file_hash"] == REALISTIC_PAYLOADS["docs"]["file_hash"]

        creds_masked, _seen, _, _plain = normalizer.mask_payload(REALISTIC_PAYLOADS["creds"])
        assert creds_masked["hash"] == 0


class TestMaskIdentifier:
    def test_masks_email_local_and_domain_parts(self):
        assert normalizer.mask_identifier("johndoe@example.fr") == "jo••••@ex••••.fr"

    def test_masks_bare_username(self):
        assert normalizer.mask_identifier("johndoe") == "jo••••"

    def test_short_values_fully_masked(self):
        assert normalizer.mask_identifier("jo") == "••••"


class TestNormalizeFindingPerEndpoint:
    """One realistic payload per real Breachsense endpoint schema — checks
    that the right field is picked as identifier/date/type, and that every
    secret field for that endpoint ends up masked, never in clear."""

    def test_stealer(self):
        result = normalizer.normalize_finding("stealer", REALISTIC_PAYLOADS["stealer"])
        assert result["severity"] == "critical"
        assert result["breach_date"].isoformat() == "2026-01-10"  # inf prioritaire sur fnd
        assert result["finding_type"] == "RedLine"  # champ mal
        assert result["has_secret"] is True
        blob = str(result["raw_data"])
        assert "SuperSecret123" not in blob
        assert "4111111111111111" not in blob
        assert "bc1qxyz0000000000000000000000000000000" not in blob

    def test_combo(self):
        result = normalizer.normalize_finding("combo", REALISTIC_PAYLOADS["combo"])
        assert result["severity"] == "high"
        assert result["breach_date"].isoformat() == "2026-01-15"
        assert "SuperSecret123" not in str(result["raw_data"])

    def test_creds_identifier_is_eml_field(self):
        result = normalizer.normalize_finding(
            "creds", REALISTIC_PAYLOADS["creds"], tenant_emails={"j.dupont@example.com"}
        )
        assert result["severity"] == "high"
        assert result["identifier_plain"] == "j.dupont@example.com"
        assert "SuperSecret123" not in str(result["raw_data"])

    def test_creds_identifier_masked_for_non_tenant_email(self):
        result = normalizer.normalize_finding(
            "creds", REALISTIC_PAYLOADS["creds"], tenant_emails=set()
        )
        assert result["identifier_plain"] == ""
        assert result["identifier_masked"] == "j.••••@ex••••.com"

    def test_sessions_uses_user_name_field_and_masks_val_not_cookie_name(self):
        result = normalizer.normalize_finding(
            "sessions", REALISTIC_PAYLOADS["sessions"], tenant_emails=set()
        )
        assert result["severity"] == "critical"
        assert result["identifier_masked"] != ""  # user_name extrait, jamais l'email tenant ici
        assert result["breach_date"].isoformat() == "2026-01-15"  # fnd, pas expires
        assert "eyJhbGciOiJIUzI1NiJ9.SECRETCOOKIEVALUE" not in str(result["raw_data"])
        assert result["raw_data"]["cookie_name"] == "session_id"  # pas masqué, pas un secret

    def test_nhi_uses_category_as_type_and_masks_token(self):
        result = normalizer.normalize_finding("nhi", REALISTIC_PAYLOADS["nhi"])
        assert result["severity"] == "critical"
        assert result["finding_type"] == "service-account"
        assert result["has_secret"] is True
        assert "sk-live-abcdef1234567890" not in str(result["raw_data"])

    def test_darkweb_uses_found_field_for_date(self):
        result = normalizer.normalize_finding("darkweb", REALISTIC_PAYLOADS["darkweb"])
        assert result["severity"] == "critical"
        assert result["breach_date"].isoformat() == "2026-01-15"
        assert result["has_secret"] is False  # aucun champ secret sur cet endpoint

    def test_radar_default_severity_attention(self):
        result = normalizer.normalize_finding("radar", REALISTIC_PAYLOADS["radar"])
        assert result["severity"] == "attention"

    def test_docs_uses_leak_date_and_content_type_masks_password(self):
        result = normalizer.normalize_finding("docs", REALISTIC_PAYLOADS["docs"])
        assert result["severity"] == "high"
        assert result["breach_date"].isoformat() == "2026-01-15"
        assert result["finding_type"] == "application/pdf"
        assert "ZipArchiveSecret42" not in str(result["raw_data"])
        # file_hash n'est pas un secret : conservé en clair dans raw_data.
        assert result["raw_data"]["file_hash"] == REALISTIC_PAYLOADS["docs"]["file_hash"]

    def test_asm_non_phishing_type_is_attention(self):
        result = normalizer.normalize_finding("asm", REALISTIC_PAYLOADS["asm"])
        assert result["severity"] == "attention"
        assert result["finding_type"] == "mx"
        assert result["has_secret"] is False

    def test_asm_phishing_type_is_elevated_to_high(self):
        payload = {**REALISTIC_PAYLOADS["asm"], "type": "pphish", "dom": "examp1e-secure.com"}
        result = normalizer.normalize_finding("asm", payload)
        assert result["severity"] == "high"
        assert result["finding_type"] == "pphish"


class TestNormalizeFindingGeneral:
    def test_unknown_endpoint_falls_back_to_webhook_source(self):
        result = normalizer.normalize_finding("some-new-endpoint", {})
        assert result["source_endpoint"] == "webhook"

    def test_dedup_hash_stable_for_identical_input(self):
        payload = dict(REALISTIC_PAYLOADS["creds"])
        first = normalizer.normalize_finding("creds", payload)
        second = normalizer.normalize_finding("creds", dict(payload))
        assert first["dedup_hash"] == second["dedup_hash"]

    def test_dedup_hash_differs_for_different_findings(self):
        a = normalizer.normalize_finding("creds", REALISTIC_PAYLOADS["creds"])
        b = normalizer.normalize_finding(
            "creds",
            {**REALISTIC_PAYLOADS["creds"], "eml": "autre@example.com", "fnd": "2026-02-01"},
        )
        assert a["dedup_hash"] != b["dedup_hash"]

    def test_dedup_hash_differs_across_endpoints_for_same_raw_shape(self):
        """Same identifier/secret shape but a different endpoint must not
        collide — the endpoint name is part of the hash input."""
        a = normalizer.normalize_finding("combo", {"usr": "x", "pwd": "y", "fnd": "2026-01-01"})
        b = normalizer.normalize_finding("stealer", {"usr": "x", "pwd": "y", "fnd": "2026-01-01"})
        assert a["dedup_hash"] != b["dedup_hash"]

    def test_result_severity_values_match_model_choices(self):
        result = normalizer.normalize_finding("stealer", REALISTIC_PAYLOADS["stealer"])
        assert result["severity"] in BreachFinding.Severity.values

    def test_unknown_endpoint_still_extracts_via_fallback_keys(self):
        """Robustness net (ADR-014 §2) for a schema not in ENDPOINT_SCHEMAS
        — generic keys still get picked up rather than silently dropped."""
        result = normalizer.normalize_finding(
            "future-endpoint", {"email": "a@example.com", "date": "2026-03-01", "password": "x"}
        )
        assert result["identifier_masked"] != "" or result["identifier_plain"] != ""
        assert result["breach_date"].isoformat() == "2026-03-01"
        assert result["has_secret"] is True
