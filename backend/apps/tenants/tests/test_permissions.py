import pytest
from django.test import RequestFactory

from apps.tenants.models import Membership
from apps.tenants.permissions import IsTenantAdmin, IsTenantMember, IsTenantMemberReadOnlyForReader

pytestmark = pytest.mark.django_db


def _request_with_membership(membership):
    request = RequestFactory().get("/")
    request.membership = membership
    return request


def test_is_tenant_member_denies_without_membership():
    request = RequestFactory().get("/")
    request.membership = None

    assert IsTenantMember().has_permission(request, view=None) is False


def test_is_tenant_member_allows_any_role(user_factory, tenant_factory):
    owner = user_factory(email="owner@example.com")
    tenant = tenant_factory(owner)
    membership = Membership.all_objects.get(tenant=tenant, user=owner)

    request = _request_with_membership(membership)

    assert IsTenantMember().has_permission(request, view=None) is True


def test_is_tenant_admin_denies_non_admin_roles(user_factory, tenant_factory):
    admin = user_factory(email="admin@example.com")
    tenant = tenant_factory(admin)
    reader = user_factory(email="reader@example.com")
    reader_membership = Membership.all_objects.create(
        tenant=tenant, user=reader, role=Membership.Role.READER
    )

    request = _request_with_membership(reader_membership)

    assert IsTenantAdmin().has_permission(request, view=None) is False


def test_is_tenant_admin_allows_admin_role(user_factory, tenant_factory):
    admin = user_factory(email="admin@example.com")
    tenant = tenant_factory(admin)
    admin_membership = Membership.all_objects.get(tenant=tenant, user=admin)

    request = _request_with_membership(admin_membership)

    assert IsTenantAdmin().has_permission(request, view=None) is True


def test_reader_can_read_but_not_write(user_factory, tenant_factory):
    admin = user_factory(email="admin@example.com")
    tenant = tenant_factory(admin)
    reader = user_factory(email="reader@example.com")
    reader_membership = Membership.all_objects.create(
        tenant=tenant, user=reader, role=Membership.Role.READER
    )

    get_request = RequestFactory().get("/")
    get_request.membership = reader_membership
    post_request = RequestFactory().post("/")
    post_request.membership = reader_membership

    assert IsTenantMemberReadOnlyForReader().has_permission(get_request, view=None) is True
    assert IsTenantMemberReadOnlyForReader().has_permission(post_request, view=None) is False


def test_contributor_can_write(user_factory, tenant_factory):
    admin = user_factory(email="admin@example.com")
    tenant = tenant_factory(admin)
    contributor = user_factory(email="contributor@example.com")
    contributor_membership = Membership.all_objects.create(
        tenant=tenant, user=contributor, role=Membership.Role.CONTRIBUTOR
    )

    post_request = RequestFactory().post("/")
    post_request.membership = contributor_membership

    assert IsTenantMemberReadOnlyForReader().has_permission(post_request, view=None) is True
