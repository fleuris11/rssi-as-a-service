from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.assessments.serializers import MeasureSerializer

from .models import ActionItem
from .services import priority_ratio

User = get_user_model()


class ActionItemSerializer(serializers.ModelSerializer):
    measure = MeasureSerializer(read_only=True)
    domain_name = serializers.CharField(source="measure.domain.name", read_only=True)
    assignee_email = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()

    class Meta:
        model = ActionItem
        fields = [
            "id",
            "assessment",
            "measure",
            "domain_name",
            "status",
            "assignee",
            "assignee_email",
            "note",
            "priority",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "assessment",
            "measure",
            "domain_name",
            "assignee_email",
            "priority",
            "created_at",
            "updated_at",
        ]

    def get_assignee_email(self, item):
        return item.assignee.email if item.assignee_id else None

    def get_priority(self, item):
        return round(priority_ratio(item), 2)


class ActionItemUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ActionItem.Status.choices, required=False)
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    note = serializers.CharField(required=False, allow_blank=True)
