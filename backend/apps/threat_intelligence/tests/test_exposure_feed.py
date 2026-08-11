"""Phase 8B — le fil d'exposition et l'arbitrage d'affichage qui l'accompagne.

Deux propriétés produit sont vérifiées ici en plus du fonctionnement :
- la liste Compromissions ne montre plus que des fuites **avérées** (les
  signaux pré-incident ont leur carte, avec leurs propres actions) ;
- le fil d'exposition, lui, montre l'exposition **complète** d'un actif —
  la séparation liste/carte est un choix d'affichage, pas de fond.
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


TYPOSQUAT_PAYLOAD = {
    "data": "exemp1e.fr",
    "src": "Enregistrement de domaine similaire",
    "found": "2026-01-01",
}


class TestFindingsListExcludesPreIncident:
    def test_list_shows_only_confirmed_leaks(self, tenant, website_asset):
        _ingest(tenant, website_asset, "creds", {"eml": "a@example.com", "pwd": "x"})
        _ingest(tenant, website_asset, "radar", TYPOSQUAT_PAYLOAD)
        _ingest(
            tenant,
            website_asset,
            "darkweb",
            {"data": "example.com", "site": "F", "found": "2026-01-01"},
        )

        endpoints = {f.source_endpoint for f in services.list_findings(tenant)}
        assert endpoints == {"creds"}

    def test_include_pre_incident_restores_the_full_picture(self, tenant, website_asset):
        _ingest(tenant, website_asset, "creds", {"eml": "a@example.com", "pwd": "x"})
        _ingest(tenant, website_asset, "radar", TYPOSQUAT_PAYLOAD)

        full = services.list_findings(tenant, include_pre_incident=True)
        assert full.count() == 2

    def test_api_list_excludes_pre_incident(self, api_client, tenant, tenant_owner, website_asset):
        _ingest(tenant, website_asset, "creds", {"eml": "a@example.com", "pwd": "x"})
        _ingest(tenant, website_asset, "radar", TYPOSQUAT_PAYLOAD)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-finding-list"), **headers)

        assert response.data["count"] == 1
        assert response.data["results"][0]["source_endpoint"] == "creds"


class TestPreIncidentHistory:
    def test_treated_signals_leave_the_active_card(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        finding = _ingest(tenant, website_asset, "radar", TYPOSQUAT_PAYLOAD)
        headers = _auth(api_client, tenant_owner, tenant)

        api_client.patch(
            reverse("breach-finding-detail", args=[finding.id]),
            {"status": "treated"},
            format="json",
            **headers,
        )

        active = api_client.get(reverse("breach-pre-incident"), **headers)
        assert active.data["total"] == 0

    def test_treated_signals_remain_visible_in_history(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        finding = _ingest(tenant, website_asset, "radar", TYPOSQUAT_PAYLOAD)
        services.set_finding_status(finding, status="treated", user=tenant_owner)
        headers = _auth(api_client, tenant_owner, tenant)

        history = api_client.get(reverse("breach-pre-incident"), {"status": "treated"}, **headers)

        assert history.data["total"] == 1


class TestExposureFeedAPI:
    def test_groups_by_asset_with_score_and_components(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        _ingest(tenant, website_asset, "creds", {"eml": "a@example.com", "pwd": "x"})
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-exposure-feed"), **headers)

        assert response.status_code == status.HTTP_200_OK
        group = response.data["assets"][0]
        assert group["asset_value"] == website_asset.value
        assert group["score"] > 0
        assert group["level_label"]
        assert group["components"][0]["detail"]

    def test_includes_plain_language_and_recommended_action(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        _ingest(tenant, website_asset, "sessions", {"user_name": "u", "val": "cookie"})
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-exposure-feed"), **headers)

        finding = response.data["assets"][0]["findings"][0]
        # La spécificité produit du cas "sessions" : le cookie contourne AUSSI
        # la double authentification — c'est ce qui doit être dit.
        assert "double authentification" in finding["meaning"]
        assert finding["recommended_action"]

    def test_includes_pre_incident_findings_in_asset_exposure(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        _ingest(tenant, website_asset, "radar", TYPOSQUAT_PAYLOAD)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-exposure-feed"), **headers)

        assert response.data["total_findings"] == 1

    def test_assets_are_sorted_by_score_descending(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        second_asset = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="example.com",
            ownership_confirmed=True,
        )
        _ingest(tenant, website_asset, "radar", TYPOSQUAT_PAYLOAD)  # attention
        _ingest(tenant, second_asset, "sessions", {"user_name": "u", "val": "cookie"})  # critique
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-exposure-feed"), **headers)

        scores = [group["score"] for group in response.data["assets"]]
        assert scores == sorted(scores, reverse=True)
        assert response.data["assets"][0]["asset_value"] == second_asset.value

    def test_excludes_treated_findings(self, api_client, tenant, tenant_owner, website_asset):
        finding = _ingest(tenant, website_asset, "creds", {"eml": "a@example.com", "pwd": "x"})
        services.set_finding_status(finding, status="treated", user=tenant_owner)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-exposure-feed"), **headers)

        assert response.data["assets"] == []
        assert response.data["total_findings"] == 0

    def test_empty_feed_is_a_valid_response(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("breach-exposure-feed"), **headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["assets"] == []
        assert response.data["highest_score"] == 0

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
        _ingest(tenant_b, asset_b, "creds", {"eml": "b@example.com", "pwd": "x"})

        headers_a = _auth(api_client, owner_a, tenant_a)
        response = api_client.get(reverse("breach-exposure-feed"), **headers_a)

        assert response.data["assets"] == []

    def test_requires_authentication(self, api_client):
        response = api_client.get(reverse("breach-exposure-feed"))
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_never_exposes_a_secret(self, api_client, tenant, tenant_owner, website_asset):
        """Le fil affiche beaucoup de choses sur une fuite — jamais le secret
        (ADR-014 : il ne sort que par l'endpoint de révélation)."""
        _ingest(tenant, website_asset, "creds", {"eml": "a@example.com", "pwd": "SuperSecret42"})
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-exposure-feed"), **headers)

        assert "SuperSecret42" not in str(response.data)
