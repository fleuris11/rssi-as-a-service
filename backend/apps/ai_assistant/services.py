"""Public interface of the ai_assistant app — the SINGLE entry point for
every AI interaction on the platform (CLAUDE.md architecture rule 3 / ADR-004
/ ADR-005): "aucun appel direct à l'API Anthropic ailleurs dans le code".

Pipeline for every use case, in order:
(a) build the minimal context needed (never raw PII by default) ;
(b) pseudonymize it (real values -> stable {{PLACEHOLDER}} tokens, mapping
    stored encrypted server-side, short TTL) ;
(c) call the Anthropic API, model routed by use case ;
(d) rehydrate the real values into the response ;
(e) log the call (tenant, use case, model, tokens, cost, duration).

Like apps.monitoring/apps.notifications, every function here is given an
already-resolved tenant/document/conversation and consistently uses
``all_objects`` with an explicit ``tenant=`` filter — Celery tasks have no
ambient request context.
"""

import json
import logging
import re
import time
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlparse

import anthropic
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.assessments import services as assessments_services
from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset
from apps.tenants import services as tenants_services

from . import prompts
from .models import (
    AIJob,
    AIUsageLog,
    AIUsageQuota,
    Conversation,
    GeneratedDocument,
    Message,
    PseudonymizationMapping,
)

logger = logging.getLogger(__name__)

ASSISTANT_HISTORY_WINDOW = 20


class AIError(Exception):
    """Base class for business-rule violations raised by this module."""


class AIDisabledError(AIError):
    pass


class QuotaExceededError(AIError):
    pass


class MappingExpiredError(AIError):
    pass


# --- Modèle / routage (ADR-004) -------------------------------------------
#
# Haiku par défaut (météo, assistant : synthèses/reformulations courtes,
# ancrées sur un contexte déjà calculé) ; Sonnet réservé à la génération
# documentaire longue (charte informatique) — cadrage §4.5/§8 (Green IT).
# Décision de routage pour l'assistant (nouveau cas d'usage, cf. ADR-004
# "à documenter dans le code du point d'entrée") : Haiku, revisable si la
# qualité perçue le justifie.

USE_CASE_MODELS = {
    AIUsageLog.UseCase.DOCUMENT_CHARTER: "claude-sonnet-5",
    AIUsageLog.UseCase.ASSISTANT_REPLY: "claude-haiku-4-5",
    AIUsageLog.UseCase.WEATHER_ENRICHMENT: "claude-haiku-4-5",
}
USE_CASE_MAX_TOKENS = {
    AIUsageLog.UseCase.DOCUMENT_CHARTER: 4000,
    AIUsageLog.UseCase.ASSISTANT_REPLY: 1024,
    AIUsageLog.UseCase.WEATHER_ENRICHMENT: 400,
}
# Tarifs Anthropic indicatifs (USD / million de tokens) au moment de
# l'implémentation — à réviser si les tarifs évoluent (cadrage §8 : suivi
# tokens/coût, pas une facturation exacte).
PRICING_USD_PER_MILLION_TOKENS = {
    "claude-haiku-4-5": {"input": Decimal("1.00"), "output": Decimal("5.00")},
    "claude-sonnet-5": {"input": Decimal("3.00"), "output": Decimal("15.00")},
}


def estimate_cost_usd(model: str, tokens_input: int, tokens_output: int) -> Decimal:
    pricing = PRICING_USD_PER_MILLION_TOKENS[model]
    million = Decimal(1_000_000)
    return (Decimal(tokens_input) / million * pricing["input"]) + (
        Decimal(tokens_output) / million * pricing["output"]
    )


# --- Activation IA (US-4.3) -------------------------------------------------


def ensure_ai_enabled(tenant) -> None:
    if not tenant.ai_enabled:
        raise AIDisabledError("L'IA est désactivée pour cette entreprise.")


# --- Quotas (US-4.3, cadrage §8) --------------------------------------------


