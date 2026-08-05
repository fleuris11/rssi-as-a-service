from unittest.mock import MagicMock, patch

import pytest

from apps.ai_assistant import services, tasks
from apps.ai_assistant.models import AIJob, GeneratedDocument, Message

pytestmark = pytest.mark.django_db


def _fake_response(text="Contenu généré.", tokens_in=100, tokens_out=200):
    response = MagicMock()
    response.content = [MagicMock(type="text", text=text)]
    response.usage.input_tokens = tokens_in
    response.usage.output_tokens = tokens_out
    return response


class TestGenerateDocumentTask:
    def test_marks_job_done_and_document_draft_on_success(self, tenant, tenant_owner):
        document, job = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        with patch("apps.ai_assistant.services._get_client") as mock_get_client:
            mock_get_client.return_value.messages.create.return_value = _fake_response()
            tasks.generate_document_task(job.id)

        job.refresh_from_db()
        document.refresh_from_db()
        assert job.status == AIJob.Status.DONE
        assert document.status == GeneratedDocument.Status.DRAFT
        assert document.content_markdown

    def test_missing_document_fails_the_job_cleanly(self, tenant, tenant_owner):
        document, job = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        GeneratedDocument.all_objects.filter(id=document.id).delete()

        tasks.generate_document_task(job.id)

        job.refresh_from_db()
        assert job.status == AIJob.Status.FAILED

    def test_is_a_no_op_on_an_already_done_job(self, tenant, tenant_owner):
        document, job = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        services.mark_job_done(job)

        with patch("apps.ai_assistant.services._get_client") as mock_get_client:
            tasks.generate_document_task(job.id)
            mock_get_client.assert_not_called()

    def test_unknown_job_id_is_a_no_op(self):
        tasks.generate_document_task(999999)

    def test_a_running_job_is_reprocessed_not_skipped(self, tenant, tenant_owner):
        """Regression: a job already marked ``running`` is exactly what a
        retried attempt sees (the first attempt calls mark_job_running
        before the failure that triggers the retry) — the idempotency guard
        must not treat that as "already handled", or the job would be
        stranded in ``running`` forever instead of ever reaching a terminal
        status. Only done/failed jobs are skipped."""
        document, job = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        services.mark_job_running(job)

        with patch("apps.ai_assistant.services._get_client") as mock_get_client:
            mock_get_client.return_value.messages.create.return_value = _fake_response()
            tasks.generate_document_task(job.id)

        job.refresh_from_db()
        document.refresh_from_db()
        assert job.status == AIJob.Status.DONE
        assert document.status == GeneratedDocument.Status.DRAFT


class TestGenerateAssistantReplyTask:
    def test_marks_job_done_with_message_id(self, tenant, tenant_owner):
        conversation = services.create_conversation(tenant=tenant, user=tenant_owner)
        user_message, job = services.create_assistant_job(
            tenant=tenant, user=tenant_owner, conversation=conversation, text="Bonjour"
        )
        with patch("apps.ai_assistant.services._get_client") as mock_get_client:
            mock_get_client.return_value.messages.create.return_value = _fake_response(
                text="Bonjour, comment puis-je vous aider ?"
            )
            tasks.generate_assistant_reply_task(job.id)

        job.refresh_from_db()
        assert job.status == AIJob.Status.DONE
        assert "message_id" in job.result_ref
        reply = Message.all_objects.get(id=job.result_ref["message_id"])
        assert reply.role == Message.Role.ASSISTANT
        assert reply.content == "Bonjour, comment puis-je vous aider ?"
        assert Message.all_objects.filter(id=user_message.id).exists()

    def test_missing_conversation_fails_the_job_cleanly(self, tenant, tenant_owner):
        conversation = services.create_conversation(tenant=tenant, user=tenant_owner)
        _user_message, job = services.create_assistant_job(
            tenant=tenant, user=tenant_owner, conversation=conversation, text="Bonjour"
        )
        conversation.delete()

        tasks.generate_assistant_reply_task(job.id)

        job.refresh_from_db()
        assert job.status == AIJob.Status.FAILED

    def test_a_running_job_is_reprocessed_not_skipped(self, tenant, tenant_owner):
        conversation = services.create_conversation(tenant=tenant, user=tenant_owner)
        _user_message, job = services.create_assistant_job(
            tenant=tenant, user=tenant_owner, conversation=conversation, text="Bonjour"
        )
        services.mark_job_running(job)

        with patch("apps.ai_assistant.services._get_client") as mock_get_client:
            mock_get_client.return_value.messages.create.return_value = _fake_response(
                text="Réponse après reprise."
            )
            tasks.generate_assistant_reply_task(job.id)

        job.refresh_from_db()
        assert job.status == AIJob.Status.DONE
