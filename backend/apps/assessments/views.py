from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing import api_guards, features
from apps.tenants.permissions import IsTenantAdmin, IsTenantMember, IsTenantMemberReadOnlyForReader

from . import services
from .models import Measure
from .serializers import (
    AnswerSerializer,
    AssessmentHistorySerializer,
    AssessmentSerializer,
    ConsolidatedScoresSerializer,
    CreateSubsetSerializer,
    MeasureOverrideSerializer,
    ReferentialSerializer,
    ReferentialSummarySerializer,
    ScoresSerializer,
    StartAssessmentSerializer,
    SubmitAnswerSerializer,
    SubsetSerializer,
    WriteMeasureOverrideSerializer,
)


def _get_assessment_or_404(request, assessment_id):
    assessment = services.get_assessment(tenant=request.tenant, assessment_id=assessment_id)
    if assessment is None:
        raise NotFound("Évaluation introuvable.")
    return assessment


def _resolve_referential(request, slug, *, for_reading: bool):
    """Le référentiel désigné par ``slug``, ou celui par défaut.

    ``for_reading`` distingue les deux gardes du modèle (ADR-029) : lire
    demande que le client ait déjà produit dessus OU qu'il lui soit attribué ;
    produire demande une attribution active. Un référentiel retiré reste donc
    consultable, jamais remplissable.
    """
    if not slug:
        return services.get_default_referential(request.tenant)
    referential = services.get_referential(slug=slug)
    if referential is None:
        raise NotFound("Référentiel introuvable.")
    autorise = (
        services.is_readable(request.tenant, referential)
        if for_reading
        else services.is_granted(request.tenant, referential)
    )
    if not autorise:
        raise PermissionDenied(
            f"Le référentiel « {referential.name} » ne vous est pas attribué. "
            "Vous pouvez en faire la demande depuis votre espace."
        )
    return referential


class ReferentialListView(APIView):
    """Le catalogue vu par ce client : ce qu'il a, ce qu'il a eu, et ce qu'il
    pourrait demander.

    On expose aussi les référentiels NON attribués — comme les fonctionnalités
    hors offre, qui s'affichent désactivées plutôt que masquées : un client
    doit pouvoir savoir que le produit sait faire ISO 27001 avant de le
    demander.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        tenant = request.tenant
        attribues = {r.id for r in services.granted_referentials(tenant)}
        lisibles = {r.id for r in services.readable_referentials(tenant)}
        catalogue = list(services.assignable_referentials(tenant))
        # Un référentiel retiré depuis, mais déjà évalué, n'est plus dans le
        # catalogue attribuable : on le rajoute, sinon l'historique du client
        # pointerait vers un référentiel que l'API prétend inexistant.
        deja_vus = {r.id for r in catalogue}
        catalogue += [r for r in services.readable_referentials(tenant) if r.id not in deja_vus]

        charge = []
        for referential in sorted(catalogue, key=lambda r: r.name):
            referential.granted = referential.id in attribues
            referential.readable = referential.id in lisibles
            referential.measure_count = Measure.objects.filter(referential=referential).count()

            # B3.8 : l'ecran Diagnostic est un ACCUEIL. Le nom seul ne dit pas
            # ou on en est — il faut l'avancement, le score s'il existe, et la
            # date. Sans eux, un client avec plusieurs referentiels doit
            # ouvrir chacun pour savoir lequel reprendre.
            en_cours = services.get_current_assessment(tenant, referential=referential)
            terminee = services.get_latest_completed_assessment(tenant, referential=referential)
            referential.assessment_status = (
                "in_progress" if en_cours else ("completed" if terminee else "not_started")
            )
            referential.last_assessed_at = (
                terminee.completed_at if terminee else (en_cours.started_at if en_cours else None)
            )
            referential.last_score = (
                services.compute_scores(terminee)["global"] if terminee else None
            )
            # Les compositions utilisables : « les 10 mesures essentielles »
            # existe pour qu'un dirigeant ne referme pas un questionnaire de
            # 42 questions. Encore faut-il qu'il la voie.
            # `available_subsets` et non `subsets` : ce dernier est deja la
            # relation inverse de MeasureSubset, et Django interdit d'y
            # affecter directement.
            referential.available_subsets = [
                {
                    "slug": subset.slug,
                    "name": subset.name,
                    "description": subset.description,
                    "measure_count": len(services.subset_measure_ids(subset)),
                }
                for subset in services.list_subsets(tenant, referential=referential)
            ]
            charge.append(referential)
        return Response(ReferentialSummarySerializer(charge, many=True).data)


class ReferentialDetailView(APIView):
    """La structure d'un référentiel — ce à partir de quoi le questionnaire
    est rendu, surcharges du client appliquées."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request, slug=None):
        try:
            referential = _resolve_referential(request, slug, for_reading=True)
        except services.NoActiveReferentialError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        subset = None
        subset_slug = request.query_params.get("subset")
        if subset_slug:
            subset = services.get_subset(tenant=request.tenant, slug=subset_slug)
            if subset is None or subset.referential_id != referential.id:
                raise NotFound("Questionnaire introuvable pour ce référentiel.")

        structure = services.get_referential_structure(
            referential, tenant=request.tenant, subset=subset
        )
        return Response(
            ReferentialSerializer(
                {
                    "referential": referential,
                    "granted": services.is_granted(request.tenant, referential),
                    "subset": subset,
                    "domains": structure,
                }
            ).data
        )


