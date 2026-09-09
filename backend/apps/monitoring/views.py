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
    AssetOwnershipProofSerializer,
    AssetSerializer,
    CheckResultSerializer,
    OwnershipProofStartSerializer,
    OwnershipProofVerifySerializer,
)


def _get_asset_or_404(request, asset_id):
    asset = services.get_asset(tenant=request.tenant, asset_id=asset_id)
    if asset is None:
        raise NotFound("Actif introuvable.")
    return asset


def _client_ip(request) -> str:
    # Même modèle de confiance que apps.accounts.views._client_ip : en
    # production, le seul chemin jusqu'ici passe par Caddy, qui pose
    # X-Forwarded-For. Ne jamais faire confiance à cet en-tête sur un
    # processus directement exposé.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


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
                tenant=request.tenant,
                user=request.user,
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                **serializer.validated_data,
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


class AssetOwnershipView(APIView):
    """GET : où en est la possession de cet actif. POST : ouvrir une preuve.

    ADR-026. La lecture est ouverte à tout membre — savoir si un actif est
    régularisé n'est pas une action. L'ouverture d'une preuve, elle, engage
    l'entreprise (elle enverra peut-être un email à une organisation tierce)
    et suit donc la même règle que les autres écritures de ce module.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def get(self, request, asset_id):
        asset = _get_asset_or_404(request, asset_id)
        return Response(
            {
                "asset_id": asset.id,
                "domain": services.asset_domain(asset),
                "state": services.ownership_state(asset),
                "proven": services.is_ownership_proven(asset),
                "proofs": AssetOwnershipProofSerializer(
                    services.list_ownership_proofs(asset), many=True
                ).data,
                # Les adresses génériques admises, construites sur le domaine
                # réel : l'écran n'a pas à connaître la liste, ni à la recopier.
                "email_choices": [
                    f"{partie}@{services.asset_domain(asset)}"
                    for partie in services.OWNERSHIP_EMAIL_LOCAL_PARTS
                ],
            }
        )

    def post(self, request, asset_id):
        asset = _get_asset_or_404(request, asset_id)
        serializer = OwnershipProofStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            proof = services.start_ownership_proof(
                asset=asset,
                method=serializer.validated_data["method"],
                user=request.user,
                email_recipient=serializer.validated_data.get("email_recipient", ""),
            )
        except services.OwnershipError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AssetOwnershipProofSerializer(proof).data, status=status.HTTP_201_CREATED)


class AssetOwnershipVerifyView(APIView):
    """POST : vérifier une preuve ouverte.

    Une preuve non encore publiée n'est pas une erreur : la réponse est 200
    avec ``verified: false`` et le détail de ce qui manque. Répondre 400
    ferait passer pour une faute du client une étape normale de son parcours
    — et l'écran perdrait le message qui lui dit quoi corriger.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def post(self, request, asset_id, proof_id):
        asset = _get_asset_or_404(request, asset_id)
        proof = services.get_ownership_proof(asset=asset, proof_id=proof_id)
        if proof is None:
            raise NotFound("Vérification introuvable.")

        serializer = OwnershipProofVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proof = services.verify_ownership_proof(
            proof, submitted_token=serializer.validated_data.get("code", "")
        )
        return Response(
            {
                "verified": proof.status == proof.Status.VERIFIED,
                "proof": AssetOwnershipProofSerializer(proof).data,
                "state": services.ownership_state(asset),
            }
        )
