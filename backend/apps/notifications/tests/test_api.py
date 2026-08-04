import pytest
from django.urls import reverse
from rest_framework import status

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


class TestNotificationPreferencesAPI:
    def test_get_creates_defaults_on_first_access(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("notification-preferences"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["weather_enabled"] is True
        assert response.data["weather_time"] == "08:00:00"

    def test_patch_updates_weather_time(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.patch(
            reverse("notification-preferences"),
            {"weather_time": "07:30:00"},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["weather_time"] == "07:30:00"

    def test_reader_can_read_but_not_update(self, api_client, tenant, user_factory):
        reader = user_factory(email="reader@example.com")
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        headers = _auth(api_client, reader, tenant)

        read_response = api_client.get(reverse("notification-preferences"), **headers)
        write_response = api_client.patch(
            reverse("notification-preferences"),
            {"weather_enabled": False},
            format="json",
            **headers,
        )

        assert read_response.status_code == status.HTTP_200_OK
        assert write_response.status_code == status.HTTP_403_FORBIDDEN

    def test_preferences_are_isolated_per_tenant(self, api_client, user_factory, tenant_factory):
        owner_a = user_factory(email="owner-a@example.com")
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com")
        tenant_b = tenant_factory(owner_b, name="Entreprise B")

        headers_a = _auth(api_client, owner_a, tenant_a)
        api_client.patch(
            reverse("notification-preferences"),
            {"weather_time": "06:00:00"},
            format="json",
            **headers_a,
        )

        headers_b = _auth(api_client, owner_b, tenant_b)
        response_b = api_client.get(reverse("notification-preferences"), **headers_b)

        assert response_b.data["weather_time"] == "08:00:00"  # untouched default
