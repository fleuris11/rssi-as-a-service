"""La veille, vue de la console (V2-7, ADR-034).

**Console uniquement.** Aucune de ces vues n'est joignable depuis un espace
client : la veille alimente le catalogue de référentiels, qui est partagé, et
une suggestion non triée n'a rien à faire sous les yeux d'un client. Toutes
portent ``IsPlatformAdmin`` ou ``IsFullPlatformAdmin``.

Lecture ouverte aux deux niveaux d'administrateur, décisions réservées au
niveau complet : trier la veille, c'est décider de ce que le produit exigera
de ses clients demain.
"""

import logging

from rest_framework import permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.assessments import services as assessments_services
from apps.platform_admin.models import AdminAuditLog
from apps.platform_admin.permissions import IsFullPlatformAdmin, IsPlatformAdmin
from apps.platform_admin.services import record_admin_action

from . import services
from .serializers import (
    IntegrateMeasureSerializer,
    ReviewUpdateSerializer,
    WatchSourceSerializer,
    WatchUpdateSerializer,
)

logger = logging.getLogger(__name__)


def _client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "")


class WatchQueueView(APIView):
    """La file de suggestions : ce qui a changé, où, et le lien vers la
    source officielle."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        source = None
        slug = request.query_params.get("source")
        if slug:
            source = services.get_source(slug=slug)
            if source is None:
                raise NotFound("Source introuvable.")

        updates = services.list_updates(status=request.query_params.get("status"), source=source)
        return Response(
            {
                "summary": services.queue_summary(),
                "health": services.sources_health(),
                "results": WatchUpdateSerializer(updates, many=True).data,
            }
        )


class WatchSourceListView(APIView):
    """Les sources suivies, leur état, et ce qu'on en attend."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        return Response(WatchSourceSerializer(services.list_sources(), many=True).data)


class WatchSourceDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFullPlatformAdmin]

    def patch(self, request, slug):
        """Corriger une adresse de flux, ou activer/désactiver une source.

        C'est ce qui permet d'installer le flux EUR-Lex ciblé sans
        redéploiement — la source est livrée inactive et sans adresse
        précisément pour être configurée ici.
        """
        source = services.get_source(slug=slug)
        if source is None:
            raise NotFound("Source introuvable.")

        serializer = WatchSourceSerializer(source, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_admin_action(
            actor=request.user,
            action=AdminAuditLog.Action.SETTING_CHANGED,
            target=f"Veille — {source.slug}",
            detail="Source de veille modifiée.",
            ip_address=_client_ip(request),
        )
        return Response(WatchSourceSerializer(source).data)


class WatchSourcePollView(APIView):
    """Relance une source à la main, sans attendre le passage hebdomadaire —
    typiquement juste après en avoir configuré une."""

    permission_classes = [permissions.IsAuthenticated, IsFullPlatformAdmin]

    def post(self, request, slug):
        source = services.get_source(slug=slug)
        if source is None:
            raise NotFound("Source introuvable.")
        try:
            rapport = services.poll_source(source)
        except services.WatchError as exc:
            # Le message d'erreur d'une source est déjà borné et destiné à
            # l'exploitant : ici, contrairement aux messages clients, il PEUT
            # être technique — c'est lui qui dit pourquoi le flux ne répond
            # pas.
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({**rapport, "source": WatchSourceSerializer(source).data})


class WatchUpdateReviewView(APIView):
    """Enregistre la décision d'un humain sur une suggestion."""

    permission_classes = [permissions.IsAuthenticated, IsFullPlatformAdmin]

    def post(self, request, update_id):
        update = services.get_update(update_id)
        if update is None:
            raise NotFound("Suggestion introuvable.")

        serializer = ReviewUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        referential = None
        if data["referential"]:
            referential = assessments_services.get_referential(slug=data["referential"])
            if referential is None:
                raise NotFound("Référentiel introuvable.")

        try:
            services.review_update(
                update,
                status=data["status"],
                reviewer=request.user,
                kind=data["kind"],
                note=data["note"],
                target_referential=referential,
            )
        except services.WatchError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        record_admin_action(
            actor=request.user,
            action=AdminAuditLog.Action.SETTING_CHANGED,
            target=update.title[:200],
            detail=f"Veille — suggestion {update.get_status_display().lower()}.",
            ip_address=_client_ip(request),
        )
        return Response(WatchUpdateSerializer(update).data)


class WatchUpdateIntegrateView(APIView):
    """Le seul endpoint qui ajoute une mesure à un référentiel depuis la
    veille. Il exige un contenu saisi, et journalise l'acte."""

    permission_classes = [permissions.IsAuthenticated, IsFullPlatformAdmin]

    def post(self, request, update_id):
        update = services.get_update(update_id)
        if update is None:
            raise NotFound("Suggestion introuvable.")

        serializer = IntegrateMeasureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        referential = assessments_services.get_referential(slug=data["referential"])
        if referential is None:
            raise NotFound("Référentiel introuvable.")

        try:
            mesure = services.integrate_as_measure(
                update,
                reviewer=request.user,
                referential=referential,
                domain_code=data["domain_code"],
                code=data["code"],
                official_title=data["official_title"],
                plain_language=data["plain_language"],
                level=data["level"],
                weight=data["weight"],
                effort=data["effort"],
                impact=data["impact"],
            )
        except (services.WatchError, assessments_services.AssessmentsError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        record_admin_action(
            actor=request.user,
            action=AdminAuditLog.Action.SETTING_CHANGED,
            target=f"{referential.name} — mesure {mesure.code}",
            detail=(f"Mesure ajoutée depuis la veille : « {update.title[:120]} » ({update.url})."),
            ip_address=_client_ip(request),
        )
        return Response(
            {"update": WatchUpdateSerializer(update).data, "measure_id": mesure.id},
            status=status.HTTP_201_CREATED,
        )


class WatchUpdateSummaryView(APIView):
    """Résumé par IA, déclenché à la main. Elle résume et ne conclut pas."""

    permission_classes = [permissions.IsAuthenticated, IsFullPlatformAdmin]

    def post(self, request, update_id):
        update = services.get_update(update_id)
        if update is None:
            raise NotFound("Suggestion introuvable.")
        try:
            services.summarize_update(update, reviewer=request.user)
        except services.WatchError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WatchUpdateSerializer(update).data)
