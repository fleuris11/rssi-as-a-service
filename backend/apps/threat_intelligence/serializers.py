from rest_framework import serializers

from . import finding_details, plain_language, services
from .models import (
    BreachFinding,
    BreachIntelligenceUsage,
    BreachScanJob,
    IdentifierAccessAudit,
    MonitoredAsset,
    SecretRevealAudit,
    WatchedAccount,
    WatchedAccountFinding,
)


class BreachFindingSerializer(serializers.ModelSerializer):
    asset_id = serializers.IntegerField(source="asset.id", read_only=True)
    asset_value = serializers.CharField(source="asset.value", read_only=True)
    # Vulgarisation déterministe (Phase 8B, étendue V2-2) : ce que c'est, ce
    # que ça implique, ce qu'il faut faire — calculés côté serveur à partir du
    # module plain_language, affichés immédiatement, sans appel IA.
    meaning = serializers.SerializerMethodField()
    impact = serializers.SerializerMethodField()
    recommended_action = serializers.SerializerMethodField()
    # V2-2 (ADR-027) : ce que la source renvoie et que le produit taisait —
    # logiciel malveillant, service concerné, poste infecté… Chaque champ
    # porte son libellé français et ce qu'il implique.
    details = serializers.SerializerMethodField()
    # V2-2 (ADR-027) : l'adresse, selon le rôle du lecteur.
    #
    # `identifier_plain` et `identifier_masked` ne sont PLUS exposés
    # séparément. Ils l'étaient tant que le clair n'existait que pour les
    # membres du tenant ; maintenant que toute fuite en porte un, les laisser
    # dans la charge contournerait la garde de rôle — le lecteur aurait reçu
    # l'adresse dans un champ voisin de celui qu'on lui masque.
    identifier = serializers.SerializerMethodField()

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
            "identifier",
            "secret_masked",
            "has_secret",
            "breach_date",
            "detected_at",
            # V2-1 : une fuite traitée que les analyses suivantes revoient
            # garde sa date de détection. C'est celle-ci qui répond à « le
            # fournisseur la remonte-t-il toujours ? » — question légitime,
            # à laquelle taire la réponse serait cacher plutôt que masquer.
            "last_seen_at",
            "treated_at",
            "meaning",
            "impact",
            "recommended_action",
            "details",
        ]
        # raw_data et secret_encrypted sont délibérément exclus (ADR-014 :
        # minimisation — le dirigeant a besoin de savoir *quoi* et *où*, pas
        # du détail brut, même déjà masqué, de la charge fournisseur ; le
        # secret chiffré ne sort jamais que via l'endpoint de révélation
        # dédié, ré-authentifié).
        read_only_fields = fields

    def get_meaning(self, finding) -> str:
        return plain_language.explain(finding)["meaning"]

    def get_impact(self, finding) -> str:
        return plain_language.explain(finding)["impact"]

    def get_recommended_action(self, finding) -> str:
        return plain_language.explain(finding)["action"]

    def get_details(self, finding) -> list:
        return finding_details.details_for(finding)

    def get_identifier(self, finding) -> str:
        """Sans rôle dans le contexte, on sert la forme MASQUÉE.

        Le défaut sûr est celui qui protège : un sérialiseur instancié sans
        contexte (un test, un futur appelant, une commande) ne doit pas
        publier une adresse par omission. Une garde dont l'oubli ouvre
        l'accès n'est pas une garde.
        """
        return services.identifier_for_viewer(finding, role=self.context.get("viewer_role"))


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


class ReuseSignalSerializer(serializers.Serializer):
    """Corrélation « réutilisation possible » (ADR-017). Le vocabulaire est
    imposé côté serveur (module correlation.py) : le frontend n'invente ni
    libellé ni formulation, pour qu'aucune interface ne puisse laisser croire
    qu'une réutilisation a été *vérifiée*."""

    signal_type = serializers.CharField()
    label = serializers.CharField()
    explanation = serializers.CharField()
    identifier = serializers.CharField(allow_blank=True)
    related_finding_ids = serializers.ListField(child=serializers.IntegerField())
    occurrences = serializers.IntegerField(required=False)
    external_service = serializers.CharField(required=False)


class FindingDetailSerializer(serializers.Serializer):
    """Un champ de la charge fournisseur, rendu lisible (V2-2, ADR-027).

    Trois parties, et les trois comptent : le libellé français dit de QUOI il
    s'agit, la valeur dit CE QUE c'est, et l'implication dit POURQUOI ça
    compte. « Raccoon » seul n'informe personne.
    """

    label = serializers.CharField()
    value = serializers.CharField()
    implication = serializers.CharField()


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
    secret_purged_at = serializers.DateTimeField(allow_null=True)
    breach_date = serializers.DateField(allow_null=True)
    detected_at = serializers.DateTimeField()
    meaning = serializers.CharField()
    impact = serializers.CharField()
    recommended_action = serializers.CharField()
    details = FindingDetailSerializer(many=True)
    reuse_signals = ReuseSignalSerializer(many=True)


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
    reuse_signals = ReuseSignalSerializer(many=True)


