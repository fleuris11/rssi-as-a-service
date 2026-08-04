from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.assessments import services as assessments_services
from apps.assessments.serializers import ScoresSerializer
from apps.tenants.permissions import IsTenantMember, IsTenantMemberReadOnlyForReader

from . import services
from .serializers import ActionItemSerializer, ActionItemUpdateSerializer


def _get_item_or_404(request, item_id):
    item = services.get_action_item(tenant=request.tenant, item_id=item_id)
    if item is None:
        raise NotFound("Action introuvable.")
    return item


class ActionItemListView(generics.ListAPIView):
    """Kanban list — one flat list, each item carries its status; the
    frontend groups them into à faire / en cours / fait columns.

    Optional filters: ``?assessment=<id>`` and ``?status=todo|in_progress|done``.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    serializer_class = ActionItemSerializer

    def get_queryset(self):
        assessment = None
        assessment_id = self.request.query_params.get("assessment")
        if assessment_id is not None:
            assessment = assessments_services.get_assessment(
                tenant=self.request.tenant, assessment_id=assessment_id
            )
            if assessment is None:
                raise NotFound("Évaluation introuvable.")
        return services.list_action_items(
            self.request.tenant,
            assessment=assessment,
            status=self.request.query_params.get("status"),
        )


class ActionItemDetailView(APIView):
    """Retrieve or update one action item — status change and assignation
    both go through PATCH (cadrage M3: "changement de statut, assignation")."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def get(self, request, item_id):
        return Response(ActionItemSerializer(_get_item_or_404(request, item_id)).data)

    def patch(self, request, item_id):
        item = _get_item_or_404(request, item_id)
        serializer = ActionItemUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "status" in data:
            services.update_status(item, data["status"])
        if "assignee" in data:
            try:
                services.assign_action_item(item, data["assignee"])
            except services.InvalidAssigneeError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if "note" in data:
            services.set_note(item, data["note"])

        item.refresh_from_db()
        return Response(ActionItemSerializer(item).data)


class ProjectedScoreView(APIView):
    """Global + per-domain score if every "done" action item's measure were
    fully compliant — defaults to the tenant's latest completed assessment."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        assessment_id = request.query_params.get("assessment")
        if assessment_id is not None:
            assessment = assessments_services.get_assessment(
                tenant=request.tenant, assessment_id=assessment_id
            )
        else:
            assessment = assessments_services.get_latest_completed_assessment(request.tenant)
        if assessment is None:
            raise NotFound("Aucune évaluation terminée pour cette entreprise.")
        return Response(ScoresSerializer(services.compute_projected_score(assessment)).data)
