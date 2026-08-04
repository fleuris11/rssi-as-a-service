import re
from urllib.parse import urlparse

from rest_framework import serializers

from .models import Alert, Asset, CheckResult

DOMAIN_RE = re.compile(
    r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ["id", "type", "value", "is_active", "ownership_confirmed", "created_at"]
        read_only_fields = fields


class AssetCreateSerializer(serializers.Serializer):
    """Validates asset creation input — value format depends on type, and
    ownership_confirmed must be explicitly true (US-5.1: "preuve de
    légitimité"); the actual enforcement lives in
    monitoring.services.create_asset, this only shapes the input."""

    type = serializers.ChoiceField(choices=Asset.Type.choices)
    value = serializers.CharField(max_length=255)
    ownership_confirmed = serializers.BooleanField()

    def validate(self, attrs):
        value = attrs["value"].strip()
        if attrs["type"] == Asset.Type.WEBSITE:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise serializers.ValidationError(
                    {"value": "URL invalide : un site web doit commencer par http:// ou https://."}
                )
        else:
            if not DOMAIN_RE.match(value):
                raise serializers.ValidationError({"value": "Domaine invalide."})
        attrs["value"] = value
        return attrs


class CheckResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckResult
        fields = ["id", "check_type", "status", "details", "latency_ms", "checked_at"]
        read_only_fields = fields


class AlertSerializer(serializers.ModelSerializer):
    asset_id = serializers.IntegerField(source="asset.id", read_only=True)
    asset_value = serializers.CharField(source="asset.value", read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id",
            "asset_id",
            "asset_value",
            "alert_type",
            "severity",
            "is_open",
            "details",
            "opened_at",
            "resolved_at",
        ]
        read_only_fields = fields


class AssetDashboardSerializer(serializers.Serializer):
    asset = AssetSerializer()
    uptime_24h = serializers.FloatField(allow_null=True)
    open_alerts = AlertSerializer(many=True)
    latest_checks = serializers.SerializerMethodField()

    def get_latest_checks(self, obj):
        return {
            check_type: CheckResultSerializer(result).data if result else None
            for check_type, result in obj["latest_checks"].items()
        }
