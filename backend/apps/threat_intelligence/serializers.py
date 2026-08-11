from rest_framework import serializers

from . import plain_language
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
    # Vulgarisation déterministe (Phase 8B) : « ce que ça veut dire » et
    # « ce qu'il faut faire », calculés côté serveur à partir du module
    # plain_language — affichés immédiatement, sans appel IA.
    meaning = serializers.SerializerMethodField()
    recommended_action = serializers.SerializerMethodField()

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
            "meaning",
            "recommended_action",
        ]
        # raw_data et secret_encrypted sont délibérément exclus (ADR-014 :
        # minimisation — le dirigeant a besoin de savoir *quoi* et *où*, pas
        # du détail brut, même déjà masqué, de la charge fournisseur ; le
        # secret chiffré ne sort jamais que via l'endpoint de révélation
        # dédié, ré-authentifié).
        read_only_fields = fields

    def get_meaning(self, finding) -> str:
        return plain_language.explain(finding)["meaning"]

    def get_recommended_action(self, finding) -> str:
        return plain_language.explain(finding)["action"]


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


class PreIncidentItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    asset_value = serializers.CharField()
    detail = serializers.CharField()
    detected_at = serializers.DateTimeField()
    breach_date = serializers.DateField(allow_null=True)


class PreIncidentSignalSerializer(serializers.Serializer):
    """Radar pré-incident (Phase 8A) : un signal d'exposition publique, pas
    un constat de fuite — d'où la phrase de vulgarisation et le niveau
    d'urgence, tous deux calculés côté serveur pour que le frontend n'ait
    aucune règle métier à dupliquer."""

    signal_type = serializers.CharField()
    label = serializers.CharField()
    plain_language = serializers.CharField()
    urgency = serializers.CharField()
    count = serializers.IntegerField()
    items = PreIncidentItemSerializer(many=True)


class PreIncidentSummarySerializer(serializers.Serializer):
    signals = PreIncidentSignalSerializer(many=True)
    total = serializers.IntegerField()


class ExposureFindingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    source_endpoint = serializers.CharField()
    source_label = serializers.CharField()
    finding_type = serializers.CharField()
    severity = serializers.CharField()
    severity_label = serializers.CharField()
    identifier = serializers.CharField(allow_blank=True)
    secret_masked = serializers.CharField(allow_blank=True)
    has_secret = serializers.BooleanField()
    breach_date = serializers.DateField(allow_null=True)
    detected_at = serializers.DateTimeField()
    meaning = serializers.CharField()
    recommended_action = serializers.CharField()


class ExposureScoreComponentSerializer(serializers.Serializer):
    """Le « pourquoi ce score » (ADR-016) : chaque ligne dit quelle fuite
    contribue combien, et pourquoi ce montant."""

    finding_id = serializers.IntegerField()
    label = serializers.CharField()
    severity = serializers.CharField()
    points = serializers.IntegerField()
    detail = serializers.CharField()


class ExposureAssetGroupSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    asset_value = serializers.CharField()
    asset_type_label = serializers.CharField()
    score = serializers.IntegerField()
    level = serializers.CharField()
    level_label = serializers.CharField()
    findings_count = serializers.IntegerField()
    components = ExposureScoreComponentSerializer(many=True)
    findings = ExposureFindingSerializer(many=True)


class ExposureSynthesisSerializer(serializers.Serializer):
    content = serializers.CharField()
    generated_at = serializers.DateTimeField()
    is_stale = serializers.BooleanField()


class ExposureFeedSerializer(serializers.Serializer):
    assets = ExposureAssetGroupSerializer(many=True)
    total_findings = serializers.IntegerField()
    highest_score = serializers.IntegerField()
    # Absent (null) quand aucune synthèse n'a été générée ou que l'IA est
    # indisponible : la page doit être complète sans elle.
    synthesis = ExposureSynthesisSerializer(allow_null=True)


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
