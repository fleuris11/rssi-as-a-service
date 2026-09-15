from rest_framework import serializers

from .models import Notification, NotificationPreferences


class NotificationSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    # Le nom du client concerné : quelqu'un qui suit plusieurs entreprises
    # doit savoir de laquelle on lui parle.
    tenant_name = serializers.CharField(source="tenant.name", read_only=True, default=None)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "kind",
            "kind_label",
            "title",
            "body",
            "link",
            "tenant_name",
            "created_at",
            "read_at",
            "is_read",
        ]
        read_only_fields = fields

    def get_is_read(self, obj) -> bool:
        return obj.read_at is not None


class NotificationPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreferences
        fields = [
            "weather_enabled",
            "weather_time",
            "realtime_alerts_enabled",
            "weather_enrichment_enabled",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]
