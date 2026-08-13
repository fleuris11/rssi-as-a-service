from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.permissions import IsTenantMember

from . import entitlements
from . import services as billing_services
from .serializers import PublicPlanSerializer


class PublicPlanListView(APIView):
    """GET /api/v1/billing/plans/ — catalogue publié, **sans
    authentification** : c'est la source de la grille tarifaire du site
    vitrine, qui doit s'afficher pour un visiteur anonyme.

    N'expose que les offres publiées : un brouillon en cours de préparation ne
    doit pas apparaître publiquement avant sa publication.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def get(self, request):
        plans = billing_services.list_published_plans()
        return Response({"plans": PublicPlanSerializer(plans, many=True).data})


class EntitlementsView(APIView):
    """Ce que comprend l'offre du tenant courant, et ce qui n'y est pas.

    Le frontend s'en sert pour afficher les fonctionnalités hors offre en
    **désactivé** plutôt que masquées : un client doit voir que le produit
    sait le faire, et savoir quelle offre le lui donnerait.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        return Response(entitlements.summary(request.tenant))
