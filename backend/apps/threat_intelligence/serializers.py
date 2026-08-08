from rest_framework import serializers

from .models import (
    BreachFinding,
    BreachIntelligenceUsage,
    BreachScanJob,
    MonitoredAsset,
    SecretRevealAudit,
)


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
            "has_secret",
            "breach_date",
            "detected_at",
            "treated_at",
        ]
        # raw_data et secret_encrypted sont délibérément exclus (ADR-014 :
        # minimisation — le dirigeant a besoin de savoir *quoi* et *où*, pas
        # du détail brut, même déjà masqué, de la charge fournisseur ; le
        # secret chiffré ne sort jamais que via l'endpoint de révélation
        # dédié, ré-authentifié).
        read_only_fields = fields


class BreachFindingStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[BreachFinding.Status.TREATED, BreachFinding.Status.IGNORED]
    )


class SecretRevealRequestSerializer(serializers.Serializer):
    """Step-up re-authentication payload (ADR-014, mise à jour) : le mot de
    passe du compte OU un code TOTP à 6 chiffres, jamais les deux requis —
    au moins l'un des deux, fourni à CHAQUE révélation (pas de session
    élevée mise en cache)."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")
    totp_code = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("password") and not attrs.get("totp_code"):
            raise serializers.ValidationError(
                "Fournissez votre mot de passe ou un code de vérification à 6 chiffres."
            )
        return attrs


class SecretRevealAuditSerializer(serializers.ModelSerializer):
    """Tenant admin's own view of the reveal log — never the secret."""

    finding_id = serializers.IntegerField(source="finding.id", read_only=True, default=None)
    user_email = serializers.CharField(source="user.email", read_only=True, default="")

    class Meta:
        model = SecretRevealAudit
        fields = [
            "id",
            "finding_id",
            "user_email",
            "success",
            "denial_reason",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields


class SecretRevealAuditAdminSerializer(SecretRevealAuditSerializer):
    """Platform back-office variant — adds which tenant, same aggregate-only
    spirit as ``BreachIntelligenceUsageSerializer`` (no finding detail beyond
    its id, no secret)."""

    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta(SecretRevealAuditSerializer.Meta):
        fields = [*SecretRevealAuditSerializer.Meta.fields, "tenant_name"]
        read_only_fields = fields


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
