import pytest
from django.urls import reverse
from rest_framework import status

from apps.monitoring import services
from apps.monitoring.models import Alert, Asset, CheckResult
from apps.tenants.models import Membership

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


class TestAssetCreation:
    def test_create_requires_ownership_checkbox(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("asset-list"),
            {"type": "website", "value": "https://example.com", "ownership_confirmed": False},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Asset.all_objects.count() == 0

    def test_create_website_asset(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("asset-list"),
            {"type": "website", "value": "https://example.com", "ownership_confirmed": True},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["value"] == "https://example.com"

    def test_rejects_invalid_url_for_website(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("asset-list"),
            {"type": "website", "value": "not-a-url", "ownership_confirmed": True},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rejects_invalid_domain_for_email_asset(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("asset-list"),
            {"type": "email_domain", "value": "not a domain!!", "ownership_confirmed": True},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reader_cannot_create_asset(self, api_client, tenant, user_factory):
        reader = user_factory(email="reader@example.com")
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        headers = _auth(api_client, reader, tenant)

        response = api_client.post(
            reverse("asset-list"),
            {"type": "website", "value": "https://example.com", "ownership_confirmed": True},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestAssetManagement:
    def test_list_assets(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.WEBSITE,
            value="https://example.com",
            ownership_confirmed=True,
        )

        response = api_client.get(reverse("asset-list"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_patch_toggles_active(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        asset = services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.WEBSITE,
            value="https://example.com",
            ownership_confirmed=True,
        )

        response = api_client.patch(
            reverse("asset-detail", args=[asset.id]),
            {"is_active": False},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False

    def test_delete_asset(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        asset = services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.WEBSITE,
            value="https://example.com",
            ownership_confirmed=True,
        )

        response = api_client.delete(reverse("asset-detail", args=[asset.id]), **headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Asset.all_objects.filter(id=asset.id).exists()


class TestDashboardAndAlerts:
    def test_dashboard_reflects_latest_checks_and_open_alerts(
        self, api_client, tenant, tenant_owner
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        asset = services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.WEBSITE,
            value="https://example.com",
            ownership_confirmed=True,
        )
        CheckResult.all_objects.create(
            tenant=tenant,
            asset=asset,
            check_type=CheckResult.CheckType.HTTP_UPTIME,
            status=CheckResult.Status.OK,
            details={"status_code": 200},
        )
        Alert.all_objects.create(
            tenant=tenant,
            asset=asset,
            alert_type=Alert.AlertType.SSL_EXPIRING,
            severity=Alert.Severity.WARNING,
        )

        response = api_client.get(reverse("monitoring-dashboard"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        row = response.data[0]
        assert row["asset"]["value"] == "https://example.com"
        assert row["latest_checks"]["http_uptime"]["status"] == "ok"
        assert len(row["open_alerts"]) == 1

    def test_open_alerts_endpoint(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        asset = services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.WEBSITE,
            value="https://example.com",
            ownership_confirmed=True,
        )
        Alert.all_objects.create(
            tenant=tenant,
            asset=asset,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )

        response = api_client.get(reverse("monitoring-open-alerts"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1


class TestMonitoringTenantIsolation:
    def test_cannot_read_another_tenants_asset(self, api_client, user_factory, tenant_factory):
        owner_a = user_factory(email="owner-a@example.com")
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com")
        tenant_b = tenant_factory(owner_b, name="Entreprise B")

        asset_b = services.create_asset(
            tenant=tenant_b,
            user=owner_b,
            type=Asset.Type.WEBSITE,
            value="https://b.example.com",
            ownership_confirmed=True,
        )

        headers_a = _auth(api_client, owner_a, tenant_a)
        response = api_client.get(reverse("asset-detail", args=[asset_b.id]), **headers_a)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_dashboard_is_scoped_per_tenant(self, api_client, user_factory, tenant_factory):
        owner_a = user_factory(email="owner-a@example.com")
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com")
        tenant_b = tenant_factory(owner_b, name="Entreprise B")

        services.create_asset(
            tenant=tenant_b,
            user=owner_b,
            type=Asset.Type.WEBSITE,
            value="https://b.example.com",
            ownership_confirmed=True,
        )

        headers_a = _auth(api_client, owner_a, tenant_a)
        response = api_client.get(reverse("monitoring-dashboard"), **headers_a)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_open_alerts_are_scoped_per_tenant(self, api_client, user_factory, tenant_factory):
        owner_a = user_factory(email="owner-a@example.com")
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com")
        tenant_b = tenant_factory(owner_b, name="Entreprise B")

        asset_b = services.create_asset(
            tenant=tenant_b,
            user=owner_b,
            type=Asset.Type.WEBSITE,
            value="https://b.example.com",
            ownership_confirmed=True,
        )
        Alert.all_objects.create(
            tenant=tenant_b,
            asset=asset_b,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )

        headers_a = _auth(api_client, owner_a, tenant_a)
        response = api_client.get(reverse("monitoring-open-alerts"), **headers_a)

        assert response.data["count"] == 0
