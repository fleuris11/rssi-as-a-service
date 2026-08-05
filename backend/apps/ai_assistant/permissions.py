from rest_framework.permissions import BasePermission


class IsAIEnabled(BasePermission):
    """US-4.3: ``ai_enabled=false`` on the tenant makes every AI function
    return 403 — checked in addition to (not instead of) tenant membership,
    so a non-member still gets the ordinary 403 for that reason first."""

    message = "L'IA est désactivée pour cette entreprise."

    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        return tenant is not None and tenant.ai_enabled
