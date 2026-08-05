from django.contrib import admin

from .models import AIJob, AIUsageLog, AIUsageQuota, Conversation, GeneratedDocument, Message


@admin.register(AIUsageQuota)
class AIUsageQuotaAdmin(admin.ModelAdmin):
    list_display = ["tenant", "period", "tokens_used", "monthly_token_limit"]
    list_filter = ["period"]

    def get_queryset(self, request):
        return AIUsageQuota.all_objects.select_related("tenant")


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = [
        "tenant",
        "use_case",
        "model",
        "tokens_input",
        "tokens_output",
        "cost_estimate_usd",
        "created_at",
    ]
    list_filter = ["use_case", "model"]

    def get_queryset(self, request):
        return AIUsageLog.all_objects.select_related("tenant")


@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ["tenant", "use_case", "status", "created_at", "finished_at"]
    list_filter = ["use_case", "status"]

    def get_queryset(self, request):
        return AIJob.all_objects.select_related("tenant")


@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(admin.ModelAdmin):
    list_display = ["tenant", "type", "version", "status", "created_at"]
    list_filter = ["type", "status"]

    def get_queryset(self, request):
        return GeneratedDocument.all_objects.select_related("tenant")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["tenant", "created_by", "created_at", "updated_at"]

    def get_queryset(self, request):
        return Conversation.all_objects.select_related("tenant")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["tenant", "conversation", "role", "created_at"]
    list_filter = ["role"]

    def get_queryset(self, request):
        return Message.all_objects.select_related("tenant", "conversation")
