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
        EXPOSURE_SYNTHESIS = "exposure_synthesis", "Synthèse d'exposition"

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
        EXPOSURE_SYNTHESIS = "exposure_synthesis", "Synthèse d'exposition"

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
    """La bibliothèque documentaire du client — versionnée, brouillon/validé,
    en Markdown. Chaque (re)génération crée une ligne avec un ``version``
    incrémenté pour son (tenant, type) ; l'édition sur place garde la version.

    V2-5 : le modèle portait un seul type, la charte informatique rédigée par
    l'IA. Il en porte désormais sept, dont six **composés** — assemblés par du
    code à partir des données de la plateforme, sans appel d'IA (ADR-032).
    ``source`` porte cette distinction, parce qu'elle change ce qu'on promet
    au lecteur : un document composé est reproductible et se relit tel quel,
    un document rédigé demande une relecture attentive.
    """

    class DocumentType(models.TextChoices):
        SECURITY_POLICY = "security_policy", "Politique de sécurité du SI"
        IT_CHARTER = "it_charter", "Charte informatique"
        INCIDENT_PROCEDURE = "incident_procedure", "Procédure de gestion des incidents"
        INCIDENT_REGISTER = "incident_register", "Registre des incidents"
        CONTINUITY_PLAN = "continuity_plan", "Plan de continuité simplifié"
        AWARENESS_SHEET = "awareness_sheet", "Fiche de sensibilisation"
        COMMITTEE_REPORT = "committee_report", "Rapport de comité de sécurité"

    class Source(models.TextChoices):
        COMPOSED = "composed", "Composé à partir de vos données"
        AI = "ai", "Rédigé par l'IA, à relire"

    class Status(models.TextChoices):
        GENERATING = "generating", "Génération en cours"
        DRAFT = "draft", "Brouillon"
        VALIDATED = "validated", "Validé"
        FAILED = "failed", "Échec de génération"

    type = models.CharField(max_length=30, choices=DocumentType.choices)
    # Défaut ``AI`` : c'est ce qu'étaient toutes les lignes existantes à la
    # migration, et un défaut qui ment sur l'historique serait pire que pas
    # de champ du tout.
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.AI)
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
