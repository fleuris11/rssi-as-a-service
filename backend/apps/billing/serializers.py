from rest_framework import serializers

from . import features as feature_registry
from .models import Plan


class PublicPlanSerializer(serializers.ModelSerializer):
    """Vue publique d'une offre (site vitrine). Expose ce qui aide à choisir,
    jamais l'état interne (brouillon/retiré ne sort pas d'ici : le queryset
    est déjà filtré)."""

    features = serializers.SerializerMethodField()
    yearly_months = serializers.SerializerMethodField()

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
            "is_highlighted",
            "display_order",
            "monitored_assets",
            "monthly_scans",
            "max_users",
            "features",
            "yearly_months",
        ]

    def get_features(self, plan):
        return [{"key": key, "label": feature_registry.label(key)} for key in plan.enabled_features]

    def get_yearly_months(self, plan):
        months = plan.yearly_equivalent_months
        return float(months) if months is not None else None
