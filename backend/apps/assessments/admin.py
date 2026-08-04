from django.contrib import admin

from .models import Answer, Assessment, Domain, Measure, Referential


@admin.register(Referential)
class ReferentialAdmin(admin.ModelAdmin):
    list_display = ["name", "version", "slug", "is_active"]


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "referential", "order"]
    list_filter = ["referential"]


@admin.register(Measure)
class MeasureAdmin(admin.ModelAdmin):
    list_display = ["code", "official_title", "domain", "level", "effort", "impact"]
    list_filter = ["domain", "level", "effort", "impact"]
    search_fields = ["code", "official_title", "plain_language"]


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "referential", "status", "score_global", "started_at"]
    list_filter = ["status", "referential"]

    def get_queryset(self, request):
        # Assessment.objects is tenant-scoped and fails closed outside a
        # request scoped by TenantScopingMiddleware — admin doesn't go
        # through it, so use the unscoped manager explicitly.
        return Assessment.all_objects.select_related("tenant", "referential")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ["assessment", "measure", "value", "answered_at"]
    list_filter = ["value"]

    def get_queryset(self, request):
        return Answer.all_objects.select_related("assessment", "measure")
