from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.assessments.serializers import MeasureSerializer

from .models import ActionItem
from .services import priority_ratio

User = get_user_model()


class ActionItemSerializer(serializers.ModelSerializer):
    measure = MeasureSerializer(read_only=True)
    domain_name = serializers.CharField(source="measure.domain.name", read_only=True)
    # V2-4 : un plan consolidé mélange les référentiels. Sans cette colonne,
    # deux lignes voisines demandant à peu près la même chose seraient
    # indistinguables — et l'une des deux passerait pour un doublon.
    referential_name = serializers.CharField(source="measure.referential.name", read_only=True)
    referential_slug = serializers.CharField(source="measure.referential.slug", read_only=True)
    assignee_email = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    # Calculé côté serveur : « en retard » se définit une fois, et l'écran ne
    # refait pas la comparaison de dates dans son coin.
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = ActionItem
        fields = [
            "id",
            "assessment",
            "measure",
            "domain_name",
            "referential_name",
            "referential_slug",
            "status",
            "assignee",
            "assignee_email",
            "note",
            "priority",
            # V2-3 (ADR-028) : sans échéance, aucune action ne peut être « en
            # retard » — l'indicateur du comité resterait à zéro pour tout le
            # monde, et serait donc décoratif.
            "due_date",
            "is_overdue",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "assessment",
            "measure",
            "domain_name",
            "referential_name",
            "referential_slug",
            "assignee_email",
            "priority",
            "is_overdue",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def get_assignee_email(self, item):
        return item.assignee.email if item.assignee_id else None

    def get_priority(self, item):
        return round(priority_ratio(item), 2)

    def get_is_overdue(self, item) -> bool:
        if item.due_date is None or item.status == ActionItem.Status.DONE:
            return False
        return item.due_date < timezone.localdate()


class ActionItemUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ActionItem.Status.choices, required=False)
    # `allow_null` : retirer une échéance est un geste légitime, pas une
    # erreur de saisie.
    due_date = serializers.DateField(required=False, allow_null=True)
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    note = serializers.CharField(required=False, allow_blank=True)
