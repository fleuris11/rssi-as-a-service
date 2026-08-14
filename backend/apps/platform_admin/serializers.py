from rest_framework import serializers

from apps.billing import features as feature_registry
from apps.billing.models import Plan
from apps.marketing.models import DemoRequest
from apps.tenants.models import Tenant

from .models import AdminAuditLog


class PlanAdminSerializer(serializers.ModelSerializer):
    enabled_features = serializers.ListField(read_only=True)
    feature_labels = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Plan
        fields = [
            "code",
            "name",
            "tagline",
            "description",
            "price_monthly",
            "price_yearly",
            "currency",
            "is_quote_only",
            "status",
            "status_label",
            "display_order",
            "is_highlighted",
            "monitored_assets",
            "monthly_scans",
            "max_users",
            "features",
            "enabled_features",
            "feature_labels",
        ]

    def get_feature_labels(self, plan):
        return [feature_registry.label(key) for key in plan.enabled_features]


class PlanWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "code",
            "name",
            "tagline",
            "description",
            "price_monthly",
            "price_yearly",
            "currency",
            "is_quote_only",
            "status",
            "display_order",
            "is_highlighted",
            "monitored_assets",
            "monthly_scans",
            "max_users",
            "features",
        ]

    def validate_features(self, value):
        """Rejette une clé inconnue à l'écriture, alors que la lecture
        l'ignore silencieusement (features.sanitize). Les deux comportements
        sont voulus : à la saisie on veut prévenir l'exploitant de sa faute de
        frappe ; à la lecture on ne veut jamais faire tomber l'application
        d'un client à cause d'une donnée déjà en base."""
        unknown = [key for key in value if not feature_registry.is_known(key)]
        if unknown:
            raise serializers.ValidationError(
                f"Fonctionnalité(s) inconnue(s) : {', '.join(unknown)}. "
                f"Valeurs acceptées : {', '.join(feature_registry.all_keys())}."
            )
        return value


class SubscriptionActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["activate", "suspend", "cancel", "change_plan"])
    plan_code = serializers.CharField(required=False, allow_blank=True)
    period = serializers.ChoiceField(
        choices=["monthly", "yearly"], required=False, allow_blank=True
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    def validate(self, attrs):
        if attrs["action"] == "change_plan" and not attrs.get("plan_code"):
            raise serializers.ValidationError(
                {"plan_code": "Indiquez l'offre vers laquelle basculer."}
            )
        return attrs


class TenantSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    user_count = serializers.IntegerField()
    plan_name = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()
    subscription_status_label = serializers.SerializerMethodField()
    monitored_assets_quota = serializers.SerializerMethodField()

    def _subscription(self, tenant):
        return getattr(tenant, "subscription", None)

    def get_plan_name(self, tenant):
        subscription = self._subscription(tenant)
        return subscription.plan.name if subscription else ""

    def get_subscription_status(self, tenant):
        subscription = self._subscription(tenant)
        return subscription.status if subscription else ""

    def get_subscription_status_label(self, tenant):
        subscription = self._subscription(tenant)
        return subscription.get_status_display() if subscription else "Aucun abonnement"

    def get_monitored_assets_quota(self, tenant):
        subscription = self._subscription(tenant)
        return subscription.monitored_assets_quota if subscription else 0


class DemoRequestAdminSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    company_size_label = serializers.CharField(
        source="get_company_size_display", read_only=True, default=""
    )
    already_client = serializers.SerializerMethodField()

    class Meta:
        model = DemoRequest
        # L'IP et l'agent utilisateur sont collectés pour la seule finalité
        # anti-abus : ils n'ont rien à faire dans une liste consultée pour
        # rappeler un prospect, et ne sont donc pas exposés ici.
        fields = [
            "id",
            "full_name",
            "company",
            "role",
            "email",
            "company_size",
            "company_size_label",
            "preferred_slot",
            "message",
            "status",
            "status_label",
            "created_at",
            "already_client",
        ]
        read_only_fields = fields

    def get_already_client(self, demo_request):
        """Évite de proposer une conversion qui échouerait en 409."""
        return Tenant.objects.filter(name=demo_request.company).exists()


class AdminAuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True, default="")
    tenant_name = serializers.CharField(source="tenant.name", read_only=True, default="")
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AdminAuditLog
        fields = [
            "id",
            "actor_email",
            "action",
            "action_label",
            "tenant_name",
            "target",
            "detail",
            "created_at",
        ]
        read_only_fields = fields
