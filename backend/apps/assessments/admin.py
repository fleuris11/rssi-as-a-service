from django.contrib import admin

from .models import (
    Answer,
    Assessment,
    Domain,
    Measure,
    MeasureStatementOverride,
    MeasureSubset,
    Referential,
    ReferentialAssignment,
    SubsetMeasure,
)


@admin.register(Referential)
class ReferentialAdmin(admin.ModelAdmin):
    list_display = ["name", "version", "slug", "kind", "publisher", "owner_tenant", "is_active"]
    list_filter = ["kind", "is_active"]


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "referential", "order"]
    list_filter = ["referential"]


@admin.register(Measure)
class MeasureAdmin(admin.ModelAdmin):
    list_display = ["code", "official_title", "referential", "domain", "level", "weight"]
    list_filter = ["referential", "level", "effort", "impact"]
    search_fields = ["code", "number", "official_title", "plain_language"]
    ordering = ["referential", "order"]


@admin.register(MeasureSubset)
class MeasureSubsetAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "referential", "owner_tenant", "is_active"]
    list_filter = ["referential", "is_active"]


@admin.register(SubsetMeasure)
class SubsetMeasureAdmin(admin.ModelAdmin):
    list_display = ["subset", "measure", "order"]
    list_filter = ["subset"]


@admin.register(ReferentialAssignment)
class ReferentialAssignmentAdmin(admin.ModelAdmin):
    list_display = ["tenant", "referential", "granted_at", "revoked_at"]
    list_filter = ["referential"]

    def get_queryset(self, request):
        # Tenant-scoped model: ``objects`` fails closed outside a request
        # scoped by TenantScopingMiddleware, which admin doesn't go through.
        return ReferentialAssignment.all_objects.select_related("tenant", "referential")


@admin.register(MeasureStatementOverride)
class MeasureStatementOverrideAdmin(admin.ModelAdmin):
    list_display = ["tenant", "measure", "updated_at"]

    def get_queryset(self, request):
        return MeasureStatementOverride.all_objects.select_related("tenant", "measure")


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "referential", "subset", "status", "score_global", "started_at"]
    list_filter = ["status", "referential"]

    def get_queryset(self, request):
        # Assessment.objects is tenant-scoped and fails closed outside a
        # request scoped by TenantScopingMiddleware — admin doesn't go
        # through it, so use the unscoped manager explicitly.
        return Assessment.all_objects.select_related("tenant", "referential", "subset")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ["assessment", "measure", "value", "answered_at"]
    list_filter = ["value"]

    def get_queryset(self, request):
        return Answer.all_objects.select_related("assessment", "measure")
