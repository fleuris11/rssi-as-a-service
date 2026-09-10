"""Deux jeux de vues, deux permissions, un seul modèle.

Côté client (``urls.py``) : déposer une demande, suivre les siennes, retirer
celle qui n'a pas encore été traitée. Côté console (``console_urls.py``) : voir
la file, y répondre. Les deux vivent ici parce qu'il s'agit du même objet —
séparer le dépôt et le traitement dans deux apps aurait dupliqué le modèle.
"""

from rest_framework import permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform_admin.models import AdminAuditLog
from apps.platform_admin.permissions import IsFullPlatformAdmin, IsPlatformAdmin
from apps.platform_admin.services import record_admin_action
from apps.tenants.permissions import IsTenantMemberReadOnlyForReader

from . import services
from .serializers import (
    AccessRequestSerializer,
    ConsoleAccessRequestSerializer,
    CreateAccessRequestSerializer,
    HandleAccessRequestSerializer,
)


class AccessRequestListView(APIView):
    """Les demandes de CE client, et le formulaire pour en déposer une."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def get(self, request):
        demandes = services.list_requests(request.tenant, status=request.query_params.get("status"))
        return Response(AccessRequestSerializer(demandes, many=True).data)

    def post(self, request):
        serializer = CreateAccessRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            demande = services.create_request(
                tenant=request.tenant,
                user=request.user,
                subject_type=serializer.validated_data["subject_type"],
                subject_key=serializer.validated_data["subject_key"],
                reason=serializer.validated_data["reason"],
            )
        except services.UnknownSubjectError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except services.AccessRequestError as exc:
            # Déjà détenu, déjà demandé : ce sont des situations normales, pas
            # des pannes. 409 dit « rien à faire », pas « vous avez tort ».
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AccessRequestSerializer(demande).data, status=status.HTTP_201_CREATED)


class AccessRequestDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def delete(self, request, request_id):
        demande = services.get_request(request_id=request_id, tenant=request.tenant)
        if demande is None:
            raise NotFound("Demande introuvable.")
        try:
            services.cancel_request(demande, user=request.user)
        except services.AlreadyHandledError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AccessRequestSerializer(demande).data)


class ConsoleAccessRequestListView(APIView):
    """La file de la console : qui demande quoi, quand, et pourquoi."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        demandes = services.list_all_requests(
            status=request.query_params.get("status"),
            subject_type=request.query_params.get("subject_type"),
        )
        return Response(
            {
                # Deux compteurs : ce que personne n'a encore regardé, et
                # tout ce qui reste ouvert. Le second est la vraie charge de
                # travail — une demande contactée sans suite en fait partie.
                "pending_count": services.pending_count(),
                "open_count": services.open_count(),
                "results": ConsoleAccessRequestSerializer(demandes, many=True).data,
            }
        )


class ConsoleAccessRequestDetailView(APIView):
    """Faire avancer une demande. Lecture ouverte aux deux niveaux
    d'administrateur, écriture réservée au niveau complet : accorder un
    référentiel ou une fonctionnalité est un acte de gestion.

    V2-6 : la réponse n'est plus un booléen mais une ÉTAPE. Une demande passe
    par « client contacté » et « proposition envoyée » avant de se conclure —
    c'est ce qui permet au client de voir que quelqu'un s'occupe de lui plutôt
    que de lire « en attente » pendant dix jours.
    """

    permission_classes = [permissions.IsAuthenticated, IsFullPlatformAdmin]

    def post(self, request, request_id):
        demande = services.get_request(request_id=request_id)
        if demande is None:
            raise NotFound("Demande introuvable.")

        serializer = HandleAccessRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            demande, attribue = services.advance_request(
                demande,
                status=serializer.validated_data["status"],
                response=serializer.validated_data["response"],
                actor=request.user,
            )
        except services.AlreadyHandledError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except services.AccessRequestError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        record_admin_action(
            actor=request.user,
            action=AdminAuditLog.Action.ACCESS_REQUEST_HANDLED,
            tenant=demande.tenant,
            target=demande.subject_label,
            detail=("Accordée" if demande.status == demande.Status.GRANTED else "Refusée")
            + (" et attribuée automatiquement." if attribue else "."),
            ip_address=request.META.get("REMOTE_ADDR", ""),
        )
        return Response(
            {
                **ConsoleAccessRequestSerializer(demande).data,
                # Faux quand le sujet n'a pas d'attribution automatique : la
                # console doit dire ce qui reste à faire à la main plutôt que
                # de laisser croire que c'est réglé.
                "granted_automatically": attribue,
            }
        )
