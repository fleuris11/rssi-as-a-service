"""ADR-005's mandated property test: "aucune PII ne sort". Builds the exact
payload apps.ai_assistant.services would transmit to the Anthropic API for
both use cases (mocked SDK), across several scenarios including special
characters, and asserts none of the tenant's real sensitive values appear
in it.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.ai_assistant import services
from apps.ai_assistant.models import Conversation, GeneratedDocument, Message
from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset
from apps.threat_intelligence import services as threat_intelligence_services
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db


def _fake_response(text="Réponse factice de l'API.", tokens_in=42, tokens_out=17):
    response = MagicMock()
    response.content = [MagicMock(type="text", text=text)]
    response.usage.input_tokens = tokens_in
    response.usage.output_tokens = tokens_out
    return response


@pytest.fixture
def mock_claude_client():
    with patch("apps.ai_assistant.services._get_client") as mock_get_client:
        client = MagicMock()
        client.messages.create.return_value = _fake_response()
        mock_get_client.return_value = client
        yield client


SPECIAL_CHAR_SCENARIOS = [
    {
        "company": "Café & Cie (Paris) + Associés",
        "member_name": "Jean-Édouard O'Brien",
        "member_email": "j.edouard+test@example-mail.fr",
        "website": "https://sous-domaine.exemple-test.fr",
        "email_domain": "exemple-test.fr",
    },
    {
        "company": 'Boulangerie "Le Bon Pain" S.à.r.l.',
        "member_name": "Zoé Núñez",
        "member_email": "zoe.nunez@bon-pain.io",
        "website": "https://shop.bon-pain.io",
        "email_domain": "bon-pain.io",
    },
    {
        "company": "R&D Systèmes 2.0",
        "member_name": "Đặng Thị Mai",
        "member_email": "mai.dang@rd-systemes2.fr",
        "website": "https://portail.rd-systemes2.fr",
        "email_domain": "rd-systemes2.fr",
    },
    {
        "company": "Entreprise (Test)+*.[Spécial]",
        "member_name": "A. B (Régie)",
        "member_email": "a.b+regie@test-domaine.com",
        "website": "https://app.test-domaine.com",
        "email_domain": "test-domaine.com",
    },
]


@pytest.fixture(params=SPECIAL_CHAR_SCENARIOS, ids=lambda s: s["company"])
def scenario_tenant(request, tenant, tenant_owner):
    scenario = request.param
    tenant.name = scenario["company"]
    tenant.sector = "Commerce de détail"
    tenant.headcount = 12
    tenant.save(update_fields=["name", "sector", "headcount"])

    first_name, _, last_name = scenario["member_name"].partition(" ")
    tenant_owner.first_name = first_name
    tenant_owner.last_name = last_name
    tenant_owner.email = scenario["member_email"]
    tenant_owner.save(update_fields=["first_name", "last_name", "email"])

    monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value=scenario["website"],
        ownership_confirmed=True,
    )
    monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.EMAIL_DOMAIN,
        value=scenario["email_domain"],
        ownership_confirmed=True,
    )
    return tenant, scenario


def _assert_no_leak(payload: str, scenario: dict):
    assert scenario["company"] not in payload
    assert scenario["member_name"] not in payload
    assert scenario["member_email"] not in payload
    assert scenario["website"] not in payload
    assert scenario["email_domain"] not in payload


class TestNoLeakProperty:
    def test_charter_generation_payload_never_contains_real_values(
        self, scenario_tenant, mock_claude_client
    ):
        tenant, scenario = scenario_tenant
        document = GeneratedDocument.all_objects.create(
            tenant=tenant, type=GeneratedDocument.DocumentType.IT_CHARTER, version=1
        )

        services.generate_charter_document(document=document)

        call_kwargs = mock_claude_client.messages.create.call_args.kwargs
        payload = call_kwargs["system"] + str(call_kwargs["messages"])
        _assert_no_leak(payload, scenario)

    def test_assistant_reply_payload_never_contains_real_values(
        self, scenario_tenant, mock_claude_client
    ):
        tenant, scenario = scenario_tenant
        conversation = Conversation.all_objects.create(tenant=tenant)
        Message.all_objects.create(
            tenant=tenant,
            conversation=conversation,
            role=Message.Role.USER,
            content=(
                f"Bonjour, je travaille chez {scenario['company']}, vous pouvez me "
                f"joindre à {scenario['member_email']} ou via {scenario['website']}."
            ),
        )

        services.generate_assistant_reply(conversation=conversation)

        call_kwargs = mock_claude_client.messages.create.call_args.kwargs
        payload = call_kwargs["system"] + str(call_kwargs["messages"])
        _assert_no_leak(payload, scenario)

    def test_weather_enrichment_payload_never_contains_real_values(
        self, scenario_tenant, mock_claude_client
    ):
        tenant, scenario = scenario_tenant

        services.enrich_weather_summary(
            tenant=tenant,
            deterministic_context={
                "synthese": "Tout va bien",
                "actifs": [{"valeur": scenario["website"]}],
            },
        )

        call_kwargs = mock_claude_client.messages.create.call_args.kwargs
        payload = call_kwargs["system"] + str(call_kwargs["messages"])
        _assert_no_leak(payload, scenario)


class TestBreachDataNoLeak:
    """Phase 7 (ADR-013/014): BreachFinding data reaches the assistant and
    weather-enrichment contexts (apps.ai_assistant.services.
    build_assistant_context, apps.notifications.services.
    build_weather_context) — this must go through the exact same
    pseudonymization pipeline as every other identifying data on the
    platform (CLAUDE.md architecture rule 3). Reuses scenario_tenant's
    special-character company/email/domain scenarios so a breach-specific
    regression can't hide behind a "simple" test value.
    """

    def _ingest_finding_for_tenant_email(self, tenant, scenario):
        website = Asset.all_objects.get(tenant=tenant, type=Asset.Type.WEBSITE)
        raw = RawFinding(
            endpoint="stealer",
            payload={"email": scenario["member_email"], "password": "SuperSecretRealValue123"},
        )
        return threat_intelligence_services.ingest_raw_findings(
            tenant=tenant, asset=website, raw_findings=[raw]
        )[0]

    def test_assistant_context_never_leaks_finding_identifier_or_asset(
        self, scenario_tenant, mock_claude_client
    ):
        tenant, scenario = scenario_tenant
        finding = self._ingest_finding_for_tenant_email(tenant, scenario)
        assert finding.identifier_plain == scenario["member_email"]  # sanity: real ingestion path

        conversation = Conversation.all_objects.create(tenant=tenant)
        Message.all_objects.create(
            tenant=tenant, conversation=conversation, role=Message.Role.USER, content="Bonjour"
        )

        services.generate_assistant_reply(conversation=conversation)

        call_kwargs = mock_claude_client.messages.create.call_args.kwargs
        payload = call_kwargs["system"] + str(call_kwargs["messages"])
        _assert_no_leak(payload, scenario)
        assert "SuperSecretRealValue123" not in payload

    def test_weather_enrichment_never_leaks_finding_identifier_or_asset(
        self, scenario_tenant, mock_claude_client
    ):
        from apps.notifications import services as notifications_services

        tenant, scenario = scenario_tenant
        self._ingest_finding_for_tenant_email(tenant, scenario)
        notifications_services.update_preferences(tenant, weather_enrichment_enabled=True)

        notifications_services.build_weather_context(tenant)

        call_kwargs = mock_claude_client.messages.create.call_args.kwargs
        payload = call_kwargs["system"] + str(call_kwargs["messages"])
        _assert_no_leak(payload, scenario)
        assert "SuperSecretRealValue123" not in payload

    def test_assistant_context_includes_pseudonymizable_breach_summary(
        self, scenario_tenant, mock_claude_client
    ):
        """Not just "no leak" — confirms the finding actually reaches the
        payload (as a placeholder), so the no-leak assertion above isn't
        trivially true because the data was silently dropped."""
        tenant, scenario = scenario_tenant
        self._ingest_finding_for_tenant_email(tenant, scenario)
        conversation = Conversation.all_objects.create(tenant=tenant)
        Message.all_objects.create(
            tenant=tenant, conversation=conversation, role=Message.Role.USER, content="Bonjour"
        )

        services.generate_assistant_reply(conversation=conversation)

        call_kwargs = mock_claude_client.messages.create.call_args.kwargs
        payload = call_kwargs["system"] + str(call_kwargs["messages"])
        assert "compromissions_ouvertes" in payload
        assert "{{EMAIL_1}}" in payload or "{{EMAIL_2}}" in payload or "{{MEMBER_1}}" in payload


class TestPseudonymizeTextOrdering:
    def test_longer_value_matched_before_a_shorter_substring(self):
        mapping = {"Acme Corp": "{{COMPANY}}", "Acme": "{{MEMBER_1}}"}
        result = services.pseudonymize_text("Bienvenue chez Acme Corp !", mapping)
        assert result == "Bienvenue chez {{COMPANY}} !"

    def test_special_regex_characters_are_escaped(self):
        mapping = {"A.B*C+D": "{{COMPANY}}"}
        result = services.pseudonymize_text("Contactez A.B*C+D pour plus d'infos.", mapping)
        assert result == "Contactez {{COMPANY}} pour plus d'infos."
        # A regex-unsafe value used unescaped would also match "AxBxCxD" —
        # confirms the real literal string, not a regex, drives the match.
        assert services.pseudonymize_text("AxBxCxD", mapping) == "AxBxCxD"


class TestPseudonymizeValueRecursion:
    def test_replaces_strings_nested_in_dicts_and_lists(self):
        mapping = {"Acme": "{{COMPANY}}"}
        value = {
            "name": "Acme",
            "notes": ["à propos d'Acme", {"detail": "Acme encore"}],
            "count": 3,
            "flag": None,
        }

        result = services.pseudonymize_value(value, mapping)

        assert result == {
            "name": "{{COMPANY}}",
            "notes": ["à propos d'{{COMPANY}}", {"detail": "{{COMPANY}} encore"}],
            "count": 3,
            "flag": None,
        }


class TestRehydrateText:
    def test_round_trip(self):
        mapping = {"Acme": "{{COMPANY}}", "alice@acme.fr": "{{EMAIL_1}}"}
        pseudo = services.pseudonymize_text("Acme confirme via alice@acme.fr.", mapping)
        assert services.rehydrate_text(pseudo, mapping) == "Acme confirme via alice@acme.fr."

    def test_empty_mapping_is_a_no_op(self):
        assert services.rehydrate_text("texte inchangé", {}) == "texte inchangé"


class TestMappingStorage:
    def test_store_and_load_round_trip(self, tenant):
        mapping = {"Acme": "{{COMPANY}}"}
        row = services.store_mapping(tenant, mapping)
        assert services.load_mapping(row) == mapping

    def test_expired_mapping_raises(self, tenant):
        row = services.store_mapping(tenant, {"Acme": "{{COMPANY}}"})
        row.expires_at = timezone.now() - timedelta(hours=1)
        row.save(update_fields=["expires_at"])

        with pytest.raises(services.MappingExpiredError):
            services.load_mapping(row)


class TestConversationMappingStability:
    def test_placeholder_stays_the_same_across_turns(self, tenant):
        conversation = Conversation.all_objects.create(tenant=tenant)
        first = services.get_or_create_conversation_mapping(conversation)
        conversation.refresh_from_db()
        second = services.get_or_create_conversation_mapping(conversation)

        assert first[tenant.name] == second[tenant.name] == "{{COMPANY}}"

    def test_extends_ttl_on_reuse(self, tenant):
        conversation = Conversation.all_objects.create(tenant=tenant)
        services.get_or_create_conversation_mapping(conversation)
        conversation.refresh_from_db()
        mapping_row = conversation.pseudonymization_mapping
        mapping_row.expires_at = timezone.now() + timedelta(minutes=1)
        mapping_row.save(update_fields=["expires_at"])

        services.get_or_create_conversation_mapping(conversation)

        mapping_row.refresh_from_db()
        assert mapping_row.expires_at > timezone.now() + timedelta(hours=1)
