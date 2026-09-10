from django.contrib import admin

from .models import WatchSource, WatchUpdate


@admin.register(WatchSource)
class WatchSourceAdmin(admin.ModelAdmin):
    list_display = ["publisher", "name", "format", "is_active", "consecutive_failures"]
    list_filter = ["format", "is_active"]


@admin.register(WatchUpdate)
class WatchUpdateAdmin(admin.ModelAdmin):
    list_display = ["title", "source", "status", "published_at", "detected_at"]
    list_filter = ["status", "kind", "source"]
    search_fields = ["title"]
