"""Phase 8A — Radar pré-incident. Le point produit à protéger : ce widget ne
montre QUE des signaux d'exposition publique (radar, dark web, surface
d'attaque), jamais un constat de fuite. Y laisser fuiter un finding
« stealer » viderait la distinction de son sens (et le message rassurant
« rien n'a encore fuité » deviendrait faux).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset
from apps.threat_intelligence import services
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd123"


def _auth(api_client, user, tenant):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": user.email, "password": PASSWORD}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return {
        "HTTP_AUTHORIZATION": f"Bearer {response.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


def _ingest(tenant, asset, endpoint, payload):
    return services.ingest_raw_findings(
        tenant=tenant, asset=asset, raw_findings=[RawFinding(endpoint=endpoint, payload=payload)]
    )[0]


class TestSignalClassification:
    def test_lookalike_domain_registration_is_a_typosquat_signal(self, tenant, website_asset):
        finding = _ingest(
            tenant,
            website_asset,
            "radar",
            {
                "data": "exemp1e.fr",
                "src": "Enregistrement de domaine similaire",
                "found": "2026-01-01",
            },
        )
        assert services.classify_pre_incident_signal(finding) == services.SIGNAL_TYPOSQUAT

    def test_plain_public_mention_is_informational_not_typosquat(self, tenant, website_asset):
        finding = _ingest(
            tenant,
            website_asset,
            "radar",
            {"data": "example.com", "src": "Mention sur un forum", "found": "2026-01-01"},
        )
        assert services.classify_pre_incident_signal(finding) == services.SIGNAL_PUBLIC_MENTION

    def test_darkweb_is_its_own_signal(self, tenant, website_asset):
        finding = _ingest(
            tenant,
            website_asset,
            "darkweb",
            {"data": "example.com", "site": "F", "found": "2026-01-01"},
        )
        assert services.classify_pre_incident_signal(finding) == services.SIGNAL_DARKWEB

    def test_asm_phishing_subtype_is_a_typosquat_signal(self, tenant, website_asset):
        finding = _ingest(
            tenant,
            website_asset,
            "asm",
            {"dom": "examp1e.co", "type": "pphish", "found": "2026-01-01"},
        )
        assert services.classify_pre_incident_signal(finding) == services.SIGNAL_TYPOSQUAT

    def test_asm_inventory_subtype_is_only_attack_surface(self, tenant, website_asset):
        finding = _ingest(
            tenant,
            website_asset,
            "asm",
            {"dom": "mail.example.com", "type": "mx", "found": "2026-01-01"},
        )
        assert services.classify_pre_incident_signal(finding) == services.SIGNAL_ATTACK_SURFACE


class TestPreIncidentAPI:
    def test_returns_grouped_signals_with_plain_language_and_urgency(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        _ingest(
            tenant,
            website_asset,
            "radar",
            {
                "data": "exemp1e.fr",
                "src": "Enregistrement de domaine similaire",
                "found": "2026-01-01",
            },
        )
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-pre-incident"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total"] == 1
        signal = response.data["signals"][0]
        assert signal["signal_type"] == services.SIGNAL_TYPOSQUAT
        assert signal["urgency"] == "high"
        assert len(signal["plain_language"]) > 40  # une vraie phrase, pas un code
        assert signal["items"][0]["detail"] == "exemp1e.fr"

    def test_excludes_actual_breach_findings(self, api_client, tenant, tenant_owner, website_asset):
        """Un stealer/creds est un constat de fuite — il n'a rien à faire
        dans la carte « avant-coureur »."""
        _ingest(tenant, website_asset, "stealer", {"usr": "a@example.com", "pwd": "secret"})
        _ingest(tenant, website_asset, "creds", {"eml": "b@example.com", "pwd": "secret"})
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-pre-incident"), **headers)

        assert response.data["total"] == 0

    def test_excludes_treated_signals(self, api_client, tenant, tenant_owner, website_asset):
        finding = _ingest(
            tenant,
            website_asset,
            "darkweb",
            {"data": "example.com", "site": "F", "found": "2026-01-01"},
        )
        services.set_finding_status(finding, status="treated", user=tenant_owner)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-pre-incident"), **headers)

        assert response.data["total"] == 0

    def test_empty_state_is_a_valid_calm_response(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("breach-pre-incident"), **headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"signals": [], "total": 0}

    def test_groups_several_findings_of_the_same_nature(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        _ingest(
            tenant,
            website_asset,
            "radar",
            {
                "data": "exemp1e.fr",
                "src": "Enregistrement de domaine similaire",
                "found": "2026-01-01",
            },
        )
        _ingest(
            tenant,
            website_asset,
            "asm",
            {"dom": "examp1e.co", "type": "pphish", "found": "2026-02-01"},
        )
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-pre-incident"), **headers)

        assert len(response.data["signals"]) == 1
        assert response.data["signals"][0]["count"] == 2

    def test_is_tenant_scoped(self, api_client, user_factory, tenant_factory):
        owner_a = user_factory(email="owner-a@example.com", password=PASSWORD)
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com", password=PASSWORD)
        tenant_b = tenant_factory(owner_b, name="Entreprise B")
        asset_b = monitoring_services.create_asset(
            tenant=tenant_b,
            user=owner_b,
            type=Asset.Type.WEBSITE,
            value="https://b.example.com",
            ownership_confirmed=True,
        )
        _ingest(
            tenant_b,
            asset_b,
            "darkweb",
            {"data": "b.example.com", "site": "F", "found": "2026-01-01"},
        )

        headers_a = _auth(api_client, owner_a, tenant_a)
        response = api_client.get(reverse("breach-pre-incident"), **headers_a)

        assert response.data["total"] == 0

    def test_requires_authentication(self, api_client):
        response = api_client.get(reverse("breach-pre-incident"))
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
