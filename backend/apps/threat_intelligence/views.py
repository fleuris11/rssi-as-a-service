import logging

from django.conf import settings
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.monitoring import services as monitoring_services
from apps.tenants.permissions import IsTenantMember, IsTenantMemberReadOnlyForReader

from . import quota as quota_module
from . import services
from .models import BreachIntelligenceUsage
from .serializers import (
    BreachFindingSerializer,
    BreachFindingStatusUpdateSerializer,
    BreachIntelligenceUsageSerializer,
    BreachScanJobSerializer,
    BreachScanTriggerSerializer,
    MonitoredAssetCreateSerializer,
    MonitoredAssetSerializer,
)
from .tasks import run_breach_scan_task
from .webhook_auth import is_valid_basic_auth

logger = logging.getLogger(__name__)


class BreachFindingListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    serializer_class = BreachFindingSerializer

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        return services.list_findings(self.request.tenant, status=status_filter)


class BreachFindingDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def _get_or_404(self, request, finding_id):
        finding = services.get_finding(tenant=request.tenant, finding_id=finding_id)
        if finding is None:
            raise NotFound("Fuite introuvable.")
        return finding

    def get(self, request, finding_id):
        return Response(BreachFindingSerializer(self._get_or_404(request, finding_id)).data)

    def patch(self, request, finding_id):
        finding = self._get_or_404(request, finding_id)
        serializer = BreachFindingStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        finding = services.set_finding_status(
            finding, status=serializer.validated_data["status"], user=request.user
        )
        return Response(BreachFindingSerializer(finding).data)


class MonitoredAssetListCreateView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]
    serializer_class = MonitoredAssetSerializer

    def get_queryset(self):
        return services.list_monitored_assets(self.request.tenant)

    def post(self, request, *args, **kwargs):
        serializer = MonitoredAssetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = monitoring_services.get_asset(
            tenant=request.tenant, asset_id=serializer.validated_data["asset_id"]
        )
        if asset is None:
            raise NotFound("Actif introuvable.")
        try:
            monitored = services.register_monitored_asset(tenant=request.tenant, asset=asset)
        except services.ThreatIntelligenceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MonitoredAssetSerializer(monitored).data, status=status.HTTP_201_CREATED)


class MonitoredAssetDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def delete(self, request, asset_id):
        monitored = services.get_monitored_asset(tenant=request.tenant, asset_id=asset_id)
        if monitored is None:
            raise NotFound("Cet actif n'est pas surveillé en temps réel.")
        services.unregister_monitored_asset(monitored)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BreachScanTriggerView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def post(self, request):
        serializer = BreachScanTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = None
        asset_id = serializer.validated_data.get("asset_id")
        if asset_id is not None:
            asset = monitoring_services.get_asset(tenant=request.tenant, asset_id=asset_id)
            if asset is None:
                raise NotFound("Actif introuvable.")

        try:
            job = services.create_scan_job(
                tenant=request.tenant, asset=asset, triggered_by=services.TriggeredBy.MANUAL
            )
        except services.CooldownActiveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except quota_module.QuotaExceededError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        run_breach_scan_task.delay(
            tenant_id=str(request.tenant.id),
            asset_id=asset.id if asset else None,
            triggered_by=services.TriggeredBy.MANUAL,
            job_id=job.id,
        )
        return Response(BreachScanJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class BreachScanJobDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request, job_id):
        job = services.get_scan_job(tenant=request.tenant, job_id=job_id)
        if job is None:
            raise NotFound("Analyse introuvable.")
        return Response(BreachScanJobSerializer(job).data)


class ThreatIntelligenceStatusView(APIView):
    """État visible côté tenant : quota restant (indicatif — le budget est
    partagé par toute la plateforme, pas une allocation par tenant),
    cooldown du scan manuel, occupation du pool de monitoring temps réel —
    ce que le bouton "Lancer un scan" du frontend affiche avant de laisser
    cliquer (prompt Phase 7 point 9)."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        manager = quota_module.QuotaManager()
        cooldown_key = services.SCAN_COOLDOWN_CACHE_KEY.format(tenant_id=request.tenant.id)
        pool = services.pool_summary()
        return Response(
            {
                "quota_remaining": manager.get_remaining(),
                "cooldown_active": bool(cache.get(cooldown_key)),
                "cooldown_hours": settings.BREACHSENSE_SCAN_COOLDOWN_HOURS,
                "pool_used": pool["used"],
                "pool_capacity": pool["capacity"],
                "critical_open_findings": services.count_critical_open_findings(request.tenant),
            }
        )


# --- Back-office plateforme (§9 du prompt Phase 7) --------------------------


class ThreatIntelligenceAdminStatusView(APIView):
    """Vue plateforme (pas tenant-scopée) : état du quota mensuel partagé,
    occupation des 15 slots monitorés, journal d'usage récent. Le back-
    office platform_admin est un scaffold vide à ce stade (réservé à une
    phase ultérieure — voir apps.platform_admin.apps) : cette vue est
    exposée ici, gardée par IsAdminUser (is_staff), plutôt que d'anticiper
    la construction du back-office complet, hors périmètre de cette phase."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        quota_summary = quota_module.get_quota_summary()
        pool = services.pool_summary()
        recent_usage = BreachIntelligenceUsage.all_objects.select_related("tenant").order_by(
            "-created_at"
        )[:50]
        return Response(
            {
                "quota": quota_summary,
                "pool": pool,
                "recent_usage": BreachIntelligenceUsageSerializer(recent_usage, many=True).data,
            }
        )


# --- Webhook entrant (§7 du prompt Phase 7) ---------------------------------


@method_decorator(csrf_exempt, name="dispatch")
class BreachsenseWebhookView(APIView):
    """POST /api/v1/webhooks/breachsense — pas de JWT, pas d'en-tête
    X-Tenant-Id : authentification HTTP Basic uniquement (identifiants
    dans BREACHSENSE_WEBHOOK_USERNAME/PASSWORD, comparés en temps
    constant — voir webhook_auth.py), le tenant est résolu en interne via
    MonitoredAsset.provider_ref (ADR-013). AllowAny côté DRF puisque
    l'authentification n'est pas celle de la plateforme (pas de JWT)."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not is_valid_basic_auth(request):
            response = Response(
                {"detail": "Authentification requise."}, status=status.HTTP_401_UNAUTHORIZED
            )
            response["WWW-Authenticate"] = 'Basic realm="breachsense-webhook"'
            return response

        payload = request.data
        if not isinstance(payload, list):
            raise DRFValidationError("Le corps attendu est un tableau JSON d'événements.")

        result = services.ingest_webhook_payload(payload)
        return Response(result, status=status.HTTP_200_OK)
