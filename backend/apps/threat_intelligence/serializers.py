from rest_framework import serializers

from .models import BreachFinding, BreachIntelligenceUsage, BreachScanJob, MonitoredAsset


class BreachFindingSerializer(serializers.ModelSerializer):
    asset_id = serializers.IntegerField(source="asset.id", read_only=True)
    asset_value = serializers.CharField(source="asset.value", read_only=True)

    class Meta:
        model = BreachFinding
        fields = [
            "id",
            "asset_id",
            "asset_value",
            "source_endpoint",
            "finding_type",
            "severity",
            "status",
            "identifier_plain",
            "identifier_masked",
            "secret_masked",
            "secret_seen",
            "breach_date",
            "detected_at",
            "treated_at",
        ]
        # raw_data est délibérément exclu (ADR-014 : minimisation — le
        # dirigeant a besoin de savoir *quoi* et *où*, pas du détail brut,
        # même déjà masqué, de la charge fournisseur).
        read_only_fields = fields


class BreachFindingStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[BreachFinding.Status.TREATED, BreachFinding.Status.IGNORED]
    )


class MonitoredAssetSerializer(serializers.ModelSerializer):
    asset_id = serializers.IntegerField(source="asset.id", read_only=True)
    asset_value = serializers.CharField(source="asset.value", read_only=True)

    class Meta:
        model = MonitoredAsset
        fields = ["id", "asset_id", "asset_value", "provider", "registered_at", "is_active"]
        read_only_fields = fields


class MonitoredAssetCreateSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()


class BreachScanJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = BreachScanJob
        fields = [
            "id",
            "status",
            "triggered_by",
            "result_ref",
            "error_message",
            "created_at",
            "finished_at",
        ]
        read_only_fields = fields


class BreachScanTriggerSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField(required=False, allow_null=True)


class BreachIntelligenceUsageSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = BreachIntelligenceUsage
        fields = [
            "id",
            "tenant_name",
            "endpoint",
            "requests_consumed",
            "remaining_after",
            "triggered_by",
            "findings_created",
            "created_at",
        ]
        read_only_fields = fields
