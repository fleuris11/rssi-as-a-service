"""Sérialiseurs des opérations d'écriture de la console (phase 11).

Ils valident la **forme** (types, champs obligatoires, longueurs) ; la règle
métier reste dans les ``services.py`` des apps concernées. Cette séparation
n'est pas cosmétique : un quota négocié doit être refusé de la même façon
qu'il vienne de la console, d'un script de reprise ou d'un test — dupliquer la
règle ici garantirait qu'elle diverge.
"""

from rest_framework import serializers

from apps.billing.models import Plan, Subscription
from apps.marketing.models import DemoRequest, ProspectNote
from apps.platform_admin.models import PlatformAdminProfile
from apps.tenants.models import Membership, Tenant


class ClientCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    owner_email = serializers.EmailField()
    owner_first_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    owner_last_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    plan_code = serializers.CharField(required=False, allow_blank=True, default="")
    engagement = serializers.ChoiceField(choices=["trial", "active"], default="trial")
    trial_days = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=365
    )

    sector = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    headcount = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    contact_email = serializers.EmailField(required=False, allow_blank=True, default="")
    contact_phone = serializers.CharField(
        max_length=40, required=False, allow_blank=True, default=""
    )
    address = serializers.CharField(required=False, allow_blank=True, default="")
    website = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    account_manager = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )
    internal_notes = serializers.CharField(required=False, allow_blank=True, default="")

    # Conversion depuis un prospect : le lien est conservé pour retrouver
    # d'où vient un compte.
    prospect_id = serializers.IntegerField(required=False, allow_null=True)


class TenantUpdateSerializer(serializers.ModelSerializer):
    # Surcharge du délai entre deux analyses manuelles, POUR CE CLIENT.
    #
    # `allow_null` est le cœur du champ, et il porte deux valeurs distinctes
    # qu'il ne faut surtout pas confondre :
    #   - `null` → aucune surcharge, on applique le réglage de plateforme ;
    #   - `0`    → aucun délai, décidé pour ce client.
    # Un champ qui traiterait 0 comme « vide » appliquerait 24 h à un client à
    # qui l'exploitant vient d'accorder l'inverse (voir
    # threat_intelligence.services.scan_cooldown_hours).
    scan_cooldown_minutes = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=525600
    )

    class Meta:
        model = Tenant
        fields = [
            "name",
            "sector",
            "headcount",
            "contact_email",
            "contact_phone",
            "address",
            "website",
            "account_manager",
            "internal_notes",
            "scan_cooldown_minutes",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}


class TenantSerializer(serializers.ModelSerializer):
    is_archived = serializers.BooleanField(read_only=True)
    # Le délai RÉELLEMENT appliqué, surcharge et réglage de plateforme
    # combinés : sans lui, la fiche montrerait « (vide) » sans dire ce qui
    # s'applique à la place, et l'exploitant devrait aller lire la console.
    effective_scan_cooldown_minutes = serializers.SerializerMethodField()
    effective_scan_cooldown_label = serializers.SerializerMethodField()
    archived_by_email = serializers.CharField(
        source="archived_by.email", read_only=True, default=""
    )

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "sector",
            "headcount",
            "is_active",
            "ai_enabled",
            "scan_cooldown_minutes",
            "effective_scan_cooldown_minutes",
            "effective_scan_cooldown_label",
            "contact_email",
            "contact_phone",
            "address",
            "website",
            "account_manager",
            "internal_notes",
            "created_at",
            "is_archived",
            "archived_at",
            "archived_by_email",
            "archive_reason",
        ]
        read_only_fields = fields

    def get_effective_scan_cooldown_minutes(self, tenant) -> int:
        from apps.threat_intelligence import services as threat_intelligence_services

        return threat_intelligence_services.scan_cooldown_minutes(tenant)

    def get_effective_scan_cooldown_label(self, tenant) -> str:
        """« 30 minutes », « 2 h », « 1 h 30 » — le délai tel qu'on le lit.
        Formaté ici plutôt qu'à l'écran : la même phrase sert la fiche et le
        message envoyé au client, et deux formatages divergeraient."""
        from apps.threat_intelligence import services as threat_intelligence_services

        return threat_intelligence_services.format_cooldown(
            threat_intelligence_services.scan_cooldown_minutes(tenant)
        )


class MemberSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source="user.email", read_only=True)
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    # Un compte invité qui n'a jamais défini son mot de passe se distingue d'un
    # compte désactivé : le premier attend une action de la personne, le second
    # une action de l'administrateur.
    has_usable_password = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "email",
            "name",
            "role",
            "role_label",
            "is_active",
            "has_usable_password",
            "last_login",
        ]
        read_only_fields = fields

    def get_has_usable_password(self, membership):
        return membership.user.has_usable_password()


class MemberInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")


class MemberUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)


class SubscriptionUpdateSerializer(serializers.Serializer):
    """Opérations d'abonnement au-delà des transitions d'état.

    ``None`` sur une surcharge signifie « revenir au quota de l'offre » — c'est
    la seule façon d'annuler une négociation, et il faut donc distinguer
    « absent » (ne pas toucher) de « null » (réinitialiser).
    """

    trial_ends_at = serializers.DateTimeField(required=False, allow_null=True)
    period = serializers.ChoiceField(choices=Subscription.Period.choices, required=False)
    internal_notes = serializers.CharField(required=False, allow_blank=True)
    override_monitored_assets = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=10000
    )
    override_monthly_scans = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=1000000
    )
    override_max_users = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=10000
    )
    override_features = serializers.ListField(
        child=serializers.CharField(), required=False, allow_null=True
    )

    def validate_override_features(self, value):
        if value is None:
            return None
        from apps.billing import features as feature_registry

        unknown = [key for key in value if not feature_registry.is_known(key)]
        if unknown:
            raise serializers.ValidationError(
                f"Fonctionnalité(s) inconnue(s) : {', '.join(unknown)}."
            )
        return value


class PlanDuplicateSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=40)
    name = serializers.CharField(max_length=80)


class ProspectSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    company_size_label = serializers.CharField(
        source="get_company_size_display", read_only=True, default=""
    )
    owner_email = serializers.CharField(source="owner.email", read_only=True, default="")
    converted_tenant_name = serializers.CharField(
        source="converted_tenant.name", read_only=True, default=""
    )
    already_client = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()

    class Meta:
        model = DemoRequest
        # Ni IP ni agent utilisateur : collectés pour la seule finalité
        # anti-abus, ils n'ont rien à faire dans une fiche de suivi commercial.
        fields = [
            "id",
            "full_name",
            "company",
            "role",
            "email",
            "phone",
            "company_size",
            "company_size_label",
            "preferred_slot",
            "message",
            "status",
            "status_label",
            "source",
            "source_label",
            "lost_reason",
            "next_follow_up_on",
            "owner_email",
            "converted_tenant",
            "converted_tenant_name",
            "already_client",
            "created_at",
            "updated_at",
            "notes",
        ]
        read_only_fields = fields

    def get_already_client(self, prospect):
        if prospect.converted_tenant_id:
            return True
        return Tenant.objects.filter(
            name__iexact=prospect.company, archived_at__isnull=True
        ).exists()

    def get_notes(self, prospect):
        return ProspectNoteSerializer(prospect.notes.all()[:20], many=True).data


class ProspectNoteSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source="author.email", read_only=True, default="")

    class Meta:
        model = ProspectNote
        fields = ["id", "body", "author_email", "created_at"]
        read_only_fields = fields


class ProspectWriteSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=120, required=False)
    company = serializers.CharField(max_length=160, required=False)
    role = serializers.CharField(max_length=120, required=False, allow_blank=True)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    company_size = serializers.ChoiceField(
        choices=DemoRequest.CompanySize.choices, required=False, allow_blank=True
    )
    preferred_slot = serializers.ChoiceField(
        choices=DemoRequest.Slot.choices, required=False, allow_blank=True
    )
    message = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=DemoRequest.Status.choices, required=False)
    lost_reason = serializers.CharField(max_length=200, required=False, allow_blank=True)
    next_follow_up_on = serializers.DateField(required=False, allow_null=True)


class AdminInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    level = serializers.ChoiceField(choices=PlatformAdminProfile.Level.choices)


class AdminLevelSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=PlatformAdminProfile.Level.choices)


class SettingUpdateSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=60)
    # Volontairement non typé : le registre connaît le type attendu et porte
    # la validation. Le déclarer ici obligerait à le maintenir à deux endroits.
    value = serializers.JSONField()


class MonitoredAssetCreateSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()


class TenantActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["scan", "refresh_synthesis", "purge_secrets"])


class PlanImpactSerializer(serializers.Serializer):
    """Aperçu avant confirmation : accepte les mêmes champs qu'une mise à jour
    d'offre, sans rien écrire."""

    monitored_assets = serializers.IntegerField(required=False, min_value=0)
    monthly_scans = serializers.IntegerField(required=False, min_value=0)
    max_users = serializers.IntegerField(required=False, min_value=0)
    status = serializers.ChoiceField(choices=Plan.Status.choices, required=False)
