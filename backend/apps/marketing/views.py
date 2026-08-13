import logging

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from . import services
from .models import DemoRequest
from .serializers import (
    DemoRequestAdminSerializer,
    DemoRequestSerializer,
    DemoRequestStatusUpdateSerializer,
)

logger = logging.getLogger(__name__)


class DemoRequestRateThrottle(SimpleRateThrottle):
    """Par IP : l'endpoint est public, il n'y a pas d'utilisateur à qui
    rattacher un compteur. Seuil bas — remplir un formulaire de démonstration
    plus de trois fois par heure n'a aucun usage légitime."""

    scope = "demo_request"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class DemoRequestCreateView(APIView):
    """POST /api/v1/public/demo-requests/ — endpoint **public** (le seul de
    l'application avec l'authentification et le webhook).

    Trois protections, aucune ne reposant sur un service tiers : honeypot
    (côté sérialiseur), limitation de débit par IP, et validation stricte des
    champs. Pas de CAPTCHA : il chargerait un script tiers sur une page qui
    promet de ne pas en avoir, et pénaliserait surtout les visiteurs légitimes.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes = [DemoRequestRateThrottle]

    def post(self, request):
        serializer = DemoRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        demo_request = services.create_demo_request(
            data=serializer.validated_data,
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        services.send_demo_request_emails(demo_request)
        logger.info("Demande de démonstration enregistrée (%s)", demo_request.id)

        return Response(
            {
                "detail": (
                    "Votre demande est bien enregistrée. Nous vous recontactons sous un jour ouvré."
                )
            },
            status=status.HTTP_201_CREATED,
        )


class DemoRequestAdminListView(generics.ListAPIView):
    """Back-office plateforme. ``IsAdminUser`` (is_staff) et non
    ``IsTenantAdmin`` : une demande de démonstration n'appartient à aucun
    tenant (voir models.py)."""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = DemoRequestAdminSerializer

    def get_queryset(self):
        return services.list_demo_requests(status=self.request.query_params.get("status"))


class DemoRequestAdminDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, demo_request_id):
        demo_request = DemoRequest.objects.filter(id=demo_request_id).first()
        if demo_request is None:
            return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)
        serializer = DemoRequestStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        demo_request.status = serializer.validated_data["status"]
        demo_request.save(update_fields=["status"])
        return Response(DemoRequestAdminSerializer(demo_request).data)