class RetentionPolicySerializer(serializers.Serializer):
    """Affichée au client : la promesse de rétention n'est crédible que s'il
    peut la lire dans le produit (ADR-014)."""

    secret_retention_days = serializers.IntegerField()
    reveal_audit_retention_days = serializers.IntegerField()


class SecretPurgeRunSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    started_at = serializers.DateTimeField()
    retention_days = serializers.IntegerField()
    secrets_purged = serializers.IntegerField()
    reveal_audits_deleted = serializers.IntegerField()


class ExposureSynthesisSerializer(serializers.Serializer):
    content = serializers.CharField()
    generated_at = serializers.DateTimeField()
    is_stale = serializers.BooleanField()


class ExposureFeedSerializer(serializers.Serializer):
    assets = ExposureAssetGroupSerializer(many=True)
    total_findings = serializers.IntegerField()
    highest_score = serializers.IntegerField()
    retention_policy = RetentionPolicySerializer()
    # Absent (null) quand aucune synthèse n'a été générée ou que l'IA est
    # indisponible : la page doit être complète sans elle.
    synthesis = ExposureSynthesisSerializer(allow_null=True)


class IdentifierAccessAuditSerializer(serializers.ModelSerializer):
    """Journal des consultations d'adresses (V2-2, ADR-027).

    Ne porte pas les adresses elles-mêmes, seulement leur nombre : un journal
    d'accès qui recopierait la donnée consultée doublerait l'exposition qu'il
    est censé encadrer.
    """

    user_email = serializers.CharField(source="user.email", read_only=True, default="")
    context_label = serializers.CharField(source="get_context_display", read_only=True)

    class Meta:
        model = IdentifierAccessAudit
        fields = [
            "id",
            "user_email",
            "context",
            "context_label",
            "asset_ids",
            "identifier_count",
            "ip_address",
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


# --- Comptes désignés (V2-6, ADR-033) ---------------------------------------


class WatchedAccountSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    legal_basis_label = serializers.CharField(source="get_legal_basis_display", read_only=True)
    declared_by_email = serializers.SerializerMethodField()
    open_findings = serializers.SerializerMethodField()

    class Meta:
        model = WatchedAccount
        fields = [
            "id",
            "value",
            "label",
            "category",
            "category_label",
            # La déclaration est exposée en LECTURE : le client doit pouvoir
            # relire ce qu'il a déclaré, et quand. C'est aussi ce qu'il
            # montrera si la personne concernée le lui demande.
            "legal_basis",
            "legal_basis_label",
            "purpose",
            "declaration_version",
            "declared_by_email",
            "declared_at",
            "is_active",
            "last_scanned_at",
            "removed_at",
            "open_findings",
        ]
        read_only_fields = fields

    def get_declared_by_email(self, account):
        return account.declared_by.email if account.declared_by_id else None

    def get_open_findings(self, account):
        return sum(
            1
            for finding in account.findings.all()
            if finding.status == WatchedAccountFinding.Status.OPEN
        )


class WatchedAccountCreateSerializer(serializers.Serializer):
    """La déclaration fait partie de la CRÉATION, pas d'un écran d'après.

    ``declaration_accepted`` et ``purpose`` sont obligatoires ici, et la
    validation du service les redemande : une garde de sérialiseur protège la
    saisie, pas l'API — un appel direct doit rencontrer la même exigence.
    """

    value = serializers.CharField(max_length=255)
    label = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    category = serializers.ChoiceField(
        choices=WatchedAccount.Category.choices, default=WatchedAccount.Category.OTHER
    )
    legal_basis = serializers.ChoiceField(choices=WatchedAccount.LegalBasis.choices)
    purpose = serializers.CharField(max_length=2000)
    declaration_accepted = serializers.BooleanField()

    def validate_declaration_accepted(self, value):
        if not value:
            raise serializers.ValidationError(
                "La déclaration est obligatoire pour ajouter un compte à surveiller."
            )
        return value


class WatchedAccountFindingSerializer(serializers.ModelSerializer):
    account_value = serializers.CharField(source="account.value", read_only=True)
    account_label = serializers.CharField(source="account.label", read_only=True)
    severity_label = serializers.CharField(source="get_severity_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = WatchedAccountFinding
        fields = [
            "id",
            "account",
            "account_value",
            "account_label",
            "source_endpoint",
            "finding_type",
            "severity",
            "severity_label",
            "status",
            "status_label",
            "identifier_masked",
            "secret_masked",
            # Jamais de valeur de secret : il n'en existe aucune en base pour
            # un compte désigné (ADR-033). Le booléen dit qu'un mot de passe a
            # fuité, ce qui suffit à décider de le changer.
            "has_secret",
            "breach_date",
            "detected_at",
            "last_seen_at",
            "treated_at",
        ]
        read_only_fields = fields


class WatchedAccountScanTriggerSerializer(serializers.Serializer):
    # Vide = tous les comptes actifs. La consigne demande « un ou plusieurs ».
    account_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True, default=list
    )


class WatchedAccountFindingUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=WatchedAccountFinding.Status.choices)
