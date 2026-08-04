from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.permissions import IsTenantMember, IsTenantMemberReadOnlyForReader

from . import services
from .models import CheckResult
from .serializers import (
    AlertSerializer,
    AssetCreateSerializer,
    AssetDashboardSerializer,
    AssetSerializer,
    CheckResultSerializer,
)


def _get_asset_or_404(request, asset_id):
    asset = services.get_asset(tenant=request.tenant, asset_id=asset_id)
    if asset is None:
        raise NotFound("Actif introuvable.")
    return asset


class AssetListCreateView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]
    serializer_class = AssetSerializer

    def get_queryset(self):
        return services.list_assets(self.request.tenant)

    def post(self, request, *args, **kwargs):
        serializer = AssetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            asset = services.create_asset(
                tenant=request.tenant, user=request.user, **serializer.validated_data
            )
        except services.InvalidAssetError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(AssetSerializer(asset).data, status=status.HTTP_201_CREATED)


class AssetDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def get(self, request, asset_id):
        return Response(AssetSerializer(_get_asset_or_404(request, asset_id)).data)

    def patch(self, request, asset_id):
        asset = _get_asset_or_404(request, asset_id)
        if "is_active" in request.data:
            services.set_asset_active(asset, bool(request.data["is_active"]))
        return Response(AssetSerializer(asset).data)

    def delete(self, request, asset_id):
        asset = _get_asset_or_404(request, asset_id)
        services.delete_asset(asset)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssetCheckHistoryView(generics.ListAPIView):
    """History of an asset's check results — optionally filtered by
    ``?check_type=`` — feeds the dashboard's uptime history."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    serializer_class = CheckResultSerializer

    def get_queryset(self):
        asset = _get_asset_or_404(self.request, self.kwargs["asset_id"])
        queryset = CheckResult.all_objects.filter(tenant=self.request.tenant, asset=asset)
        check_type = self.request.query_params.get("check_type")
        if check_type:
            queryset = queryset.filter(check_type=check_type)
        return queryset.order_by("-checked_at")


class DashboardView(APIView):
    """One row per asset: latest result of each applicable check, 24h
    uptime, and any open alert — everything the dashboard page needs."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        data = services.get_tenant_dashboard(request.tenant)
        return Response(AssetDashboardSerializer(data, many=True).data)


class OpenAlertListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    serializer_class = AlertSerializer

    def get_queryset(self):
        return services.list_open_alerts(self.request.tenant)
