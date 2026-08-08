"""ADR-014 §3: a dedicated property test — every simulated payload for
every Essentials endpoint carries a known secret; after running it through
the real ingestion pipeline (normalize -> persist), a raw SQL scan of the
created row's text/JSON columns must find zero occurrences of that secret
anywhere. This protects against a future regression (a new field, a
forgotten masking rule) silently storing a real secret.
"""

import json

import pytest
from django.db import connection

from apps.threat_intelligence import services
from apps.threat_intelligence.models import BreachFinding
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db

KNOWN_SECRETS = [
    "P4ssw0rd!Sup3rSecret",
    "sk-live-abcdef1234567890",
    "session-cookie-XyZ987654321",
]

# Nom de champ RÉEL porteur de secret par endpoint (schéma Breachsense,
# palier Essentials — fourni directement) : darkweb/radar/asm n'ont aucun
# champ secret et sont volontairement absents de ce mapping. stealer a
# PLUSIEURS champs secrets distincts (mot de passe + données financières) —
# couvert séparément par TestNoSecretPersistence.test_stealer_financial_fields.
ENDPOINTS_WITH_SECRET_FIELDS = {
    "stealer": "pwd",
    "combo": "pwd",
    "creds": "pwd",
    "sessions": "val",
    "nhi": "token",
    "docs": "password",
}

STEALER_EXTRA_SECRET_FIELDS = ["ccn", "ccx", "cwa"]


def _row_text_blob(finding_id: int) -> str:
    """Every text/JSON column of the BreachFinding row, concatenated —
    deliberately raw SQL (not the ORM) so this test can't be fooled by a
    Python-level property that doesn't reflect what's actually on disk."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT identifier_plain, identifier_masked, secret_masked, raw_data::text
            FROM threat_intelligence_breachfinding
            WHERE id = %s
            """,
            [finding_id],
        )
        row = cursor.fetchone()
    return "|".join(str(part) for part in row)


class TestNoSecretPersistence:
    @pytest.mark.parametrize("endpoint,secret_field", list(ENDPOINTS_WITH_SECRET_FIELDS.items()))
    def test_secret_never_persisted_for_endpoint(
        self, endpoint, secret_field, tenant, website_asset
    ):
        for secret in KNOWN_SECRETS:
            payload = {"email": "victime@example.com", secret_field: secret}
            raw = RawFinding(endpoint=endpoint, payload=payload)
            created = services.ingest_raw_findings(
                tenant=tenant, asset=website_asset, raw_findings=[raw]
            )
            assert created, f"aucune fuite créée pour {endpoint}"
            finding = created[0]

            blob = _row_text_blob(finding.id)
            assert secret not in blob, f"secret trouvé en clair dans la ligne ({endpoint})"

    @pytest.mark.parametrize("secret_field", STEALER_EXTRA_SECRET_FIELDS)
    def test_stealer_financial_fields_never_persisted(self, secret_field, tenant, website_asset):
        """stealer expose aussi des données financières (carte bancaire,
        wallet crypto) — des secrets au même titre qu'un mot de passe, sur
        des noms de champs qu'aucune sous-chaîne générique ne peut deviner
        (ADR-014 §2) : couverts par correspondance exacte de nom de champ."""
        for secret in KNOWN_SECRETS:
            payload = {"usr": "victime", secret_field: secret}
            raw = RawFinding(endpoint="stealer", payload=payload)
            created = services.ingest_raw_findings(
                tenant=tenant, asset=website_asset, raw_findings=[raw]
            )
            assert created
            blob = _row_text_blob(created[0].id)
            assert secret not in blob, (
                f"secret trouvé en clair dans la ligne (stealer.{secret_field})"
            )

    def test_darkweb_and_radar_and_asm_have_no_secret_field(self, tenant, website_asset):
        """Ces trois endpoints n'ont, par construction du schéma réel,
        aucun champ secret — vérifie que secret_seen reste False plutôt que
        de masquer quelque chose par erreur (faux positif)."""
        for endpoint, payload in (
            ("darkweb", {"data": "example.com", "site": "ForumX", "found": "2026-01-01"}),
            ("radar", {"data": "example.com", "src": "scan", "found": "2026-01-01"}),
            ("asm", {"dom": "mail.example.com", "type": "mx", "found": "2026-01-01"}),
        ):
            raw = RawFinding(endpoint=endpoint, payload=payload)
            created = services.ingest_raw_findings(
                tenant=tenant, asset=website_asset, raw_findings=[raw]
            )
            assert created
            assert created[0].secret_seen is False
            assert created[0].secret_masked == ""

    def test_secret_absent_even_from_json_raw_data_field(self, tenant, website_asset):
        secret = "TotallyLeakedPassword42"
        raw = RawFinding(endpoint="creds", payload={"eml": "x@example.com", "pwd": secret})
        services.ingest_raw_findings(tenant=tenant, asset=website_asset, raw_findings=[raw])

        finding = BreachFinding.all_objects.get(tenant=tenant)
        assert secret not in json.dumps(finding.raw_data)
        assert finding.secret_seen is True
        assert finding.secret_masked != ""
        assert secret not in finding.secret_masked

    def test_cookie_metadata_fields_survive_unmasked_only_val_is_masked(
        self, tenant, website_asset
    ):
        """Non-regression for the "cookie" marker removal (see
        test_normalizer.py): cookie_name/cookie_path are structural
        metadata, not secrets — only "val" (the actual cookie) must be
        masked, the rest should remain usable for the tenant."""
        raw = RawFinding(
            endpoint="sessions",
            payload={
                "user_name": "victime",
                "cookie_name": "session_id",
                "cookie_path": "/account",
                "val": "TopSecretCookieValue123",
            },
        )
        created = services.ingest_raw_findings(
            tenant=tenant, asset=website_asset, raw_findings=[raw]
        )
        finding = created[0]
        assert finding.raw_data["cookie_name"] == "session_id"
        assert finding.raw_data["cookie_path"] == "/account"
        assert "TopSecretCookieValue123" not in json.dumps(finding.raw_data)
