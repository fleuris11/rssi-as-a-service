"""Public interface of the tenants app — other apps must go through here
instead of importing apps.tenants.models directly (CLAUDE.md architecture rule).
"""

import logging

from django.db import transaction
from django.utils.text import slugify

from .models import Membership, Tenant

logger = logging.getLogger(__name__)


def _unique_slug(name: str) -> str:
    base = slugify(name)[:200] or "entreprise"
    slug = base
    counter = 1
    while Tenant.objects.filter(slug=slug).exists():
        counter += 1
        slug = f"{base}-{counter}"
    return slug


@transaction.atomic
def create_tenant_with_owner(
    *, name: str, owner, sector: str = "", headcount: int | None = None
) -> Tenant:
    """Creates a tenant and makes ``owner`` its first admin member.

    Atomique : si l'ouverture de l'essai est refusée faute de capacité, on ne
    laisse pas derrière soi une entreprise à moitié créée.
    """
    tenant = Tenant.objects.create(
        name=name,
        slug=_unique_slug(name),
        sector=sector,
        headcount=headcount,
    )
    Membership.all_objects.create(tenant=tenant, user=owner, role=Membership.Role.ADMIN)

    # Essai automatique (Phase 10). Import différé : apps.billing importe
    # apps.tenants pour sa clé étrangère, un import au niveau module créerait
    # un cycle.
    from apps.billing import capacity
    from apps.billing import services as billing_services

    try:
        billing_services.start_trial(tenant=tenant, actor=owner)
    except capacity.PlatformCapacityError:
        # Le seul échec qui n'est PAS absorbé. Un essai engage des
        # emplacements de surveillance sur un pool partagé par toute la
        # plateforme : l'ouvrir quand même reviendrait à constater le
        # dépassement après coup. Créer l'entreprise sans son abonnement
        # serait à peine mieux — l'utilisateur obtiendrait un compte dont
        # toutes les fonctions refusent. On remonte donc le refus, à charge
        # de l'appelant de l'afficher (la transaction annule la création).
        raise
    except Exception:  # noqa: BLE001 - la création d'entreprise prime
        # Tout le reste (catalogue d'offres vide, offre par défaut retirée)
        # est un défaut de configuration de la plateforme, pas une limite
        # qu'on oppose au client : l'entreprise est créée sans abonnement,
        # état que les gardes d'entitlements traitent explicitement
        # (« aucun abonnement actif »).
        logger.warning(
            "Essai non ouvert pour l'entreprise %s : abonnement à créer manuellement.",
            tenant.id,
            exc_info=True,
        )

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


def list_members(tenant: Tenant):
    """Members of ``tenant``, independent of ambient tenant context —
    for Celery tasks and other code with no request/middleware to have set
    it, where list_tenant_members's request-scoped read isn't available."""
    return Membership.all_objects.select_related("user").filter(tenant=tenant)


def get_tenant(tenant_id):
    return Tenant.objects.filter(id=tenant_id).first()