def get_or_create_current_quota(tenant) -> AIUsageQuota:
    period = timezone.localdate().replace(day=1)
    quota, _created = AIUsageQuota.all_objects.get_or_create(
        tenant=tenant,
        period=period,
        defaults={"monthly_token_limit": settings.AI_DEFAULT_MONTHLY_TOKEN_LIMIT},
    )
    return quota


def ensure_quota_available(tenant) -> AIUsageQuota:
    quota = get_or_create_current_quota(tenant)
    if quota.remaining_tokens <= 0:
        raise QuotaExceededError(
            "Le quota mensuel de tokens IA de cette entreprise est épuisé. "
            "Il sera réinitialisé au début du mois prochain."
        )
    return quota


def get_quota_summary(tenant) -> dict:
    quota = get_or_create_current_quota(tenant)
    return {
        "period": quota.period,
        "tokens_used": quota.tokens_used,
        "monthly_token_limit": quota.monthly_token_limit,
        "remaining_tokens": quota.remaining_tokens,
    }


# --- Pseudonymisation (ADR-005) ---------------------------------------------


def _add_value(mapping: dict, counters: dict, value, kind: str) -> None:
    value = (value or "").strip()
    if not value or value in mapping:
        return
    if kind == "COMPANY":
        mapping[value] = "{{COMPANY}}"
        return
    counters[kind] += 1
    mapping[value] = f"{{{{{kind}_{counters[kind]}}}}}"


_PLACEHOLDER_INDEX_RE = re.compile(r"^\{\{([A-Z]+)_(\d+)\}\}$")


def _counters_from_mapping(mapping: dict) -> dict:
    counters = defaultdict(int)
    for placeholder in mapping.values():
        match = _PLACEHOLDER_INDEX_RE.match(placeholder)
        if match:
            kind, index = match.group(1), int(match.group(2))
            counters[kind] = max(counters[kind], index)
    return counters


def collect_sensitive_values(tenant, mapping: dict | None = None) -> dict:
    """Real value -> stable ``{{PLACEHOLDER}}`` token. Only ever built from
    identifying data (company name, member names/emails, monitored asset
    domains/URLs) — never from aggregated/statistical fields (sector,
    headcount, scores), which are not PII and are sent as-is.

    Passing an existing ``mapping`` extends it in place, keeping every
    already-assigned placeholder unchanged and only adding new values —
    this is what keeps a conversation's placeholders stable across turns
    (cadrage §4.5) even as new tenant data appears.
    """
    mapping = mapping if mapping is not None else {}
    counters = _counters_from_mapping(mapping)

    _add_value(mapping, counters, tenant.name, "COMPANY")
    for membership in tenants_services.list_members(tenant):
        _add_value(mapping, counters, membership.user.get_full_name(), "MEMBER")
        _add_value(mapping, counters, membership.user.email, "EMAIL")
    for asset in monitoring_services.list_assets(tenant):
        if asset.type == Asset.Type.WEBSITE:
            _add_value(mapping, counters, asset.value, "URL")
            hostname = urlparse(asset.value).hostname
            if hostname:
                _add_value(mapping, counters, hostname, "DOMAIN")
        else:
            _add_value(mapping, counters, asset.value, "DOMAIN")
    return mapping


def _build_pattern(mapping: dict) -> re.Pattern | None:
    if not mapping:
        return None
    ordered = sorted(mapping, key=len, reverse=True)
    return re.compile("|".join(re.escape(value) for value in ordered))


def pseudonymize_text(text: str, mapping: dict, pattern: re.Pattern | None = None) -> str:
    if not text:
        return text
    pattern = pattern if pattern is not None else _build_pattern(mapping)
    if pattern is None:
        return text
    return pattern.sub(lambda m: mapping[m.group(0)], text)


