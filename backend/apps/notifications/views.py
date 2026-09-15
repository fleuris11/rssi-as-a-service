from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.permissions import IsTenantMemberReadOnlyForReader

from . import inbox, services
from .serializers import NotificationPreferencesSerializer, NotificationSerializer


class NotificationInboxView(generics.ListAPIView):
    """GET /api/v1/notifications/inbox/ — ses notifications, paginées.

    ``?unread=1`` pour les seules non lues, ``?q=`` pour chercher dans le
    titre et le texte (point 22 : tout ce qui dépasse vingt lignes se
    cherche). Aucune entreprise à sélectionner : la cloche suit la PERSONNE.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return inbox.list_for_user(
            self.request.user,
            unread_only=self.request.query_params.get("unread") in ("1", "true"),
            search=(self.request.query_params.get("q") or "").strip(),
        )


class NotificationCountView(APIView):
    """GET /api/v1/notifications/inbox/count/ — le chiffre de la cloche.

    Une requête de comptage et rien d'autre : l'écran l'interroge
    périodiquement, elle doit rester la moins chère possible.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"unread": inbox.unread_count(request.user)})


class NotificationReadView(APIView):
    """POST /api/v1/notifications/inbox/read/ — ``{"ids": [...]}`` ou ``{"all": true}``.

    Ne touche que les notifications que la personne peut lire : un
    identifiant appartenant à quelqu'un d'autre est ignoré en silence, sans
    confirmer qu'il existe.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.data.get("all") is True:
            return Response({"updated": inbox.mark_all_read(request.user)})
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            return Response({"detail": "Liste d'identifiants invalide."}, status=400)
        return Response({"updated": inbox.mark_read(request.user, ids)})


class NotificationPreferencesView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def get(self, request):
        prefs = services.get_or_create_preferences(request.tenant)
        return Response(NotificationPreferencesSerializer(prefs).data)

    def patch(self, request):
        serializer = NotificationPreferencesSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        prefs = services.update_preferences(request.tenant, **serializer.validated_data)
        return Response(NotificationPreferencesSerializer(prefs).data)
