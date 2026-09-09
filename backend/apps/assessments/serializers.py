from rest_framework import serializers

from .models import Answer, Assessment, Measure, MeasureSubset, Referential


class MeasureSerializer(serializers.ModelSerializer):
    # ``statement`` est l'énoncé À AFFICHER : la reformulation d'origine, ou
    # la surcharge du client quand il y en a une (ADR-029). ``plain_language``
    # reste exposé à côté pour que l'interface d'administration puisse montrer
    # ce qui a été remplacé — sans lui, on ne saurait plus revenir en arrière.
    statement = serializers.CharField(read_only=True)
    context_note = serializers.CharField(read_only=True)
    is_overridden = serializers.BooleanField(read_only=True)

    class Meta:
        model = Measure
        fields = [
            "id",
            "code",
            "number",
            "order",
            "official_title",
            "plain_language",
            "statement",
            "context_note",
            "is_overridden",
            "level",
            "weight",
            "effort",
            "impact",
            "effort_impact_disclaimer",
        ]
        read_only_fields = fields


class DomainStructureSerializer(serializers.Serializer):
    """Un domaine et les mesures qui, DANS CE PÉRIMÈTRE, lui appartiennent.

    Sérialise la sortie de ``services.get_referential_structure`` — des dicts,
    pas des ``Domain`` avec un prefetch : le sous-ensemble et les surcharges
    sont résolus dans le service, une fois.
    """

    id = serializers.IntegerField(source="domain.id")
    code = serializers.CharField(source="domain.code")
    name = serializers.CharField(source="domain.name")
    description = serializers.CharField(source="domain.description")
    order = serializers.IntegerField(source="domain.order")
    measures = MeasureSerializer(many=True)


class ReferentialSummarySerializer(serializers.ModelSerializer):
    """Une ligne de catalogue, sans les mesures : ce qu'on affiche pour
    choisir un référentiel ou en demander un."""

    granted = serializers.BooleanField(read_only=True, default=False)
    readable = serializers.BooleanField(read_only=True, default=False)
    measure_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Referential
        fields = [
            "id",
            "slug",
            "name",
            "version",
            "description",
            "publisher",
            "kind",
            "source_url",
            "licence_notice",
            "granted",
            "readable",
            "measure_count",
        ]
        read_only_fields = fields


class ReferentialSerializer(serializers.Serializer):
    """Le référentiel et sa structure, telle que le client la voit."""

    id = serializers.IntegerField(source="referential.id")
    slug = serializers.CharField(source="referential.slug")
    name = serializers.CharField(source="referential.name")
    version = serializers.CharField(source="referential.version")
    description = serializers.CharField(source="referential.description")
    publisher = serializers.CharField(source="referential.publisher")
    licence_notice = serializers.CharField(source="referential.licence_notice")
    granted = serializers.BooleanField()
    subset = serializers.SerializerMethodField()
    domains = DomainStructureSerializer(many=True)

    def get_subset(self, payload):
        subset = payload.get("subset")
        if subset is None:
            return None
        return {"id": subset.id, "slug": subset.slug, "name": subset.name}


class SubsetSerializer(serializers.ModelSerializer):
    measure_count = serializers.IntegerField(read_only=True, default=0)
    referential_slug = serializers.CharField(source="referential.slug", read_only=True)
    referential_name = serializers.CharField(source="referential.name", read_only=True)
    # Un modèle de plateforme est proposable à tous ; une composition écrite
    # pour un client n'appartient qu'à lui.
    is_platform_template = serializers.SerializerMethodField()

    class Meta:
        model = MeasureSubset
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "referential",
            "referential_slug",
            "referential_name",
            "measure_count",
            "is_platform_template",
        ]
        read_only_fields = fields

    def get_is_platform_template(self, subset) -> bool:
        return subset.owner_tenant_id is None


class DomainProgressSerializer(serializers.Serializer):
    domain_code = serializers.CharField()
    domain_name = serializers.CharField()
    answered = serializers.IntegerField()
    total = serializers.IntegerField()


class ProgressSerializer(serializers.Serializer):
    answered = serializers.IntegerField()
    total = serializers.IntegerField()
    by_domain = DomainProgressSerializer(many=True)


class DomainScoreSerializer(serializers.Serializer):
    domain_code = serializers.CharField()
    domain_name = serializers.CharField()
    score = serializers.FloatField(allow_null=True)