def pseudonymize_value(value, mapping: dict, pattern: re.Pattern | None = None):
    """Recursively pseudonymizes every string found in ``value`` (a dict,
    list, or plain string), for building the payload transmitted to the
    API — this is what the property test in tests/test_pseudonymization.py
    asserts leaks no real value."""
    pattern = pattern if pattern is not None else _build_pattern(mapping)
    if isinstance(value, str):
        return pseudonymize_text(value, mapping, pattern)
    if isinstance(value, dict):
        return {key: pseudonymize_value(v, mapping, pattern) for key, v in value.items()}
    if isinstance(value, list):
        return [pseudonymize_value(v, mapping, pattern) for v in value]
    return value


def rehydrate_text(text: str, mapping: dict) -> str:
    if not text:
        return text
    reverse = {placeholder: real for real, placeholder in mapping.items()}
    if not reverse:
        return text
    pattern = re.compile("|".join(re.escape(p) for p in sorted(reverse, key=len, reverse=True)))
    return pattern.sub(lambda m: reverse[m.group(0)], text)


def _fernet() -> Fernet:
    key = settings.AI_PSEUDONYMIZATION_KEY
    if not key:
        raise AIError(
            "AI_PSEUDONYMIZATION_KEY n'est pas configurée : impossible de chiffrer "
            "la table de correspondance de pseudonymisation."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def store_mapping(tenant, mapping: dict) -> PseudonymizationMapping:
    encrypted = _fernet().encrypt(json.dumps(mapping).encode("utf-8"))
    expires_at = timezone.now() + timedelta(hours=settings.AI_PSEUDONYMIZATION_TTL_HOURS)
    return PseudonymizationMapping.all_objects.create(
        tenant=tenant, encrypted_data=encrypted, expires_at=expires_at
    )


def load_mapping(mapping_row: PseudonymizationMapping) -> dict:
    if mapping_row.expires_at < timezone.now():
        raise MappingExpiredError("La correspondance de pseudonymisation a expiré.")
    try:
        decrypted = _fernet().decrypt(bytes(mapping_row.encrypted_data))
    except InvalidToken as exc:
        raise MappingExpiredError("La correspondance de pseudonymisation est illisible.") from exc
    return json.loads(decrypted.decode("utf-8"))


def _replace_mapping(mapping_row: PseudonymizationMapping, mapping: dict) -> None:
    mapping_row.encrypted_data = _fernet().encrypt(json.dumps(mapping).encode("utf-8"))
    mapping_row.expires_at = timezone.now() + timedelta(
        hours=settings.AI_PSEUDONYMIZATION_TTL_HOURS
    )
    mapping_row.save(update_fields=["encrypted_data", "expires_at"])


def get_or_create_conversation_mapping(conversation: Conversation) -> dict:
    """Stable placeholders across a whole conversation (cadrage §4.5):
    reuses and extends the conversation's existing mapping rather than
    generating a fresh one on every message."""
    tenant = conversation.tenant
    if conversation.pseudonymization_mapping_id:
        try:
            mapping = load_mapping(conversation.pseudonymization_mapping)
        except MappingExpiredError:
            mapping = {}
        mapping = collect_sensitive_values(tenant, mapping)
        _replace_mapping(conversation.pseudonymization_mapping, mapping)
        return mapping

    mapping = collect_sensitive_values(tenant)
    mapping_row = store_mapping(tenant, mapping)
    conversation.pseudonymization_mapping = mapping_row
    conversation.save(update_fields=["pseudonymization_mapping"])
    return mapping


# --- Appel API Claude (ADR-004) ---------------------------------------------


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def record_usage(
    *, tenant, use_case: str, model: str, tokens_input: int, tokens_output: int, duration_ms: int
) -> AIUsageLog:
    cost = estimate_cost_usd(model, tokens_input, tokens_output)
    log = AIUsageLog.all_objects.create(
        tenant=tenant,
        use_case=use_case,
        model=model,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cost_estimate_usd=cost,
        duration_ms=duration_ms,
    )
    quota = get_or_create_current_quota(tenant)
    AIUsageQuota.all_objects.filter(id=quota.id).update(
        tokens_used=F("tokens_used") + tokens_input + tokens_output
    )
    return log


def call_claude(*, tenant, use_case: str, system_prompt: str, messages: list[dict]) -> str:
    """The single call site for the Anthropic API on this platform
    (CLAUDE.md). Callers must have already checked ``ensure_ai_enabled`` and
    ``ensure_quota_available`` — this function always logs the call
    (cadrage §4.5/§8) regardless of outcome shape, then returns the
    response text."""
    model = USE_CASE_MODELS[use_case]
    max_tokens = USE_CASE_MAX_TOKENS[use_case]
    client = _get_client()

    started = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    record_usage(
        tenant=tenant,
        use_case=use_case,
        model=model,
        tokens_input=response.usage.input_tokens,
        tokens_output=response.usage.output_tokens,
        duration_ms=duration_ms,
    )
    return text


# --- Cas d'usage 1 : génération de la charte informatique (US-4.1) --------


def build_charter_context(tenant) -> dict:
    assessment = assessments_services.get_latest_completed_assessment(tenant)
    gaps = []
    global_score = None
    if assessment is not None:
        scores = assessments_services.compute_scores(assessment)
        global_score = scores["global"]
        measures = assessments_services.get_referential_measures(assessment.referential)
        values = assessments_services.get_answer_values(assessment)
        for measure in measures:
            if values.get(measure.id) in assessments_services.GAP_VALUES:
                gaps.append({"domaine": measure.domain.name, "mesure": measure.official_title})
    return {
        "raison_sociale": tenant.name,
        "secteur": tenant.sector or "non renseigné",
        "effectif": tenant.headcount,
        "score_global": global_score,
        "ecarts_identifies": gaps,
    }


def preview_charter_context(tenant) -> dict:
    """US-4.3 transparency: exactly the pseudonymized payload that would be
    sent, without persisting a mapping (read-only, no API call)."""
    context = build_charter_context(tenant)
    mapping = collect_sensitive_values(tenant)
    return pseudonymize_value(context, mapping)


def generate_charter_document(*, document: GeneratedDocument) -> GeneratedDocument:
    tenant = document.tenant
    context = build_charter_context(tenant)
    mapping = collect_sensitive_values(tenant)
    store_mapping(tenant, mapping)  # audit trail — this generation never reuses it
    pseudo_context = pseudonymize_value(context, mapping)

    text = call_claude(
        tenant=tenant,
        use_case=AIUsageLog.UseCase.DOCUMENT_CHARTER,
        system_prompt=prompts.IT_CHARTER_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": json.dumps(pseudo_context, ensure_ascii=False, indent=2)}
        ],
    )
    document.content_markdown = rehydrate_text(text, mapping)
    document.status = GeneratedDocument.Status.DRAFT
    document.save(update_fields=["content_markdown", "status", "updated_at"])
    return document


