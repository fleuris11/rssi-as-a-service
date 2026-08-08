from django.contrib import admin

from .models import (
    BreachFinding,
    BreachIntelligenceUsage,
    BreachScanJob,
    MonitoredAsset,
    SecretRevealAudit,
)


@admin.register(BreachFinding)
class BreachFindingAdmin(admin.ModelAdmin):
    # secret_masked (jamais le secret en clair — ADR-014) affiché à dessein :
    # c'est déjà une forme masquée, pas la valeur d'origine.
    list_display = ["asset", "source_endpoint", "severity", "status", "has_secret", "detected_at"]
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


@admin.register(SecretRevealAudit)
class SecretRevealAuditAdmin(admin.ModelAdmin):
    # Jamais le secret lui-même (le modèle ne le stocke pas) — uniquement le
    # qui/quoi/quand de chaque tentative, accordée ou refusée (ADR-014).
    list_display = ["tenant", "user", "finding", "success", "denial_reason", "created_at"]
    list_filter = ["success", "denial_reason"]

    def get_queryset(self, request):
        return SecretRevealAudit.all_objects.select_related("tenant", "user", "finding")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
