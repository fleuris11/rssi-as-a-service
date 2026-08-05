from django.urls import path

from .views import (
    AIJobDetailView,
    AISettingsView,
    AssistantPreviewView,
    CharterPreviewView,
    ConversationListCreateView,
    GeneratedDocumentDetailView,
    GeneratedDocumentExportPdfView,
    GeneratedDocumentExportView,
    GeneratedDocumentListCreateView,
    GeneratedDocumentValidateView,
    MessageListCreateView,
)

urlpatterns = [
    path("settings/", AISettingsView.as_view(), name="ai-settings"),
    path("preview/charter/", CharterPreviewView.as_view(), name="ai-preview-charter"),
    path("preview/assistant/", AssistantPreviewView.as_view(), name="ai-preview-assistant"),
    path("documents/", GeneratedDocumentListCreateView.as_view(), name="ai-document-list"),
    path(
        "documents/<int:document_id>/",
        GeneratedDocumentDetailView.as_view(),
        name="ai-document-detail",
    ),
    path(
        "documents/<int:document_id>/validate/",
        GeneratedDocumentValidateView.as_view(),
        name="ai-document-validate",
    ),
    path(
        "documents/<int:document_id>/export/",
        GeneratedDocumentExportView.as_view(),
        name="ai-document-export",
    ),
    path(
        "documents/<int:document_id>/export/pdf/",
        GeneratedDocumentExportPdfView.as_view(),
        name="ai-document-export-pdf",
    ),
    path("conversations/", ConversationListCreateView.as_view(), name="ai-conversation-list"),
    path(
        "conversations/<int:conversation_id>/messages/",
        MessageListCreateView.as_view(),
        name="ai-message-list",
    ),
    path("jobs/<int:job_id>/", AIJobDetailView.as_view(), name="ai-job-detail"),
]