class SubsetListView(APIView):
    """Les questionnaires composés à partir d'un référentiel : les modèles de
    plateforme et ceux écrits pour ce client."""

    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]

    def get(self, request):
        referential = None
        slug = request.query_params.get("referential")
        if slug:
            referential = services.get_referential(slug=slug)
            if referential is None:
                raise NotFound("Référentiel introuvable.")
        subsets = list(services.list_subsets(request.tenant, referential=referential))
        for subset in subsets:
            subset.measure_count = len(services.subset_measure_ids(subset))
        return Response(SubsetSerializer(subsets, many=True).data)

    def post(self, request):
        serializer = CreateSubsetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        referential = _resolve_referential(request, data["referential"], for_reading=False)
        try:
            subset = services.create_subset(
                referential=referential,
                slug=data["slug"],
                name=data["name"],
                description=data["description"],
                measure_codes=data["measure_codes"],
                # Un client ne compose que pour lui : « partagé » reste une
                # décision d'exploitant, prise depuis la console.
                owner_tenant=request.tenant,
                created_by=request.user,
            )
        except services.SubsetError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        subset.measure_count = len(services.subset_measure_ids(subset))
        return Response(SubsetSerializer(subset).data, status=status.HTTP_201_CREATED)


class MeasureOverrideListView(APIView):
    """Toutes les reformulations posées par ce client, avec l'énoncé d'origine
    à côté — sans lui, on ne saurait plus ce qui a été remplacé."""

    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]

    def get(self, request):
        overrides = services.list_overrides(request.tenant)
        return Response(MeasureOverrideSerializer(overrides, many=True).data)


class MeasureOverrideView(APIView):
    """Reformulation d'une mesure pour ce client. La surcharge vit à côté :
    ``PUT`` la pose, ``DELETE`` la retire et l'énoncé d'origine réapparaît."""

    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]

    def _measure_or_404(self, request, measure_id):
        measure = Measure.objects.filter(id=measure_id).select_related("referential").first()
        if measure is None:
            raise NotFound("Mesure introuvable.")
        if not services.is_readable(request.tenant, measure.referential):
            raise PermissionDenied("Ce référentiel ne vous est pas attribué.")
        return measure

    def put(self, request, measure_id):
        measure = self._measure_or_404(request, measure_id)
        serializer = WriteMeasureOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        override = services.set_measure_override(
            tenant=request.tenant,
            measure=measure,
            plain_language=serializer.validated_data["plain_language"],
            context_note=serializer.validated_data["context_note"],
            created_by=request.user,
        )
        return Response(MeasureOverrideSerializer(override).data)

    def delete(self, request, measure_id):
        measure = self._measure_or_404(request, measure_id)
        services.clear_measure_override(tenant=request.tenant, measure=measure)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StartAssessmentView(APIView):
    """Starts a new assessment, or resumes the tenant's in-progress one for
    that referential."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def post(self, request):
        # Garde d'offre sur la PRODUCTION d'une évaluation. Les chemins de
        # lecture (liste, détail, scores, référentiel) restent ouverts : un
        # client qui perd le diagnostic garde ce qu'il a déjà rempli.
        api_guards.ensure_feature(request.tenant, features.ANSSI_ASSESSMENT)

        serializer = StartAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            referential = _resolve_referential(request, data.get("referential"), for_reading=False)
        except services.NoActiveReferentialError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        subset = None
        if data.get("subset"):
            subset = services.get_subset(tenant=request.tenant, slug=data["subset"])
            if subset is None:
                raise NotFound("Questionnaire introuvable.")

        try:
            assessment = services.start_or_resume_assessment(
                tenant=request.tenant, user=request.user, referential=referential, subset=subset
            )
        except services.ReferentialNotAssignedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except services.AssessmentsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AssessmentSerializer(assessment).data)


class CurrentAssessmentView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        referential = None
        slug = request.query_params.get("referential")
        if slug:
            referential = services.get_referential(slug=slug)
            if referential is None:
                raise NotFound("Référentiel introuvable.")
        assessment = services.get_current_assessment(request.tenant, referential=referential)
        if assessment is None:
            raise NotFound("Aucune évaluation en cours.")
        return Response(AssessmentSerializer(assessment).data)


class AssessmentListView(generics.ListAPIView):
    """History of the tenant's assessments — most recent first (US-2.3)."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    serializer_class = AssessmentHistorySerializer

    def get_queryset(self):
        referential = None
        slug = self.request.query_params.get("referential")
        if slug:
            referential = services.get_referential(slug=slug)
            if referential is None:
                raise NotFound("Référentiel introuvable.")
        return services.list_assessments(self.request.tenant, referential=referential)


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
        # Même raisonnement pour le référentiel : une évaluation ouverte avant
        # un retrait d'attribution ne doit pas rester remplissable. Elle reste
        # LISIBLE — c'est l'écriture qu'on ferme.
        if not services.is_granted(request.tenant, assessment.referential):
            raise PermissionDenied(
                "Ce référentiel ne vous est plus attribué. Cette évaluation reste "
                "consultable, mais ne peut plus être modifiée."
            )
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
        if not services.is_granted(request.tenant, assessment.referential):
            raise PermissionDenied(
                "Ce référentiel ne vous est plus attribué. Cette évaluation reste "
                "consultable, mais ne peut plus être terminée."
            )

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


class ConsolidatedScoresView(APIView):
    """Le score par référentiel, et le consolidé quand il y en a plusieurs
    (ADR-030). Chemin de LECTURE : aucune garde d'attribution — un référentiel
    retiré depuis y figure encore avec le score qu'il avait."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        return Response(
            ConsolidatedScoresSerializer(services.consolidated_scores(request.tenant)).data
        )
