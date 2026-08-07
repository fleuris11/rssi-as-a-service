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

ENDPOINTS_WITH_SECRET_FIELDS = {
    "stealer": "password",
    "combo": "password",
    "creds": "password",
    "sessions": "cookie",
    "nhi": "token",
    "darkweb": "password",
    "docs": "credential",
}


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
            payload = {
                "email": "victime@example.com",
                secret_field: secret,
                "id": f"finding-{hash(secret) % 10_000}",
            }
            raw = RawFinding(endpoint=endpoint, payload=payload)
            created = services.ingest_raw_findings(
                tenant=tenant, asset=website_asset, raw_findings=[raw]
            )
            assert created, f"aucune fuite créée pour {endpoint}"
            finding = created[0]

            blob = _row_text_blob(finding.id)
            assert secret not in blob, f"secret trouvé en clair dans la ligne ({endpoint})"

    def test_secret_absent_even_from_json_raw_data_field(self, tenant, website_asset):
        secret = "TotallyLeakedPassword42"
        raw = RawFinding(endpoint="stealer", payload={"email": "x@example.com", "password": secret})
        services.ingest_raw_findings(tenant=tenant, asset=website_asset, raw_findings=[raw])

        finding = BreachFinding.all_objects.get(tenant=tenant)
        assert secret not in json.dumps(finding.raw_data)
        assert finding.secret_seen is True
        assert finding.secret_masked != ""
        assert secret not in finding.secret_masked
