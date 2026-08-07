"""Data models for the threat_intelligence app (Phase 7, ADR-013/014).

Every model is tenant-scoped (``TenantScopedModel``) except the fact that
the *ceiling* they operate under (query quota, monitored-asset pool) is a
platform-wide, licence-level constraint, not a per-tenant one — see
``quota.py``/``pool.py`` in services.py for where that global bookkeeping
actually lives. Like apps.monitoring/apps.ai_assistant, FKs to another
app's model (``monitoring.Asset``) are imported directly — established
precedent in this codebase (apps.ai_assistant.models does the same for
FK/type-check purposes), cross-app *business logic* still goes through
that app's services.py.
"""

from django.conf import settings
from django.db import models

from apps.monitoring.models import Asset
from apps.tenants.models import TenantScopedModel


class BreachFinding(TenantScopedModel):
    """One normalized compromise finding — never stores a secret in clear
    (ADR-014): ``secret_masked``/``secret_seen`` replace whatever password,
    token or cookie the provider returned."""

    class SourceEndpoint(models.TextChoices):
        STEALER = "stealer", "Logs de malware voleur d'identifiants"
        COMBO = "combo", "Liste combo (identifiant + mot de passe)"
        CREDS = "creds", "Identifiants exposés"
        SESSIONS = "sessions", "Sessions / cookies compromis"
        NHI = "nhi", "Identité non-humaine (clé de service, token API)"
        DARKWEB = "darkweb", "Mention dark web"
        DOCS = "docs", "Document fuité"
        ASM = "asm", "Surface d'attaque"
        RADAR = "radar", "Radar (mentions publiques)"
        WEBHOOK = "webhook", "Notification temps réel (webhook)"

    class Severity(models.TextChoices):
        # Mapping imposé par le prompt Phase 7 : stealer/sessions/nhi/darkweb
        # = critique ; creds/combo/docs = élevé ; radar/asm-phishing =
        # attention. Voir threat_intelligence.providers.breachsense.normalizer.
        CRITICAL = "critical", "Critique"
        HIGH = "high", "Élevée"
        ATTENTION = "attention", "Attention"

    class Status(models.TextChoices):
        OPEN = "open", "Ouvert"
        TREATED = "treated", "Traité"
        IGNORED = "ignored", "Ignoré"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="breach_findings")
    source_endpoint = models.CharField(max_length=20, choices=SourceEndpoint.choices)
    finding_type = models.CharField(max_length=60)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)

    # ADR-014 §4 : en clair UNIQUEMENT si l'identifiant est l'email pro d'un
    # membre du tenant ; sinon la forme masquée est seule renseignée.
    identifier_plain = models.CharField(max_length=255, blank=True)
    identifier_masked = models.CharField(max_length=255, blank=True)

    # ADR-014 §1/§2 : jamais le secret en clair — uniquement sa forme
    # masquée non réversible, et un indicateur qu'un secret existait.
    secret_masked = models.CharField(max_length=32, blank=True)
    secret_seen = models.BooleanField(default=False)

    breach_date = models.DateField(null=True, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)

    # Payload déjà masqué au moment de la normalisation (ADR-014 §2) — champs
    # non-sensibles uniquement (endpoint d'origine, métadonnées).
    raw_data = models.JSONField(default=dict, blank=True)

    # Dédoublonnage (scan répété, webhook redélivré) — voir services.py.
    dedup_hash = models.CharField(max_length=64)

    alert = models.ForeignKey(
        "monitoring.Alert", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    treated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    treated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-detected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "dedup_hash"], name="unique_breach_finding_per_tenant_dedup"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "-detected_at"]),
            models.Index(fields=["asset", "-detected_at"]),
        ]

    def __str__(self):
        return f"{self.asset_id} — {self.source_endpoint} — {self.severity} ({self.status})"


class MonitoredAsset(TenantScopedModel):
    """One occupied slot in the provider's real-time webhook monitoring
    pool (15 slots on the Essentials tier — a platform-wide, not
    per-tenant, ceiling; see threat_intelligence.services.pool). Distinct
    from — and always backed by — a ``monitoring.Asset``: only assets the
    tenant has already declared for passive checks may be registered for
    breach monitoring (extends ADR-010's "actif déclaré uniquement" to
    CTI)."""

    asset = models.OneToOneField(
        Asset, on_delete=models.CASCADE, related_name="threat_intel_monitored_asset"
    )
    provider = models.CharField(max_length=30, default="breachsense")
    provider_ref = models.CharField(max_length=255)
    # Vocabulaire du fournisseur externe (ex. "domain") — délibérément une
    # chaîne libre plutôt qu'un TextChoices : c'est Breachsense qui définit
    # ces valeurs, pas la plateforme (les deux types d'actifs monitoring
    # actuels, website et email_domain, sont tous deux des domaines côté
    # Breachsense — voir threat_intelligence.services.register_monitored_asset).
    provider_asset_type = models.CharField(max_length=20, default="domain")
    registered_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_ref"], name="unique_provider_ref_per_provider"
            ),
        ]

    def __str__(self):
        return f"{self.provider} — {self.asset_id} ({'actif' if self.is_active else 'inactif'})"


class BreachIntelligenceUsage(TenantScopedModel):
    """Audit/attribution log: which tenant's scan consumed how much of the
    platform-wide "query" budget, and what the provider reported as
    remaining right after (QuotaManager's cache is seeded from this, not
    the other way round — see services.py)."""

    class TriggeredBy(models.TextChoices):
        INITIAL = "initial", "Scan initial (déclaration d'actif)"
        MANUAL = "manual", "Scan manuel"

    endpoint = models.CharField(max_length=20, blank=True)
    requests_consumed = models.PositiveIntegerField(default=0)
    remaining_after = models.IntegerField(null=True, blank=True)
    triggered_by = models.CharField(max_length=10, choices=TriggeredBy.choices)
    findings_created = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant_id} — {self.triggered_by} — {self.requests_consumed} req"


class BreachScanJob(TenantScopedModel):
    """Async job pattern reused from ADR-011 (apps.ai_assistant.AIJob):
    POST creates the job, GET polls status/result. Always executed via
    Celery, queue "monitoring" (ADR-013: CTI is a monitoring sub-domain,
    not an AI one)."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        RUNNING = "running", "En cours"
        DONE = "done", "Terminé"
        FAILED = "failed", "Échec"

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, null=True, blank=True, related_name="breach_scan_jobs"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    triggered_by = models.CharField(
        max_length=10, choices=BreachIntelligenceUsage.TriggeredBy.choices
    )
    result_ref = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.status} — {self.tenant_id} ({self.triggered_by})"
