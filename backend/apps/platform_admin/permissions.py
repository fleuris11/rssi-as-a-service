"""Droits d'accès à la console d'administration.

Deux niveaux (phase 11), portés par ``PlatformAdminProfile`` :

- **complet** : tout, y compris la configuration de la plateforme et la
  gestion des autres administrateurs ;
- **commercial** : lecture de tous les écrans, plus la gestion des prospects.
  Un collaborateur qui prospecte n'a aucune raison de pouvoir suspendre un
  client ou modifier le catalogue.

``is_staff`` reste la porte d'entrée : sans lui, aucun accès. Le profil affine
ce que l'on peut y faire. Un compte ``is_staff`` sans profil est traité comme
**complet** — c'est le cas du fondateur et des comptes créés avant la phase 11,
qu'on ne veut pas voir perdre leurs droits au déploiement de cette migration.
"""

from rest_framework import permissions

from .models import PlatformAdminProfile

SAFE_METHODS = frozenset(["GET", "HEAD", "OPTIONS"])


def admin_level(user) -> str | None:
    """Niveau effectif, ou None si l'utilisateur n'est pas administrateur."""
    if not user or not user.is_authenticated or not user.is_staff:
        return None
    profile = getattr(user, "platform_admin", None)
    if profile is None:
        return PlatformAdminProfile.Level.FULL
    return profile.level


def can_write_everything(user) -> bool:
    return admin_level(user) == PlatformAdminProfile.Level.FULL


class IsPlatformAdmin(permissions.BasePermission):
    """Accès à la console, quel que soit le niveau."""

    message = "Cet espace est réservé à l'administration de la plateforme."

    def has_permission(self, request, view):
        return admin_level(request.user) is not None


class IsFullPlatformAdmin(permissions.BasePermission):
    """Écriture réservée au niveau complet ; lecture ouverte aux deux.

    La lecture reste ouverte à dessein : un commercial doit voir la fiche d'un
    client pour le rappeler. Ce sont les boutons d'action que son niveau lui
    refuse — et l'interface les affiche désactivés plutôt que masqués, comme
    les fonctionnalités hors offre côté client.
    """

    message = (
        "Votre niveau d'administration permet la consultation et le suivi "
        "commercial, pas cette opération. Demandez à un administrateur complet."
    )

    def has_permission(self, request, view):
        if admin_level(request.user) is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        return can_write_everything(request.user)
