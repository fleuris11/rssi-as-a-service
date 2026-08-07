from django.contrib import admin

from .models import BreachFinding, BreachIntelligenceUsage, BreachScanJob, MonitoredAsset


@admin.register(BreachFinding)
class BreachFindingAdmin(admin.ModelAdmin):
    # secret_masked (jamais le secret en clair — ADR-014) affiché à dessein :
    # c'est déjà une forme masquée, pas la valeur d'origine.
    list_display = ["asset", "source_endpoint", "severity", "status", "secret_seen", "detected_at"]
    list_filter = ["source_endpoint", "severity", "status"]

    def get_queryset(self, request):
        return BreachFinding.all_objects.select_related("asset", "tenant")


@admin.register(MonitoredAsset)
class MonitoredAssetAdmin(admin.ModelAdmin):
    list_display = ["asset", "provider", "provider_ref", "is_active", "registered_at"]
    list_filter = ["provider", "is_active"]

    def get_queryset(self, request):
        return MonitoredAsset.all_objects.select_related("asset", "tenant")


@admin.register(BreachIntelligenceUsage)
class BreachIntelligenceUsageAdmin(admin.ModelAdmin):
    list_display = ["tenant", "triggered_by", "requests_consumed", "remaining_after", "created_at"]
    list_filter = ["triggered_by"]

    def get_queryset(self, request):
        return BreachIntelligenceUsage.all_objects.select_related("tenant")


@admin.register(BreachScanJob)
class BreachScanJobAdmin(admin.ModelAdmin):
    list_display = ["tenant", "status", "triggered_by", "created_at", "finished_at"]
    list_filter = ["status", "triggered_by"]

    def get_queryset(self, request):
        return BreachScanJob.all_objects.select_related("tenant", "asset")
