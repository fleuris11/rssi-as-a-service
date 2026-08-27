from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing import api_guards, features
from apps.tenants.permissions import IsTenantMember, IsTenantMemberReadOnlyForReader

from . import services
from .models import Measure
from .serializers import (
    AnswerSerializer,
    AssessmentHistorySerializer,
    AssessmentSerializer,
    ReferentialSerializer,
    ScoresSerializer,
    SubmitAnswerSerializer,
)


def _get_assessment_or_404(request, assessment_id):
    assessment = services.get_assessment(tenant=request.tenant, assessment_id=assessment_id)
    if assessment is None:
        raise NotFound("Évaluation introuvable.")
    return assessment


class ReferentialView(APIView):
    """The active referential's domains and measures — what the
    questionnaire is rendered from."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        try:
            referential = services.get_active_referential()
        except services.NoActiveReferentialError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(ReferentialSerializer(referential).data)


class StartAssessmentView(APIView):
    """Starts a new assessment, or resumes the tenant's in-progress one."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def post(self, request):
        # Garde d'offre sur la PRODUCTION d'une évaluation. Les chemins de
        # lecture (liste, détail, scores, référentiel) restent ouverts : un
        # client qui perd le diagnostic garde ce qu'il a déjà rempli.
        api_guards.ensure_feature(request.tenant, features.ANSSI_ASSESSMENT)

        try:
            assessment = services.start_or_resume_assessment(
                tenant=request.tenant, user=request.user
            )
        except services.NoActiveReferentialError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(AssessmentSerializer(assessment).data)


class CurrentAssessmentView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        assessment = services.get_current_assessment(request.tenant)
        if assessment is None:
            raise NotFound("Aucune évaluation en cours.")
        return Response(AssessmentSerializer(assessment).data)


class AssessmentListView(generics.ListAPIView):
    """History of the tenant's assessments — most recent first (US-2.3)."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    serializer_class = AssessmentHistorySerializer

    def get_queryset(self):
        return services.list_assessments(self.request.tenant)


class AssessmentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request, assessment_id):
        assessment = _get_assessment_or_404(request, assessment_id)
        return Response(AssessmentSerializer(assessment).data)


class AnswerView(APIView):
    """Upserts the answer for one measure within one assessment (autosave)."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def put(self, request, assessment_id, measure_id):
        # Gardé aussi, et pas seulement le démarrage : sans cela, une
        # évaluation ouverte avant un changement d'offre resterait remplissable
        # indéfiniment par appel direct à l'API.
        api_guards.ensure_feature(request.tenant, features.ANSSI_ASSESSMENT)

        assessment = _get_assessment_or_404(request, assessment_id)
        measure = Measure.objects.filter(id=measure_id).first()
        if measure is None:
            raise NotFound("Mesure introuvable.")

        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            answer = services.submit_answer(
                assessment=assessment,
                measure=measure,
                value=serializer.validated_data["value"],
                note=serializer.validated_data["note"],
            )
        except services.AssessmentsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(AnswerSerializer(answer).data)


class CompleteAssessmentView(APIView):
    """Completes the assessment (locks it, snapshots the score) and
    triggers the action plan generation from its gaps."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def post(self, request, assessment_id):
        # La clôture génère le plan d'action : c'est une production, pas une
        # lecture.
        api_guards.ensure_feature(request.tenant, features.ANSSI_ASSESSMENT)

        assessment = _get_assessment_or_404(request, assessment_id)

        try:
            services.complete_assessment(assessment)
        except services.AssessmentsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        from apps.actions import services as actions_services

        actions_services.generate_action_plan(assessment)

        return Response(AssessmentSerializer(assessment).data)


class ScoresView(APIView):
    """Global + per-domain scores — feeds the results page and its radar."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request, assessment_id):
        assessment = _get_assessment_or_404(request, assessment_id)
        return Response(ScoresSerializer(services.compute_scores(assessment)).data)
