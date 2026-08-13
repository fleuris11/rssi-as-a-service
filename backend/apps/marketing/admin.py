from django.contrib import admin

from .models import DemoRequest


@admin.register(DemoRequest)
class DemoRequestAdmin(admin.ModelAdmin):
    list_display = ["company", "full_name", "email", "status", "created_at"]
    list_filter = ["status", "company_size"]
    search_fields = ["company", "full_name", "email"]
