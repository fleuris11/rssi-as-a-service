from rest_framework import serializers

from .models import Answer, Assessment, Domain, Measure, Referential


class MeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Measure
        fields = [
            "id",
            "number",
            "order",
            "official_title",
            "plain_language",
            "level",
            "effort",
            "impact",
            "effort_impact_disclaimer",
        ]
        read_only_fields = fields


class DomainSerializer(serializers.ModelSerializer):
    measures = MeasureSerializer(many=True, read_only=True)

    class Meta:
        model = Domain
        fields = ["id", "code", "name", "description", "order", "measures"]
        read_only_fields = fields


class ReferentialSerializer(serializers.ModelSerializer):
    domains = DomainSerializer(many=True, read_only=True)

    class Meta:
        model = Referential
        fields = ["id", "slug", "name", "version", "description", "domains"]
        read_only_fields = fields


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


class AnswerSerializer(serializers.ModelSerializer):
    measure_number = serializers.IntegerField(source="measure.number", read_only=True)

    class Meta:
        model = Answer
        fields = ["id", "measure", "measure_number", "value", "note", "answered_at"]
        read_only_fields = ["id", "measure_number", "answered_at"]


class SubmitAnswerSerializer(serializers.Serializer):
    value = serializers.ChoiceField(choices=Answer.Value.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class AssessmentSerializer(serializers.ModelSerializer):
    referential_name = serializers.CharField(source="referential.name", read_only=True)
    progress = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            "id",
            "referential",
            "referential_name",
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

    class Meta:
        model = Assessment
        fields = [
            "id",
            "referential_name",
            "status",
            "started_at",
            "completed_at",
            "score_global",
        ]
        read_only_fields = fields
