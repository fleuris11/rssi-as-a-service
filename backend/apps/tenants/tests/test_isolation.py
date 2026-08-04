"""Tenant isolation tests (CLAUDE.md: "un tenant A ne peut pas lire/écrire
les données d'un tenant B" — required for every API resource).

``TestTenantScopingMiddlewareAttackScenarios`` exercises the middleware's
own JWT -> user -> membership -> 403 decision directly, against
``auth-me`` — an endpoint with no ``IsTenantMember`` permission of its
own — specifically so a passing test proves the *middleware* rejects the
request, not some unrelated view-level permission check.
"""

import uuid

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


class TestTenantScopingMiddlewareAttackScenarios:
    """Scenarios (a)-(d) from the hardening review, hit against an
    endpoint (``auth-me``) that has no tenant-related permission class of
    its own — so a 403 here can only come from the middleware itself."""

    def test_a_header_for_a_tenant_the_user_is_not_a_member_of_is_rejected(
        self, api_client, two_tenants
    ):
        access = _login(api_client, "admin-a@example.com", "UnMotDePasseSolide2026")

        response = api_client.get(
            reverse("auth-me"),
            HTTP_AUTHORIZATION=f"Bearer {access}",
            HTTP_X_TENANT_ID=str(two_tenants["tenant_b"].id),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_b_missing_header_lets_the_request_through_with_no_tenant_selected(
        self, api_client, two_tenants
    ):
        """No X-Tenant-Id at all must never fall back to "show everything" —
        the middleware lets the request through (it doesn't itself require
        a tenant) but sets none, so any tenant-scoped resource fails closed
        (see TestTenantScopedManagerFailsClosed and
        TestTenantMemberListAPI.test_requires_tenant_header)."""
        access = _login(api_client, "admin-a@example.com", "UnMotDePasseSolide2026")

        response = api_client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {access}")

        assert response.status_code == status.HTTP_200_OK

    def test_c_header_for_a_tenant_that_does_not_exist_is_rejected(self, api_client, two_tenants):
        access = _login(api_client, "admin-a@example.com", "UnMotDePasseSolide2026")
        nonexistent_tenant_id = uuid.uuid4()
        assert nonexistent_tenant_id not in {two_tenants["tenant_a"].id, two_tenants["tenant_b"].id}

        response = api_client.get(
            reverse("auth-me"),
            HTTP_AUTHORIZATION=f"Bearer {access}",
            HTTP_X_TENANT_ID=str(nonexistent_tenant_id),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_c_bis_malformed_header_is_rejected_not_a_500(self, api_client, two_tenants):
        access = _login(api_client, "admin-a@example.com", "UnMotDePasseSolide2026")

        response = api_client.get(
            reverse("auth-me"),
            HTTP_AUTHORIZATION=f"Bearer {access}",
            HTTP_X_TENANT_ID="not-a-uuid",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_d_revoked_membership_is_rejected(self, api_client, two_tenants):
        """Membership.all_objects is the only manager the middleware
        trusts to resolve access — once the row is gone (revoked), a
        still-valid JWT for that user must no longer unlock the tenant."""
        access = _login(api_client, "admin-a@example.com", "UnMotDePasseSolide2026")
        tenant_a_id = two_tenants["tenant_a"].id
        Membership.all_objects.filter(tenant_id=tenant_a_id, user=two_tenants["owner_a"]).delete()

        response = api_client.get(
            reverse("auth-me"),
            HTTP_AUTHORIZATION=f"Bearer {access}",
            HTTP_X_TENANT_ID=str(tenant_a_id),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


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
