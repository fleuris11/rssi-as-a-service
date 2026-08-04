from rest_framework.permissions import BasePermission

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
