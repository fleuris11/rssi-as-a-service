from django.conf import settings
from django.db import models

from apps.tenants.models import TenantScopedModel


class AIUsageQuota(TenantScopedModel):
    """One row per (tenant, calendar month) — monthly token quota (cadrage
    §4.5/§8, Green IT), checked before every AI call and visible to the
    tenant. ``period`` is always the first day of the month."""

    period = models.DateField()
    tokens_used = models.PositiveIntegerField(default=0)
    monthly_token_limit = models.PositiveIntegerField(
        default=settings.AI_DEFAULT_MONTHLY_TOKEN_LIMIT
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "period"], name="unique_quota_per_tenant_period"
            ),
        ]
        ordering = ["-period"]

    def __str__(self):
        return (
            f"{self.tenant_id} — {self.period:%Y-%m} — "
            f"{self.tokens_used}/{self.monthly_token_limit}"
        )

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.monthly_token_limit - self.tokens_used)


class AIUsageLog(TenantScopedModel):
    """One row per Claude API call — tenant, use case, model, tokens,
    estimated cost, duration (CLAUDE.md pipeline step (e)). Never contains
    PII: only aggregate counts and the (already pseudonymized) use case."""

    class UseCase(models.TextChoices):
        DOCUMENT_CHARTER = "document_charter", "Génération de charte informatique"
        ASSISTANT_REPLY = "assistant_reply", "Réponse de l'assistant"
        WEATHER_ENRICHMENT = "weather_enrichment", "Météo cyber enrichie"

    use_case = models.CharField(max_length=30, choices=UseCase.choices)
    model = models.CharField(max_length=60)
    tokens_input = models.PositiveIntegerField()
    tokens_output = models.PositiveIntegerField()
    cost_estimate_usd = models.DecimalField(max_digits=10, decimal_places=6)
    duration_ms = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "use_case", "-created_at"])]

    def __str__(self):
        return (
            f"{self.tenant_id} — {self.use_case} — {self.model} ({self.created_at:%Y-%m-%d %H:%M})"
        )


class PseudonymizationMapping(TenantScopedModel):
    """Encrypted (Fernet) placeholder<->real-value correspondence table
    (ADR-005). Short TTL, server-side only, never transmitted to the AI
    provider. Extended on reuse (``services.touch_mapping``) so a
    conversation's placeholders stay stable across turns."""

    encrypted_data = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Correspondance {self.tenant_id} (expire {self.expires_at:%Y-%m-%d %H:%M})"


class AIJob(TenantScopedModel):
    """Job pattern (CLAUDE.md architecture rule 3): POST creates the job,
    GET polls status/result. Always executed via Celery (queue ``ai``),
    never in the HTTP request/response cycle.

    ``result_ref`` is an opaque pointer interpreted by the view/task for
    this use case (e.g. ``{"document_id": 5}`` or ``{"conversation_id": 9,
    "message_id": 12}``) — kept generic rather than a set of nullable FKs,
    since each use case only ever populates one shape.
    """

    class UseCase(models.TextChoices):
        DOCUMENT_CHARTER = "document_charter", "Génération de charte informatique"
        ASSISTANT_REPLY = "assistant_reply", "Réponse de l'assistant"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        RUNNING = "running", "En cours"
        DONE = "done", "Terminé"
        FAILED = "failed", "Échec"

    use_case = models.CharField(max_length=30, choices=UseCase.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    result_ref = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.use_case} — {self.status} ({self.tenant_id})"


class GeneratedDocument(TenantScopedModel):
    """US-4.1: charte informatique — versioned, brouillon/validé, markdown.
    Each (re)generation creates a new row with an incremented ``version``
    for its (tenant, type); editing in place keeps the same version."""

    class DocumentType(models.TextChoices):
        IT_CHARTER = "it_charter", "Charte informatique"

    class Status(models.TextChoices):
        GENERATING = "generating", "Génération en cours"
        DRAFT = "draft", "Brouillon"
        VALIDATED = "validated", "Validé"
        FAILED = "failed", "Échec de génération"

    type = models.CharField(max_length=30, choices=DocumentType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.GENERATING)
    version = models.PositiveIntegerField(default=1)
    content_markdown = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-version", "-created_at"]

    def __str__(self):
        return f"{self.get_type_display()} v{self.version} — {self.status} ({self.tenant_id})"


class Conversation(TenantScopedModel):
    """US-4.2: assistant contextuel. One pseudonymization mapping per
    conversation so placeholders stay stable across the whole exchange
    (cadrage §4.5: "table de correspondance ... placeholders stables")."""

    pseudonymization_mapping = models.ForeignKey(
        PseudonymizationMapping, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation {self.id} ({self.tenant_id})"


class Message(TenantScopedModel):
    class Role(models.TextChoices):
        USER = "user", "Dirigeant"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role} — {self.conversation_id}"