def list_documents(tenant):
    return GeneratedDocument.all_objects.filter(tenant=tenant).order_by("-version", "-created_at")


def get_document(*, tenant, document_id):
    return GeneratedDocument.all_objects.filter(tenant=tenant, id=document_id).first()


def _next_document_version(tenant, document_type: str) -> int:
    latest = (
        GeneratedDocument.all_objects.filter(tenant=tenant, type=document_type)
        .order_by("-version")
        .first()
    )
    return (latest.version + 1) if latest else 1


def create_document_job(*, tenant, user, document_type: str) -> tuple[GeneratedDocument, AIJob]:
    ensure_ai_enabled(tenant)
    ensure_quota_available(tenant)
    document = GeneratedDocument.all_objects.create(
        tenant=tenant,
        type=document_type,
        version=_next_document_version(tenant, document_type),
        status=GeneratedDocument.Status.GENERATING,
        created_by=user,
    )
    job = AIJob.all_objects.create(
        tenant=tenant,
        use_case=AIJob.UseCase.DOCUMENT_CHARTER,
        status=AIJob.Status.PENDING,
        result_ref={"document_id": document.id},
        created_by=user,
    )
    return document, job


def update_document_content(
    document: GeneratedDocument, content_markdown: str
) -> GeneratedDocument:
    if document.status == GeneratedDocument.Status.VALIDATED:
        raise AIError("Ce document est déjà validé et ne peut plus être modifié.")
    document.content_markdown = content_markdown
    document.save(update_fields=["content_markdown", "updated_at"])
    return document


