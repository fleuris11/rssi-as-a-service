from django.http import HttpResponse
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.permissions import IsTenantAdmin, IsTenantMember, IsTenantMemberReadOnlyForReader

from . import services
from .permissions import IsAIEnabled
from .serializers import (
    AIJobSerializer,
    ConversationSerializer,
    DocumentContentUpdateSerializer,
    GeneratedDocumentCreateSerializer,
    GeneratedDocumentSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)
from .tasks import generate_assistant_reply_task, generate_document_task


class AISettingsView(APIView):
    """GET is available to any member (needed to know whether AI features
    should be shown at all); PATCH (the ai_enabled kill switch) is admin
    only — deliberately NOT gated by IsAIEnabled, since disabling must
    always stay reachable even after AI has been turned off."""

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [permissions.IsAuthenticated(), IsTenantAdmin()]
        return [permissions.IsAuthenticated(), IsTenantMember()]

    def get(self, request):
        tenant = request.tenant
        return Response(
            {"ai_enabled": tenant.ai_enabled, "quota": services.get_quota_summary(tenant)}
        )

    def patch(self, request):
        tenant = request.tenant
        if "ai_enabled" in request.data:
            tenant.ai_enabled = bool(request.data["ai_enabled"])
            tenant.save(update_fields=["ai_enabled"])
        return self.get(request)


class CharterPreviewView(APIView):
    """US-4.3 transparency: the pseudonymized payload a charter generation
    would transmit, without launching a job."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember, IsAIEnabled]

    def get(self, request):
        return Response(services.preview_charter_context(request.tenant))


class AssistantPreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember, IsAIEnabled]

    def get(self, request):
        return Response(services.preview_assistant_context(request.tenant))


def _get_document_or_404(request, document_id):
    document = services.get_document(tenant=request.tenant, document_id=document_id)
    if document is None:
        raise NotFound("Document introuvable.")
    return document


class GeneratedDocumentListCreateView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader, IsAIEnabled]
    serializer_class = GeneratedDocumentSerializer

    def get_queryset(self):
        return services.list_documents(self.request.tenant)

    def post(self, request, *args, **kwargs):
        serializer = GeneratedDocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document, job = services.create_document_job(
                tenant=request.tenant,
                user=request.user,
                document_type=serializer.validated_data["type"],
            )
        except services.QuotaExceededError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        generate_document_task.delay(job.id)
        return Response(
            {
                "document": GeneratedDocumentSerializer(document).data,
                "job": AIJobSerializer(job).data,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class GeneratedDocumentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader, IsAIEnabled]

    def get(self, request, document_id):
        return Response(
            GeneratedDocumentSerializer(_get_document_or_404(request, document_id)).data
        )

    def patch(self, request, document_id):
        document = _get_document_or_404(request, document_id)
        serializer = DocumentContentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_document_content(
                document, serializer.validated_data["content_markdown"]
            )
        except services.AIError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(GeneratedDocumentSerializer(document).data)


class GeneratedDocumentValidateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader, IsAIEnabled]

    def post(self, request, document_id):
        document = _get_document_or_404(request, document_id)
        services.validate_document(document)
        return Response(GeneratedDocumentSerializer(document).data)


class GeneratedDocumentExportView(APIView):
    """Markdown export (US-4.1). PDF export was scoped out as non-trivial to
    integrate cleanly in this phase — documented as reste-à-faire in
    docs/journal.md."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember, IsAIEnabled]

    def get(self, request, document_id):
        document = _get_document_or_404(request, document_id)
        response = HttpResponse(
            document.content_markdown, content_type="text/markdown; charset=utf-8"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{document.type}-v{document.version}.md"'
        )
        return response


class ConversationListCreateView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader, IsAIEnabled]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return services.list_conversations(self.request.tenant)

    def post(self, request, *args, **kwargs):
        conversation = services.create_conversation(tenant=request.tenant, user=request.user)
        return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)


def _get_conversation_or_404(request, conversation_id):
    conversation = services.get_conversation(tenant=request.tenant, conversation_id=conversation_id)
    if conversation is None:
        raise NotFound("Conversation introuvable.")
    return conversation


class MessageListCreateView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader, IsAIEnabled]
    serializer_class = MessageSerializer

    def get_queryset(self):
        conversation = _get_conversation_or_404(self.request, self.kwargs["conversation_id"])
        return services.list_messages(conversation)

    def post(self, request, *args, **kwargs):
        conversation = _get_conversation_or_404(request, kwargs["conversation_id"])
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user_message, job = services.create_assistant_job(
                tenant=request.tenant,
                user=request.user,
                conversation=conversation,
                text=serializer.validated_data["content"],
            )
        except services.QuotaExceededError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        generate_assistant_reply_task.delay(job.id)
        return Response(
            {"message": MessageSerializer(user_message).data, "job": AIJobSerializer(job).data},
            status=status.HTTP_202_ACCEPTED,
        )


class AIJobDetailView(APIView):
    """Job pattern polling endpoint (CLAUDE.md rule 3). Deliberately not
    gated by IsAIEnabled: a job already in flight when AI gets disabled
    must remain pollable."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request, job_id):
        job = services.get_job(tenant=request.tenant, job_id=job_id)
        if job is None:
            raise NotFound("Tâche introuvable.")
        return Response(AIJobSerializer(job).data)
