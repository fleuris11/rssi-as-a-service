from django.contrib import admin

from .models import EmailLog, NotificationPreferences


@admin.register(NotificationPreferences)
class NotificationPreferencesAdmin(admin.ModelAdmin):
    list_display = ["tenant", "weather_enabled", "weather_time", "realtime_alerts_enabled"]

    def get_queryset(self, request):
        return NotificationPreferences.all_objects.select_related("tenant")


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ["tenant", "kind", "recipient", "sent_at"]
    list_filter = ["kind"]

    def get_queryset(self, request):
        return EmailLog.all_objects.select_related("tenant")