def validate_document(document: GeneratedDocument) -> GeneratedDocument:
    document.status = GeneratedDocument.Status.VALIDATED
    document.validated_at = timezone.now()
    document.save(update_fields=["status", "validated_at", "updated_at"])
    return document


_PDF_STYLESHEET = """
@page { size: A4; margin: 2.5cm 2cm; }
body {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 11pt;
  color: #1e293b;
  line-height: 1.5;
}
h1, h2, h3 { color: #0f172a; }
h1 { font-size: 20pt; margin-bottom: 0.3em; }
h2 {
  font-size: 14pt;
  margin-top: 1.4em;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 0.2em;
}
code { background: #f1f5f9; padding: 0.1em 0.3em; border-radius: 3px; }
"""


def render_document_pdf(document: GeneratedDocument) -> bytes:
    """PDF export (US-4.1 reste-à-faire de Phase 4, traité en Phase 5) via
    WeasyPrint : le markdown validé est converti en HTML minimal puis rendu
    en PDF. Système de rendu (Pango/Cairo) installé au niveau du Dockerfile
    et de la CI — voir docs/adr/012-export-pdf-weasyprint.md."""
    import markdown as markdown_lib
    import weasyprint

    body_html = markdown_lib.markdown(document.content_markdown, extensions=["extra", "sane_lists"])
    full_html = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<style>{_PDF_STYLESHEET}</style></head><body>{body_html}</body></html>"
    )
    return weasyprint.HTML(string=full_html).write_pdf()


# --- Cas d'usage 2 : assistant contextuel (US-4.2) --------------------------


def build_assistant_context(tenant) -> dict:
    assessment = assessments_services.get_latest_completed_assessment(tenant)
    scores = assessments_services.compute_scores(assessment) if assessment is not None else None
    open_alerts = monitoring_services.list_open_alerts(tenant)
    return {
        "raison_sociale": tenant.name,
        "secteur": tenant.sector or "non renseigné",
        "effectif": tenant.headcount,
        "score_global": scores["global"] if scores else None,
        "scores_par_domaine": scores["by_domain"] if scores else [],
        "alertes_ouvertes": [
            {
                "actif": alert.asset.value,
                "type": alert.get_alert_type_display(),
                "gravite": alert.get_severity_display(),
            }
            for alert in open_alerts
        ],
    }


def preview_assistant_context(tenant) -> dict:
    context = build_assistant_context(tenant)
    mapping = collect_sensitive_values(tenant)
    return pseudonymize_value(context, mapping)


def list_conversations(tenant):
    return Conversation.all_objects.filter(tenant=tenant).order_by("-updated_at")


def get_conversation(*, tenant, conversation_id):
    return Conversation.all_objects.filter(tenant=tenant, id=conversation_id).first()


def create_conversation(*, tenant, user) -> Conversation:
    ensure_ai_enabled(tenant)
    return Conversation.all_objects.create(tenant=tenant, created_by=user)


def list_messages(conversation: Conversation):
    return Message.all_objects.filter(
        tenant=conversation.tenant, conversation=conversation
    ).order_by("created_at")


