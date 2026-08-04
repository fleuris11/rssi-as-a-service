from django.contrib import admin

from .models import Membership, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "sector", "is_active", "created_at"]
    search_fields = ["name", "slug"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["tenant", "user", "role", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__email", "tenant__name"]

    def get_queryset(self, request):
        # Membership.objects is tenant-scoped and fails closed outside a
        # request that went through TenantScopingMiddleware (admin doesn't)
        # — use the unscoped manager explicitly here.
        return Membership.all_objects.select_related("tenant", "user")
