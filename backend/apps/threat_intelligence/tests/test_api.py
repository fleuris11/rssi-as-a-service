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
        assert "complet" in response.data["detail"]

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
    def test_status_reflects_cooldown_and_pool(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("threat-intelligence-status"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["cooldown_active"] is False
        assert response.data["pool_capacity"] == 15


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