def create_assistant_job(
    *, tenant, user, conversation: Conversation, text: str
) -> tuple[Message, AIJob]:
    ensure_ai_enabled(tenant)
    ensure_quota_available(tenant)
    user_message = Message.all_objects.create(
        tenant=tenant, conversation=conversation, role=Message.Role.USER, content=text
    )
    job = AIJob.all_objects.create(
        tenant=tenant,
        use_case=AIJob.UseCase.ASSISTANT_REPLY,
        status=AIJob.Status.PENDING,
        result_ref={"conversation_id": conversation.id, "user_message_id": user_message.id},
        created_by=user,
    )
    return user_message, job


def generate_assistant_reply(*, conversation: Conversation) -> Message:
    tenant = conversation.tenant
    mapping = get_or_create_conversation_mapping(conversation)
    pattern = _build_pattern(mapping)
    context = pseudonymize_value(build_assistant_context(tenant), mapping, pattern)
    system_prompt = (
        f"{prompts.ASSISTANT_SYSTEM_PROMPT}\n\n"
        "## Contexte de conformité de l'entreprise (pseudonymisé, JSON)\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )

    history = list(
        Message.all_objects.filter(tenant=tenant, conversation=conversation).order_by(
            "-created_at"
        )[:ASSISTANT_HISTORY_WINDOW]
    )
    history.reverse()
    api_messages = [
        {
            "role": "user" if m.role == Message.Role.USER else "assistant",
            "content": pseudonymize_text(m.content, mapping, pattern),
        }
        for m in history
    ]

    text = call_claude(
        tenant=tenant,
        use_case=AIUsageLog.UseCase.ASSISTANT_REPLY,
        system_prompt=system_prompt,
        messages=api_messages,
    )
    reply = Message.all_objects.create(
        tenant=tenant,
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content=rehydrate_text(text, mapping),
    )
    Conversation.all_objects.filter(id=conversation.id).update(updated_at=timezone.now())
    return reply


# --- Jobs (pattern asynchrone, CLAUDE.md règle n°3) -------------------------


def get_job(*, tenant, job_id):
    return AIJob.all_objects.filter(tenant=tenant, id=job_id).first()


def mark_job_running(job: AIJob) -> AIJob:
    job.status = AIJob.Status.RUNNING
    job.save(update_fields=["status"])
    return job


def mark_job_done(job: AIJob, result_ref: dict | None = None) -> AIJob:
    job.status = AIJob.Status.DONE
    if result_ref:
        job.result_ref = {**job.result_ref, **result_ref}
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "result_ref", "finished_at"])
    return job


def mark_job_failed(job: AIJob, error_message: str) -> AIJob:
    job.status = AIJob.Status.FAILED
    job.error_message = error_message
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error_message", "finished_at"])
    return job


# --- Cas d'usage 3 : météo enrichie (optionnelle, US-5.5 note IA) ---------


def enrich_weather_summary(*, tenant, deterministic_context: dict) -> str | None:
    """Best-effort Haiku reformulation of the deterministic weather digest
    built by apps.notifications. Returns ``None`` on ANY failure — disabled,
    no quota, network/API error — so the caller always falls back to the
    deterministic template (CLAUDE.md: "le template reste le fallback ...
    la météo part toujours")."""
    try:
        ensure_ai_enabled(tenant)
        ensure_quota_available(tenant)
        mapping = collect_sensitive_values(tenant)
        pattern = _build_pattern(mapping)
        pseudo_context = pseudonymize_value(deterministic_context, mapping, pattern)
        text = call_claude(
            tenant=tenant,
            use_case=AIUsageLog.UseCase.WEATHER_ENRICHMENT,
            system_prompt=prompts.WEATHER_ENRICHMENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(pseudo_context, ensure_ascii=False)}],
        )
        return rehydrate_text(text, mapping)
    except Exception:  # noqa: BLE001 - deliberately broad: la météo part toujours
        logger.warning(
            "Échec de l'enrichissement IA de la météo pour le tenant %s", tenant.id, exc_info=True
        )
        return None
