from django.contrib import admin

from .models import AccessRequest


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ["tenant", "subject_type", "subject_label", "status", "created_at"]
    list_filter = ["status", "subject_type"]

    def get_queryset(self, request):
        # Tenant-scoped model: ``objects`` fails closed outside a scoped
        # request, and admin doesn't go through the middleware.
        return AccessRequest.all_objects.select_related("tenant", "requested_by")
