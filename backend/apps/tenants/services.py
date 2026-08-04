"""Public interface of the tenants app — other apps must go through here
instead of importing apps.tenants.models directly (CLAUDE.md architecture rule).
"""

from django.utils.text import slugify

from .models import Membership, Tenant


def _unique_slug(name: str) -> str:
    base = slugify(name)[:200] or "entreprise"
    slug = base
    counter = 1
    while Tenant.objects.filter(slug=slug).exists():
        counter += 1
        slug = f"{base}-{counter}"
    return slug


def create_tenant_with_owner(
    *, name: str, owner, sector: str = "", headcount: int | None = None
) -> Tenant:
    """Creates a tenant and makes ``owner`` its first admin member."""
    tenant = Tenant.objects.create(
        name=name,
        slug=_unique_slug(name),
        sector=sector,
        headcount=headcount,
    )
    Membership.all_objects.create(tenant=tenant, user=owner, role=Membership.Role.ADMIN)
    return tenant


def list_user_memberships(user):
    """All of a user's memberships, across every tenant (used before a
    tenant is selected, e.g. to populate a tenant switcher)."""
    return (
        Membership.all_objects.filter(user=user).select_related("tenant").order_by("tenant__name")
    )


def get_membership(*, user, tenant_id):
    return (
        Membership.all_objects.filter(user=user, tenant_id=tenant_id)
        .select_related("tenant")
        .first()
    )


def list_tenant_members(tenant: Tenant):
    """Members of ``tenant``. Relies on TenantScopingMiddleware having
    already set the tenant context for this request."""
    return Membership.objects.select_related("user").filter(tenant=tenant)