class ScoresSerializer(serializers.Serializer):
    global_score = serializers.FloatField(allow_null=True, source="global")
    by_domain = DomainScoreSerializer(many=True)


class ReferentialScoreSerializer(serializers.Serializer):
    referential_id = serializers.IntegerField()
    referential_slug = serializers.CharField()
    referential_name = serializers.CharField()
    assessment_id = serializers.IntegerField(allow_null=True)
    score = serializers.FloatField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    measure_count = serializers.IntegerField()
    granted = serializers.BooleanField()


class ConsolidatedScoresSerializer(serializers.Serializer):
    """Le consolidé ne part JAMAIS seul : ``by_referential`` et ``method``
    voyagent avec lui (ADR-030)."""

    by_referential = ReferentialScoreSerializer(many=True)
    consolidated = serializers.FloatField(allow_null=True)
    method = serializers.CharField()
    scored_referentials = serializers.IntegerField()
    unscored_referentials = serializers.ListField(child=serializers.CharField())


class AnswerSerializer(serializers.ModelSerializer):
    measure_code = serializers.CharField(source="measure.code", read_only=True)
    measure_number = serializers.IntegerField(source="measure.number", read_only=True)

    class Meta:
        model = Answer
        fields = ["id", "measure", "measure_code", "measure_number", "value", "note", "answered_at"]
        read_only_fields = ["id", "measure_code", "measure_number", "answered_at"]


class SubmitAnswerSerializer(serializers.Serializer):
    value = serializers.ChoiceField(choices=Answer.Value.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class StartAssessmentSerializer(serializers.Serializer):
    """Sur quoi démarrer. Les deux champs sont facultatifs : sans rien, on
    démarre sur le premier référentiel attribué, questionnaire complet."""

    referential = serializers.CharField(required=False, allow_blank=True)
    subset = serializers.CharField(required=False, allow_blank=True)


class AssessmentSerializer(serializers.ModelSerializer):
    referential_name = serializers.CharField(source="referential.name", read_only=True)
    referential_slug = serializers.CharField(source="referential.slug", read_only=True)
    subset_name = serializers.CharField(source="subset.name", read_only=True, default=None)
    progress = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            "id",
            "referential",
            "referential_name",
            "referential_slug",
            "subset",
            "subset_name",
            "status",
            "started_at",
            "completed_at",
            "score_global",
            "progress",
            "answers",
        ]
        read_only_fields = fields

    def get_progress(self, assessment):
        from . import services

        return ProgressSerializer(services.get_progress(assessment)).data

    def get_answers(self, assessment):
        from . import services

        return AnswerSerializer(services.list_answers(assessment), many=True).data


class AssessmentHistorySerializer(serializers.ModelSerializer):
    referential_name = serializers.CharField(source="referential.name", read_only=True)
    referential_slug = serializers.CharField(source="referential.slug", read_only=True)
    subset_name = serializers.CharField(source="subset.name", read_only=True, default=None)

    class Meta:
        model = Assessment
        fields = [
            "id",
            "referential_name",
            "referential_slug",
            "subset_name",
            "status",
            "started_at",
            "completed_at",
            "score_global",
        ]
        read_only_fields = fields


class MeasureOverrideSerializer(serializers.Serializer):
    """Surcharge d'énoncé posée pour un client, à côté de la mesure."""

    measure = serializers.IntegerField(source="measure_id", read_only=True)
    measure_code = serializers.CharField(source="measure.code", read_only=True)
    original_plain_language = serializers.CharField(source="measure.plain_language", read_only=True)
    plain_language = serializers.CharField(read_only=True)
    context_note = serializers.CharField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class WriteMeasureOverrideSerializer(serializers.Serializer):
    plain_language = serializers.CharField(required=False, allow_blank=True, default="")
    context_note = serializers.CharField(required=False, allow_blank=True, default="")


class CreateSubsetSerializer(serializers.Serializer):
    referential = serializers.CharField()
    slug = serializers.SlugField(max_length=100)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    measure_codes = serializers.ListField(child=serializers.CharField(max_length=40), min_length=1)
    # Vrai = modèle de plateforme, réutilisable par tous les clients à qui le
    # référentiel est attribué. Faux = composition propre à ce client.
    shared = serializers.BooleanField(required=False, default=False)
