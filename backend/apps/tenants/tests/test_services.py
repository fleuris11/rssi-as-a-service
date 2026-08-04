import pytest

from apps.tenants.models import Membership
from apps.tenants.services import (
    create_tenant_with_owner,
    get_membership,
    list_tenant_members,
    list_user_memberships,
)

pytestmark = pytest.mark.django_db


def test_create_tenant_with_owner_grants_admin_role(user_factory):
    owner = user_factory(email="owner@example.com")

    tenant = create_tenant_with_owner(name="Entreprise A", owner=owner)

    membership = Membership.all_objects.get(tenant=tenant, user=owner)
    assert membership.role == Membership.Role.ADMIN


def test_list_user_memberships_covers_every_tenant(user_factory, tenant_factory):
    user = user_factory(email="multi@example.com")
    tenant_factory(user, name="Entreprise A")
    tenant_factory(user, name="Entreprise B")

    memberships = list(list_user_memberships(user))

    assert {m.tenant.name for m in memberships} == {"Entreprise A", "Entreprise B"}


def test_get_membership_returns_none_for_unrelated_tenant(user_factory, tenant_factory):
    owner = user_factory(email="owner@example.com")
    outsider = user_factory(email="outsider@example.com")
    tenant = tenant_factory(owner)

    assert get_membership(user=outsider, tenant_id=tenant.id) is None
    assert get_membership(user=owner, tenant_id=tenant.id) is not None


def test_list_tenant_members_requires_scoped_context(user_factory, tenant_factory):
    """Without TenantScopingMiddleware having set the context (as happens
    outside a request, e.g. here), the scoped ``objects`` manager that
    list_tenant_members relies on fails closed."""
    owner = user_factory(email="owner@example.com")
    tenant = tenant_factory(owner)

    assert list(list_tenant_members(tenant)) == []
