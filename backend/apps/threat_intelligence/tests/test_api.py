from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset
from apps.tenants.models import Membership
from apps.threat_intelligence import services
from apps.threat_intelligence.models import MonitoredAsset
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db


def _login(api_client, email, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


def _auth(api_client, user, tenant):
    access = _login(api_client, user.email)
    return {"HTTP_AUTHORIZATION": f"Bearer {access}", "HTTP_X_TENANT_ID": str(tenant.id)}


class TestBreachFindingAPI:
    def test_list_findings(self, api_client, tenant, tenant_owner, website_asset):
        raw = RawFinding(endpoint="stealer", payload={"email": "a@example.com"})
        services.ingest_raw_findings(tenant=tenant, asset=website_asset, raw_findings=[raw])
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-finding-list"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert "secret_masked" in response.data["results"][0]
        assert "raw_data" not in response.data["results"][0]

    def test_filter_by_status(self, api_client, tenant, tenant_owner, website_asset):
        raw = RawFinding(endpoint="stealer", payload={"email": "a@example.com"})
        services.ingest_raw_findings(tenant=tenant, asset=website_asset, raw_findings=[raw])
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-finding-list"), {"status": "treated"}, **headers)

        assert response.data["count"] == 0

    def test_patch_marks_finding_treated(self, api_client, tenant, tenant_owner, website_asset):
        raw = RawFinding(endpoint="stealer", payload={"email": "a@example.com"})
        finding = services.ingest_raw_findings(
            tenant=tenant, asset=website_asset, raw_findings=[raw]
        )[0]
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.patch(
            reverse("breach-finding-detail", args=[finding.id]),
            {"status": "treated"},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "treated"

    def test_reader_cannot_patch_finding(self, api_client, tenant, website_asset, user_factory):
        raw = RawFinding(endpoint="stealer", payload={"email": "a@example.com"})
        finding = services.ingest_raw_findings(
            tenant=tenant, asset=website_asset, raw_findings=[raw]
        )[0]
        reader = user_factory(email="reader@example.com")
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        headers = _auth(api_client, reader, tenant)

        response = api_client.patch(
            reverse("breach-finding-detail", args=[finding.id]),
            {"status": "ignored"},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_read_another_tenants_finding(self, api_client, user_factory, tenant_factory):
        owner_a = user_factory(email="owner-a@example.com")
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com")
        tenant_b = tenant_factory(owner_b, name="Entreprise B")
        asset_b = monitoring_services.create_asset(
            tenant=tenant_b,
            user=owner_b,
            type=Asset.Type.WEBSITE,
            value="https://b.example.com",
            ownership_confirmed=True,
        )
        raw = RawFinding(endpoint="stealer", payload={"email": "a@example.com"})
        finding_b = services.ingest_raw_findings(
            tenant=tenant_b, asset=asset_b, raw_findings=[raw]
        )[0]

        headers_a = _auth(api_client, owner_a, tenant_a)
        response = api_client.get(
            reverse("breach-finding-detail", args=[finding_b.id]), **headers_a
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_findings_are_scoped_per_tenant_in_list(self, api_client, user_factory, tenant_factory):
        owner_a = user_factory(email="owner-a@example.com")
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com")
        tenant_b = tenant_factory(owner_b, name="Entreprise B")
        asset_b = monitoring_services.create_asset(
            tenant=tenant_b,
            user=owner_b,
            type=Asset.Type.WEBSITE,
            value="https://b.example.com",
            ownership_confirmed=True,
        )
        raw = RawFinding(endpoint="stealer", payload={"email": "a@example.com"})
        services.ingest_raw_findings(tenant=tenant_b, asset=asset_b, raw_findings=[raw])

        headers_a = _auth(api_client, owner_a, tenant_a)
        response = api_client.get(reverse("breach-finding-list"), **headers_a)

        assert response.data["count"] == 0


class TestMonitoredAssetAPI:
    def test_register_asset_for_realtime_monitoring(
        self, api_client, tenant, tenant_owner, website_asset, fake_provider, settings
    ):
        settings.BREACHSENSE_WEBHOOK_CALLBACK_URL = "https://api.example.com/webhook"
        headers = _auth(api_client, tenant_owner, tenant)

        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            response = api_client.post(
                reverse("monitored-asset-list"),
                {"asset_id": website_asset.id},
                format="json",
                **headers,
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert MonitoredAsset.all_objects.filter(asset=website_asset).exists()

    def test_register_returns_400_when_pool_full(
        self, api_client, tenant, tenant_owner, website_asset, fake_provider, settings
    ):
        settings.BREACHSENSE_WEBHOOK_CALLBACK_URL = "https://api.example.com/webhook"
        settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE = 0
        headers = _auth(api_client, tenant_owner, tenant)

        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            response = api_client.post(
                reverse("monitored-asset-list"),
                {"asset_id": website_asset.id},
                format="json",
                **headers,
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.data["detail"]
        # Le plafond est celui de la PLATEFORME, partagé par tous les clients
        # (ADR-013) : le client lit une limite de son offre et une sortie, pas
        # le nom du fournisseur ni la taille du parc.
        assert "offre" in detail and "contactez-nous" in detail.lower()
        assert "breachsense" not in detail.lower()
        assert not any(c.isdigit() for c in detail)

    def test_unregister_asset(
        self, api_client, tenant, tenant_owner, website_asset, fake_provider, settings
    ):
        settings.BREACHSENSE_WEBHOOK_CALLBACK_URL = "https://api.example.com/webhook"
        headers = _auth(api_client, tenant_owner, tenant)
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            services.register_monitored_asset(tenant=tenant, asset=website_asset)

            response = api_client.delete(
                reverse("monitored-asset-detail", args=[website_asset.id]), **headers
            )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert services.list_monitored_assets(tenant).count() == 0


class TestBreachScanAPI:
    def test_trigger_manual_scan_returns_job(self, api_client, tenant, tenant_owner, website_asset):
        headers = _auth(api_client, tenant_owner, tenant)
        with patch("apps.threat_intelligence.tasks.run_breach_scan_task.delay"):
            response = api_client.post(reverse("breach-scan-trigger"), {}, format="json", **headers)

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["status"] == "pending"

    def test_trigger_blocked_by_cooldown(self, api_client, tenant, tenant_owner):
        services.mark_scan_cooldown(tenant)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(reverse("breach-scan-trigger"), {}, format="json", **headers)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_poll_job_status(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        job = services.create_scan_job(tenant=tenant, triggered_by=services.TriggeredBy.MANUAL)

        response = api_client.get(reverse("breach-scan-job-detail", args=[job.id]), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == job.id


class TestThreatIntelligenceStatusAPI:
    def test_status_reflects_cooldown(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("threat-intelligence-status"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["cooldown_active"] is False

    def test_status_never_exposes_platform_wide_figures(self, api_client, tenant, tenant_owner):
        """Cette vue renvoyait le budget de requêtes PARTAGÉ et l'occupation du
        pool de licence, que l'écran affichait tels quels (« quota restant
        (plateforme) : 971 », « 0 / 15 emplacements »). Un client y lisait la
        consommation des autres — une fuite entre locataires par l'interface."""
        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("threat-intelligence-status"), **headers)

        interdits = {"quota_remaining", "pool_used", "pool_capacity", "pool_remaining"}
        fuites = interdits & set(response.data)
        assert not fuites, f"Champs de plateforme exposés au client : {sorted(fuites)}"

    def test_status_reports_the_tenant_own_allowance(self, api_client, tenant, tenant_owner):
        from apps.billing.models import Plan, Subscription

        plan = Plan.objects.create(
            code="test-statut",
            name="Test statut",
            monitored_assets=3,
            monthly_scans=7,
            max_users=5,
            status=Plan.Status.PUBLISHED,
            price_monthly=10,
        )
        # Le tenant de test porte déjà un abonnement (un seul par entreprise) :
        # on le rebranche sur cette offre plutôt que d'en créer un second.
        Subscription.objects.update_or_create(
            tenant=tenant,
            defaults={"plan": plan, "status": Subscription.Status.ACTIVE},
        )

        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("threat-intelligence-status"), **headers)

        # Ce que le client peut lire : ce que SON offre comprend, rien d'autre.
        assert response.data["scans_quota"] == 7
        assert response.data["scans_used"] == 0
        assert response.data["scans_remaining"] == 7
        assert response.data["monitored_quota"] == 3
        assert response.data["monitored_used"] == 0


class TestAdminStatusAPI:
    def test_non_staff_forbidden(self, api_client, tenant_owner, tenant):
        access = _login(api_client, tenant_owner.email)
        response = api_client.get(
            reverse("threat-intelligence-admin-status"), HTTP_AUTHORIZATION=f"Bearer {access}"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_can_view_platform_wide_status(self, api_client, user_factory):
        staff = user_factory(email="staff@example.com", is_staff=True)
        access = _login(api_client, staff.email)

        response = api_client.get(
            reverse("threat-intelligence-admin-status"), HTTP_AUTHORIZATION=f"Bearer {access}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert "quota" in response.data
        assert "pool" in response.data
        assert "recent_usage" in response.data
