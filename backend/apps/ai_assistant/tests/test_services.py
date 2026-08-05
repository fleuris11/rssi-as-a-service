from unittest.mock import MagicMock, patch

import pytest

from apps.ai_assistant import services
from apps.ai_assistant.models import AIJob, AIUsageLog, AIUsageQuota, GeneratedDocument

pytestmark = pytest.mark.django_db


def _fake_response(text="Contenu généré.", tokens_in=100, tokens_out=200):
    response = MagicMock()
    response.content = [MagicMock(type="text", text=text)]
    response.usage.input_tokens = tokens_in
    response.usage.output_tokens = tokens_out
    return response


class TestAIEnabled:
    def test_raises_when_disabled(self, tenant):
        tenant.ai_enabled = False
        tenant.save(update_fields=["ai_enabled"])
        with pytest.raises(services.AIDisabledError):
            services.ensure_ai_enabled(tenant)

    def test_does_not_raise_when_enabled(self, tenant):
        services.ensure_ai_enabled(tenant)


class TestQuota:
    def test_creates_current_month_quota_with_configured_default_limit(self, tenant, settings):
        settings.AI_DEFAULT_MONTHLY_TOKEN_LIMIT = 1000
        quota = services.get_or_create_current_quota(tenant)
        assert quota.monthly_token_limit == 1000
        assert quota.tokens_used == 0

    def test_is_idempotent_for_the_same_month(self, tenant):
        first = services.get_or_create_current_quota(tenant)
        second = services.get_or_create_current_quota(tenant)
        assert first.id == second.id

    def test_ensure_quota_available_raises_when_exhausted(self, tenant):
        quota = services.get_or_create_current_quota(tenant)
        AIUsageQuota.all_objects.filter(id=quota.id).update(tokens_used=quota.monthly_token_limit)
        with pytest.raises(services.QuotaExceededError):
            services.ensure_quota_available(tenant)

    def test_record_usage_increments_quota_and_writes_a_log(self, tenant):
        services.record_usage(
            tenant=tenant,
            use_case=AIUsageLog.UseCase.ASSISTANT_REPLY,
            model="claude-haiku-4-5",
            tokens_input=100,
            tokens_output=50,
            duration_ms=250,
        )
        quota = services.get_or_create_current_quota(tenant)
        assert quota.tokens_used == 150
        log = AIUsageLog.all_objects.get(tenant=tenant)
        assert log.tokens_input == 100
        assert log.tokens_output == 50
        assert log.cost_estimate_usd > 0

    def test_get_quota_summary_reports_remaining_tokens(self, tenant, settings):
        settings.AI_DEFAULT_MONTHLY_TOKEN_LIMIT = 1000
        services.record_usage(
            tenant=tenant,
            use_case=AIUsageLog.UseCase.ASSISTANT_REPLY,
            model="claude-haiku-4-5",
            tokens_input=100,
            tokens_output=50,
            duration_ms=10,
        )
        summary = services.get_quota_summary(tenant)
        assert summary["tokens_used"] == 150
        assert summary["remaining_tokens"] == 850


class TestEstimateCostUsd:
    def test_haiku_is_cheaper_than_sonnet_for_the_same_volume(self):
        haiku_cost = services.estimate_cost_usd("claude-haiku-4-5", 1_000_000, 1_000_000)
        sonnet_cost = services.estimate_cost_usd("claude-sonnet-5", 1_000_000, 1_000_000)
        assert haiku_cost < sonnet_cost


class TestCreateDocumentJob:
    def test_raises_when_ai_disabled(self, tenant, tenant_owner):
        tenant.ai_enabled = False
        tenant.save(update_fields=["ai_enabled"])
        with pytest.raises(services.AIDisabledError):
            services.create_document_job(
                tenant=tenant,
                user=tenant_owner,
                document_type=GeneratedDocument.DocumentType.IT_CHARTER,
            )
        assert GeneratedDocument.all_objects.count() == 0

    def test_raises_when_quota_exhausted(self, tenant, tenant_owner):
        quota = services.get_or_create_current_quota(tenant)
        AIUsageQuota.all_objects.filter(id=quota.id).update(tokens_used=quota.monthly_token_limit)
        with pytest.raises(services.QuotaExceededError):
            services.create_document_job(
                tenant=tenant,
                user=tenant_owner,
                document_type=GeneratedDocument.DocumentType.IT_CHARTER,
            )
        assert GeneratedDocument.all_objects.count() == 0

    def test_creates_a_generating_document_and_a_pending_job(self, tenant, tenant_owner):
        document, job = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        assert document.status == GeneratedDocument.Status.GENERATING
        assert document.version == 1
        assert job.status == AIJob.Status.PENDING
        assert job.result_ref == {"document_id": document.id}

    def test_second_generation_increments_the_version(self, tenant, tenant_owner):
        document_1, _job_1 = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        document_1.status = GeneratedDocument.Status.DRAFT
        document_1.save(update_fields=["status"])

        document_2, _job_2 = services.create_document_job(
            tenant=tenant,
            user=tenant_owner,
            document_type=GeneratedDocument.DocumentType.IT_CHARTER,
        )
        assert document_2.version == 2


class TestGenerateCharterDocument:
    def test_rehydrates_the_company_name_and_marks_draft(self, tenant):
        document = GeneratedDocument.all_objects.create(
            tenant=tenant, type=GeneratedDocument.DocumentType.IT_CHARTER, version=1
        )
        response = _fake_response(text="# Charte de {{COMPANY}}\n\nBienvenue chez {{COMPANY}}.")
        with patch("apps.ai_assistant.services._get_client") as mock_get_client:
            mock_get_client.return_value.messages.create.return_value = response
            services.generate_charter_document(document=document)

        document.refresh_from_db()
        assert document.status == GeneratedDocument.Status.DRAFT
        assert tenant.name in document.content_markdown
        assert "{{COMPANY}}" not in document.content_markdown


