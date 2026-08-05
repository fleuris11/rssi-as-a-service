"""Per-tenant DRF throttling (cadrage §6). Rates are shrunk per-test via the
``throttle_rate`` fixture below, which patches ``SimpleRateThrottle.
THROTTLE_RATES`` (a plain dict) directly rather than overriding
``settings.REST_FRAMEWORK``: DRF snapshots ``api_settings.
DEFAULT_THROTTLE_RATES`` into that class attribute once, at import time —
a later ``settings`` override never reaches it, since ``api_settings.
reload()`` only clears its own cache, not this already-bound class
attribute. Patching the dict's contents in place is what actually takes
effect, and is what makes the limit reachable in a handful of requests
instead of hundreds.
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.throttling import SimpleRateThrottle

from apps.tenants.throttling import TenantAIRateThrottle, TenantRateThrottle

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


@pytest.fixture
def throttle_rate():
    originals = {}

    def _set(scope: str, rate: str):
        originals.setdefault(scope, SimpleRateThrottle.THROTTLE_RATES.get(scope))
        SimpleRateThrottle.THROTTLE_RATES[scope] = rate

    yield _set

    for scope, original in originals.items():
        if original is None:
            SimpleRateThrottle.THROTTLE_RATES.pop(scope, None)
        else:
            SimpleRateThrottle.THROTTLE_RATES[scope] = original


class TestThrottleKeying:
    """Unit-level: no tenant resolved -> no throttling (fails open, not
    closed — a request with no tenant is rejected by IsTenantMember/the
    scoping middleware for an unrelated reason, not silently rate-limited
    for a tenant that doesn't exist)."""

    def test_no_key_without_a_resolved_tenant(self, rf):
        request = rf.get("/api/v1/tenants/members/")
        request.tenant = None
        assert TenantRateThrottle().get_cache_key(request, view=None) is None
        assert TenantAIRateThrottle().get_cache_key(request, view=None) is None

    def test_key_scoped_to_the_tenant_id(self, rf, tenant):
        request = rf.get("/api/v1/tenants/members/")
        request.tenant = tenant
        key = TenantRateThrottle().get_cache_key(request, view=None)
        assert str(tenant.id) in key


class TestGeneralApiThrottling:
    def test_returns_429_once_the_tenant_rate_is_exhausted(
        self, api_client, tenant, tenant_owner, throttle_rate
    ):
        throttle_rate("tenant", "2/min")
        headers = _auth(api_client, tenant_owner, tenant)
        url = reverse("tenant-member-list")

        first = api_client.get(url, **headers)
        second = api_client.get(url, **headers)
        third = api_client.get(url, **headers)

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
        assert third.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_two_tenants_have_independent_budgets(
        self, api_client, tenant, tenant_owner, user_factory, tenant_factory, throttle_rate
    ):
        throttle_rate("tenant", "1/min")
        other_owner = user_factory(email="other-tenant-owner@example.com")
        other_tenant = tenant_factory(other_owner, name="Autre Entreprise")
        headers_a = _auth(api_client, tenant_owner, tenant)
        headers_b = _auth(api_client, other_owner, other_tenant)
        url = reverse("tenant-member-list")

        first_tenant_first_call = api_client.get(url, **headers_a)
        first_tenant_second_call = api_client.get(url, **headers_a)
        second_tenant_first_call = api_client.get(url, **headers_b)

        assert first_tenant_first_call.status_code == status.HTTP_200_OK
        assert first_tenant_second_call.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        # Tenant B's own budget is untouched by tenant A exhausting its own.
        assert second_tenant_first_call.status_code == status.HTTP_200_OK


class TestAIEndpointThrottling:
    def test_ai_endpoints_return_429_once_their_own_rate_is_exhausted(
        self, api_client, tenant, tenant_owner, throttle_rate
    ):
        throttle_rate("tenant_ai", "2/min")
        headers = _auth(api_client, tenant_owner, tenant)
        url = reverse("ai-document-list")

        first = api_client.get(url, **headers)
        second = api_client.get(url, **headers)
        third = api_client.get(url, **headers)

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
        assert third.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_ai_throttle_does_not_consume_the_general_tenant_budget(
        self, api_client, tenant, tenant_owner, throttle_rate
    ):
        # Distinct scopes (cadrage: "aligné sur les quotas", not merged with
        # the general API budget) — exhausting "tenant_ai" leaves "tenant"
        # untouched.
        throttle_rate("tenant_ai", "1/min")
        headers = _auth(api_client, tenant_owner, tenant)

        api_client.get(reverse("ai-document-list"), **headers)
        exhausted = api_client.get(reverse("ai-document-list"), **headers)
        general_api_call = api_client.get(reverse("tenant-member-list"), **headers)

        assert exhausted.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert general_api_call.status_code == status.HTTP_200_OK
