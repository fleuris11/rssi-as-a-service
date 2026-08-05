from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.ai_assistant import services
from apps.ai_assistant.models import AIUsageQuota, GeneratedDocument
from apps.tenants.models import Membership

pytestmark = pytest.mark.django_db


def _login(api_client, email, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


def _auth(api_client, user, tenant):
    access = _login(api_client, user.email)
    return {"HTTP_AUTHORIZATION": f"Bearer {access}", "HTTP_X_TENANT_ID": str(tenant.id)}


class TestAISettings:
    def test_get_returns_ai_enabled_and_quota(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("ai-settings"), **headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["ai_enabled"] is True
        assert "remaining_tokens" in response.data["quota"]

    def test_reader_cannot_toggle_ai_enabled(self, api_client, tenant, user_factory):
        reader = user_factory(email="reader@example.com")
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        headers = _auth(api_client, reader, tenant)

        response = api_client.patch(
            reverse("ai-settings"), {"ai_enabled": False}, format="json", **headers
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_disable_ai(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.patch(
            reverse("ai-settings"), {"ai_enabled": False}, format="json", **headers
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["ai_enabled"] is False
        tenant.refresh_from_db()
        assert tenant.ai_enabled is False


class TestAIDisabledReturns403Everywhere:
    """US-4.3: ai_enabled=false makes every AI function return 403 — the
    settings endpoint itself is deliberately exempt (see TestAISettings),
    it must stay reachable to re-enable AI."""

    @pytest.fixture(autouse=True)
    def _disable_ai(self, tenant):
        tenant.ai_enabled = False
        tenant.save(update_fields=["ai_enabled"])

    @pytest.mark.parametrize(
        "method,url_name,url_kwargs",
        [
            ("get", "ai-preview-charter", {}),
            ("get", "ai-preview-assistant", {}),
            ("get", "ai-document-list", {}),
            ("post", "ai-document-list", {}),
            ("get", "ai-conversation-list", {}),
            ("post", "ai-conversation-list", {}),
        ],
    )
    def test_returns_403(self, api_client, tenant, tenant_owner, method, url_name, url_kwargs):
        headers = _auth(api_client, tenant_owner, tenant)
        response = getattr(api_client, method)(reverse(url_name, kwargs=url_kwargs), **headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestQuotaExceeded:
    def test_document_creation_is_refused_cleanly(self, api_client, tenant, tenant_owner):
        quota = services.get_or_create_current_quota(tenant)
        AIUsageQuota.all_objects.filter(id=quota.id).update(tokens_used=quota.monthly_token_limit)
        headers = _auth(api_client, tenant_owner, tenant)

        with patch("apps.ai_assistant.views.generate_document_task.delay") as mock_delay:
            response = api_client.post(
                reverse("ai-document-list"), {"type": "it_charter"}, format="json", **headers
            )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        mock_delay.assert_not_called()
        assert GeneratedDocument.all_objects.count() == 0


class TestDocumentJobCreation:
    def test_creates_document_and_dispatches_job(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)

        with patch("apps.ai_assistant.views.generate_document_task.delay") as mock_delay:
            response = api_client.post(
                reverse("ai-document-list"), {"type": "it_charter"}, format="json", **headers
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_delay.assert_called_once()
        assert response.data["document"]["status"] == "generating"
        assert response.data["job"]["status"] == "pending"

    def test_reader_cannot_generate_a_document(self, api_client, tenant, user_factory):
        reader = user_factory(email="reader@example.com")
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        headers = _auth(api_client, reader, tenant)

        response = api_client.post(
            reverse("ai-document-list"), {"type": "it_charter"}, format="json", **headers
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestDocumentLifecycleApi:
    def test_edit_then_validate_then_cannot_edit(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        document, _job = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        document.status = GeneratedDocument.Status.DRAFT
        document.content_markdown = "# Brouillon"
        document.save(update_fields=["status", "content_markdown"])

        patch_response = api_client.patch(
            reverse("ai-document-detail", kwargs={"document_id": document.id}),
            {"content_markdown": "# Version corrigée"},
            format="json",
            **headers,
        )
        assert patch_response.status_code == status.HTTP_200_OK
        assert patch_response.data["content_markdown"] == "# Version corrigée"

        validate_response = api_client.post(
            reverse("ai-document-validate", kwargs={"document_id": document.id}), **headers
        )
        assert validate_response.status_code == status.HTTP_200_OK
        assert validate_response.data["status"] == "validated"

        blocked_response = api_client.patch(
            reverse("ai-document-detail", kwargs={"document_id": document.id}),
            {"content_markdown": "# Encore"},
            format="json",
            **headers,
        )
        assert blocked_response.status_code == status.HTTP_400_BAD_REQUEST

    def test_export_returns_markdown_attachment(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        document, _job = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        document.content_markdown = "# Charte"
        document.save(update_fields=["content_markdown"])

        response = api_client.get(
            reverse("ai-document-export", kwargs={"document_id": document.id}), **headers
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"].startswith("text/markdown")
        assert response.content.decode() == "# Charte"

    def test_export_pdf_returns_a_pdf_attachment(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        document, _job = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        document.content_markdown = "# Charte\n\nBienvenue."
        document.save(update_fields=["content_markdown"])

        response = api_client.get(
            reverse("ai-document-export-pdf", kwargs={"document_id": document.id}), **headers
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")


class TestAssistantJobCreation:
    def test_creates_conversation_message_and_dispatches_job(
        self, api_client, tenant, tenant_owner
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        conversation_response = api_client.post(reverse("ai-conversation-list"), **headers)
        assert conversation_response.status_code == status.HTTP_201_CREATED
        conversation_id = conversation_response.data["id"]

        with patch("apps.ai_assistant.views.generate_assistant_reply_task.delay") as mock_delay:
            response = api_client.post(
                reverse("ai-message-list", kwargs={"conversation_id": conversation_id}),
                {"content": "Suis-je conforme au RGPD ?"},
                format="json",
                **headers,
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_delay.assert_called_once()
        assert response.data["message"]["role"] == "user"
        assert response.data["job"]["status"] == "pending"

    def test_rejects_an_empty_message(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        conversation_response = api_client.post(reverse("ai-conversation-list"), **headers)
        conversation_id = conversation_response.data["id"]

        response = api_client.post(
            reverse("ai-message-list", kwargs={"conversation_id": conversation_id}),
            {"content": "   "},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestJobPolling:
    def test_poll_job_status(self, api_client, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        _document, job = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )

        response = api_client.get(reverse("ai-job-detail", kwargs={"job_id": job.id}), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "pending"


class TestTenantIsolation:
    def test_cannot_read_another_tenants_document(
        self, api_client, tenant, tenant_owner, other_tenant, user_factory
    ):
        other_owner = user_factory(email="other-owner-doc@example.com")
        Membership.all_objects.create(
            tenant=other_tenant, user=other_owner, role=Membership.Role.ADMIN
        )
        document, _job = services.create_document_job(
            tenant=other_tenant,
            user=other_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )

        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(
            reverse("ai-document-detail", kwargs={"document_id": document.id}), **headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_read_another_tenants_conversation_messages(
        self, api_client, tenant, tenant_owner, other_tenant, user_factory
    ):
        other_owner = user_factory(email="other-owner-conv@example.com")
        Membership.all_objects.create(
            tenant=other_tenant, user=other_owner, role=Membership.Role.ADMIN
        )
        conversation = services.create_conversation(tenant=other_tenant, user=other_owner)

        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(
            reverse("ai-message-list", kwargs={"conversation_id": conversation.id}), **headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_poll_another_tenants_job(
        self, api_client, tenant, tenant_owner, other_tenant, user_factory
    ):
        other_owner = user_factory(email="other-owner-job@example.com")
        Membership.all_objects.create(
            tenant=other_tenant, user=other_owner, role=Membership.Role.ADMIN
        )
        _document, job = services.create_document_job(
            tenant=other_tenant,
            user=other_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )

        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("ai-job-detail", kwargs={"job_id": job.id}), **headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_document_list_only_shows_own_tenants_documents(
        self, api_client, tenant, tenant_owner, other_tenant, user_factory
    ):
        other_owner = user_factory(email="other-owner-list@example.com")
        Membership.all_objects.create(
            tenant=other_tenant, user=other_owner, role=Membership.Role.ADMIN
        )
        services.create_document_job(
            tenant=other_tenant,
            user=other_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )

        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("ai-document-list"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
