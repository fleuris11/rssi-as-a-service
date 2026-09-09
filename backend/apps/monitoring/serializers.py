import re
from urllib.parse import urlparse

from rest_framework import serializers

from . import services
from .models import Alert, Asset, AssetOwnershipProof, CheckResult

DOMAIN_RE = re.compile(
    r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


class AssetSerializer(serializers.ModelSerializer):
    # ADR-026 : `ownership_confirmed` ne dit que « quelqu'un a coché une
    # case ». `ownership_state` dit ce qui est réellement établi — prouvé,
    # déclaré sur l'honneur, ou à régulariser. L'écran a besoin des deux :
    # l'un est un engagement, l'autre un fait.
    ownership_state = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            "id",
            "type",
            "value",
            "is_active",
            "ownership_confirmed",
            "ownership_state",
            "created_at",
        ]
        read_only_fields = fields

    def get_ownership_state(self, asset) -> str:
        return services.ownership_state(asset)


class AssetOwnershipProofSerializer(serializers.ModelSerializer):
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    # Ce que le client doit publier, calculé côté serveur : l'écran, l'email
    # et le support disent ainsi exactement la même chose.
    instructions = serializers.SerializerMethodField()

    class Meta:
        model = AssetOwnershipProof
        fields = [
            "id",
            "method",
            "method_label",
            "status",
            "status_label",
            "email_recipient",
            "instructions",
            "created_at",
            "verified_at",
            "last_attempt_at",
            "last_error",
        ]
        read_only_fields = fields

    def get_instructions(self, proof) -> dict:
        return services.ownership_instructions(proof)


class OwnershipProofStartSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=AssetOwnershipProof.Method.choices)
    # Partie locale seulement (« admin »), jamais une adresse libre : la
    # méthode ne vaut que si l'adresse n'est pas choisie par le demandeur.
    email_recipient = serializers.CharField(required=False, allow_blank=True, max_length=255)


class OwnershipProofVerifySerializer(serializers.Serializer):
    # Le code reçu par email. Ignoré pour les deux autres méthodes, où la
    # preuve se lit sur le domaine lui-même.
    code = serializers.CharField(required=False, allow_blank=True, max_length=64)


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
