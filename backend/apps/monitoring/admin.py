from django.contrib import admin

from .models import Alert, Asset, CheckResult


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ["value", "type", "tenant", "is_active", "created_at"]
    list_filter = ["type", "is_active"]
    search_fields = ["value"]

    def get_queryset(self, request):
        # Asset.objects is tenant-scoped and fails closed outside a
        # request scoped by TenantScopingMiddleware — admin doesn't go
        # through it, so use the unscoped manager explicitly.
        return Asset.all_objects.select_related("tenant")


@admin.register(CheckResult)
class CheckResultAdmin(admin.ModelAdmin):
    list_display = ["asset", "check_type", "status", "latency_ms", "checked_at"]
    list_filter = ["check_type", "status"]

    def get_queryset(self, request):
        return CheckResult.all_objects.select_related("asset", "tenant")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["asset", "alert_type", "severity", "is_open", "opened_at"]
    list_filter = ["alert_type", "severity", "is_open"]

    def get_queryset(self, request):
        return Alert.all_objects.select_related("asset", "tenant")
