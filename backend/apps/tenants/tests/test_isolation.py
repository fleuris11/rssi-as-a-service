"""Tenant isolation tests (CLAUDE.md: "un tenant A ne peut pas lire/écrire
les données d'un tenant B" — required for every API resource)."""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.tenants.context import get_current_tenant_id, reset_current_tenant, set_current_tenant
from apps.tenants.models import Membership

pytestmark = pytest.mark.django_db


def _login(api_client, email, password):
    url = reverse("token-obtain-pair")
    response = api_client.post(url, {"email": email, "password": password}, format="json")
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


@pytest.fixture
def two_tenants(user_factory, tenant_factory):
    owner_a = user_factory(email="admin-a@example.com", password="UnMotDePasseSolide2026")
    owner_b = user_factory(email="admin-b@example.com", password="UnMotDePasseSolide2026")
    tenant_a = tenant_factory(owner_a, name="Entreprise A")
    tenant_b = tenant_factory(owner_b, name="Entreprise B")
    return {
        "owner_a": owner_a,
        "owner_b": owner_b,
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
    }


class TestTenantScopedManagerFailsClosed:
    def test_returns_nothing_without_tenant_context(self, two_tenants):
        assert get_current_tenant_id() is None
        assert list(Membership.objects.all()) == []

    def test_returns_only_current_tenant_rows_once_scoped(self, two_tenants):
        token = set_current_tenant(str(two_tenants["tenant_a"].id))
        try:
            members = list(Membership.objects.all())
        finally:
            reset_current_tenant(token)

        assert {m.tenant_id for m in members} == {two_tenants["tenant_a"].id}


class TestTenantMemberListAPI:
    def test_requires_tenant_header(self, api_client, two_tenants):
        access = _login(api_client, "admin-a@example.com", "UnMotDePasseSolide2026")
        url = reverse("tenant-member-list")

        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {access}")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_denies_access_to_a_foreign_tenant(self, api_client, two_tenants):
        access = _login(api_client, "admin-a@example.com", "UnMotDePasseSolide2026")
        url = reverse("tenant-member-list")

        response = api_client.get(
            url,
            HTTP_AUTHORIZATION=f"Bearer {access}",
            HTTP_X_TENANT_ID=str(two_tenants["tenant_b"].id),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_only_the_selected_tenant_members(self, api_client, two_tenants):
        access = _login(api_client, "admin-a@example.com", "UnMotDePasseSolide2026")
        url = reverse("tenant-member-list")

        response = api_client.get(
            url,
            HTTP_AUTHORIZATION=f"Bearer {access}",
            HTTP_X_TENANT_ID=str(two_tenants["tenant_a"].id),
        )

        assert response.status_code == status.HTTP_200_OK
        emails = {member["email"] for member in response.data["results"]}
        assert emails == {"admin-a@example.com"}
        assert "admin-b@example.com" not in emails


class TestMyTenantListAPI:
    def test_lists_only_the_users_own_tenants(self, api_client, two_tenants):
        access = _login(api_client, "admin-a@example.com", "UnMotDePasseSolide2026")
        url = reverse("tenant-list")

        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {access}")

        assert response.status_code == status.HTTP_200_OK
        names = {tenant["name"] for tenant in response.data["results"]}
        assert names == {"Entreprise A"}
        assert "Entreprise B" not in names
