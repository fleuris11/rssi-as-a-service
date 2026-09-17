from rest_framework.permissions import SAFE_METHODS

from apps.tenants.models import Membership
from apps.tenants.permissions import IsTenantMember


class IsTenantAdminForWrites(IsTenantMember):
    """Lecture ouverte à tout membre, écriture réservée aux administrateurs.

    Décider qui doit être formé, et jusqu'à quand, est un acte de gestion du
    personnel — pas une contribution technique. ``IsTenantMemberReadOnlyForReader``,
    la permission par défaut des ressources métier, aurait laissé un
    contributeur inscrire des salariés et révoquer leurs accès.
    """

    message = "Seul un administrateur de l'entreprise peut gérer les formations."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.membership.role == Membership.Role.ADMIN
