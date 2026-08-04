from django.contrib import admin

from .models import ActionItem


@admin.register(ActionItem)
class ActionItemAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "measure", "status", "assignee", "updated_at"]
    list_filter = ["status"]

    def get_queryset(self, request):
        # ActionItem.objects is tenant-scoped and fails closed outside a
        # request scoped by TenantScopingMiddleware — admin doesn't go
        # through it, so use the unscoped manager explicitly.
        return ActionItem.all_objects.select_related("tenant", "measure", "assignee")