class TestDocumentLifecycle:
    def test_cannot_edit_a_validated_document(self, tenant):
        document = GeneratedDocument.all_objects.create(
            tenant=tenant,
            type=GeneratedDocument.DocumentType.IT_CHARTER,
            version=1,
            status=GeneratedDocument.Status.VALIDATED,
        )
        with pytest.raises(services.AIError):
            services.update_document_content(document, "# Nouveau contenu")

    def test_validate_sets_status_and_timestamp(self, tenant):
        document = GeneratedDocument.all_objects.create(
            tenant=tenant,
            type=GeneratedDocument.DocumentType.IT_CHARTER,
            version=1,
            status=GeneratedDocument.Status.DRAFT,
        )
        services.validate_document(document)
        assert document.status == GeneratedDocument.Status.VALIDATED
        assert document.validated_at is not None


class TestRenderDocumentPdf:
    """WeasyPrint needs system libraries (Pango/Cairo/GDK-Pixbuf) not
    present on every dev machine (notably plain Windows) — this only runs
    where they're installed (Docker image, CI backend job; see
    docs/adr/012-export-pdf-weasyprint.md)."""

    def test_produces_a_pdf_document(self, tenant):
        document = GeneratedDocument.all_objects.create(
            tenant=tenant,
            type=GeneratedDocument.DocumentType.IT_CHARTER,
            version=1,
            content_markdown=(
                "# Charte informatique\n\nBienvenue chez {{COMPANY}}.\n\n"
                "## Mots de passe\n\n- Au moins 12 caractères\n- Pas de réutilisation"
            ),
        )

        pdf_bytes = services.render_document_pdf(document)

        assert pdf_bytes.startswith(b"%PDF")

    def test_empty_document_still_produces_a_valid_pdf(self, tenant):
        document = GeneratedDocument.all_objects.create(
            tenant=tenant, type=GeneratedDocument.DocumentType.IT_CHARTER, version=1
        )

        pdf_bytes = services.render_document_pdf(document)

        assert pdf_bytes.startswith(b"%PDF")


class TestCreateAssistantJob:
    def test_raises_when_ai_disabled(self, tenant, tenant_owner):
        conversation = services.create_conversation(tenant=tenant, user=tenant_owner)
        tenant.ai_enabled = False
        tenant.save(update_fields=["ai_enabled"])
        with pytest.raises(services.AIDisabledError):
            services.create_assistant_job(
                tenant=tenant, user=tenant_owner, conversation=conversation, text="Bonjour"
            )

    def test_creates_user_message_and_pending_job(self, tenant, tenant_owner):
        from apps.ai_assistant.models import Message

        conversation = services.create_conversation(tenant=tenant, user=tenant_owner)
        user_message, job = services.create_assistant_job(
            tenant=tenant,
            user=tenant_owner,
            conversation=conversation,
            text="Suis-je conforme au RGPD ?",
        )
        assert user_message.role == Message.Role.USER
        assert job.status == AIJob.Status.PENDING
        assert job.result_ref == {
            "conversation_id": conversation.id,
            "user_message_id": user_message.id,
        }


class TestGenerateAssistantReply:
    def test_creates_an_assistant_message_and_bumps_conversation(self, tenant, tenant_owner):
        conversation = services.create_conversation(tenant=tenant, user=tenant_owner)
        from apps.ai_assistant.models import Message

        Message.all_objects.create(
            tenant=tenant, conversation=conversation, role=Message.Role.USER, content="Bonjour"
        )
        response = _fake_response(text="Bonjour, voici ma réponse.")
        with patch("apps.ai_assistant.services._get_client") as mock_get_client:
            mock_get_client.return_value.messages.create.return_value = response
            reply = services.generate_assistant_reply(conversation=conversation)

        assert reply.role == Message.Role.ASSISTANT
        assert reply.content == "Bonjour, voici ma réponse."


class TestWeatherEnrichmentFallback:
    def test_returns_none_when_ai_disabled(self, tenant):
        tenant.ai_enabled = False
        tenant.save(update_fields=["ai_enabled"])
        assert services.enrich_weather_summary(tenant=tenant, deterministic_context={}) is None

    def test_returns_none_when_quota_exhausted(self, tenant):
        quota = services.get_or_create_current_quota(tenant)
        AIUsageQuota.all_objects.filter(id=quota.id).update(tokens_used=quota.monthly_token_limit)
        assert services.enrich_weather_summary(tenant=tenant, deterministic_context={}) is None

    def test_returns_none_on_any_api_failure(self, tenant):
        with patch(
            "apps.ai_assistant.services._get_client", side_effect=RuntimeError("panne réseau")
        ):
            assert services.enrich_weather_summary(tenant=tenant, deterministic_context={}) is None
        # Never logged as usage — the call never actually happened.
        assert AIUsageLog.all_objects.filter(tenant=tenant).count() == 0

    def test_returns_rehydrated_text_on_success(self, tenant):
        response = _fake_response(
            text="{{COMPANY}} se porte bien aujourd'hui.", tokens_in=10, tokens_out=5
        )
        with patch("apps.ai_assistant.services._get_client") as mock_get_client:
            mock_get_client.return_value.messages.create.return_value = response
            result = services.enrich_weather_summary(
                tenant=tenant, deterministic_context={"synthese": "ok"}
            )
        assert result == f"{tenant.name} se porte bien aujourd'hui."
