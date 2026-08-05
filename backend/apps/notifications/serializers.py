from rest_framework import serializers

from .models import NotificationPreferences


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
