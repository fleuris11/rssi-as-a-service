from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Membership


class IsTenantMember(BasePermission):
    """Requires a valid ``X-Tenant-Id`` header for a tenant the user belongs to."""

    message = (
        "Sélectionnez une entreprise valide (en-tête X-Tenant-Id) pour accéder à cette ressource."
    )

    def has_permission(self, request, view):
        return getattr(request, "membership", None) is not None


class IsTenantAdmin(IsTenantMember):
    """Requires the admin role on the tenant selected via ``X-Tenant-Id``."""

    message = "Cette action nécessite le rôle administrateur sur l'entreprise."

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.membership.role == Membership.Role.ADMIN
        )


class IsTenantMemberReadOnlyForReader(IsTenantMember):
    """Default permission for tenant-scoped business resources (diagnostic,
    plan d'action, ...): any member can read, but the "reader" role is
    read-only — CLAUDE.md/cadrage US-1.2's three roles are meaningless
    unless this is enforced everywhere, not just on membership management."""

    message = "Le rôle lecteur ne permet pas de modifier cette ressource."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.membership.role != Membership.Role.READER
