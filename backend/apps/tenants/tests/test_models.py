import pytest
from django.db import IntegrityError

from apps.tenants.models import Membership
from apps.tenants.services import create_tenant_with_owner

pytestmark = pytest.mark.django_db


def test_duplicate_company_names_get_distinct_slugs(user_factory):
    owner_a = user_factory(email="a@example.com")
    owner_b = user_factory(email="b@example.com")

    tenant_a = create_tenant_with_owner(name="Boulangerie du Coin", owner=owner_a)
    tenant_b = create_tenant_with_owner(name="Boulangerie du Coin", owner=owner_b)

    assert tenant_a.slug != tenant_b.slug
    assert tenant_a.slug == "boulangerie-du-coin"
    assert tenant_b.slug == "boulangerie-du-coin-2"


def test_membership_is_unique_per_tenant_and_user(user_factory, tenant_factory):
    owner = user_factory(email="owner@example.com")
    tenant = tenant_factory(owner)

    with pytest.raises(IntegrityError):
        Membership.all_objects.create(tenant=tenant, user=owner, role=Membership.Role.READER)
