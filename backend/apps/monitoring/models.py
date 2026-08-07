from django.conf import settings
from django.db import models

from apps.tenants.models import TenantScopedModel


class Asset(TenantScopedModel):
    """Something a tenant has declared and attested ownership of — checks
    only ever run against assets that exist here (CLAUDE.md: "un actif
    n'est vérifié que s'il est déclaré par le tenant")."""

    class Type(models.TextChoices):
        WEBSITE = "website", "Site web"
        EMAIL_DOMAIN = "email_domain", "Domaine email"

    type = models.CharField(max_length=20, choices=Type.choices)
    # WEBSITE: a full https:// URL. EMAIL_DOMAIN: a bare domain name.
    value = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    # Required True at creation (US-5.1: "preuve de légitimité") — enforced
    # in the serializer, not just defaulted here.
    ownership_confirmed = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "type", "value"], name="unique_asset_per_tenant"
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_type_display()} — {self.value}"


class CheckResult(TenantScopedModel):
    """One timestamped observation. Status is a shared tri-state across
    every check type — deliberately: it's what the ☀️/⚠️/🔴 weather email
    (apps.notifications) reads directly, no per-check-type translation."""

    class CheckType(models.TextChoices):
        HTTP_UPTIME = "http_uptime", "Disponibilité HTTP"
        SSL_CERTIFICATE = "ssl_certificate", "Certificat SSL"
        SECURITY_HEADERS = "security_headers", "En-têtes de sécurité"
        EMAIL_DNS = "email_dns", "Configuration email (SPF/DMARC)"

    class Status(models.TextChoices):
        OK = "ok", "OK"
        WARNING = "warning", "Avertissement"
        CRITICAL = "critical", "Critique"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="check_results")
    check_type = models.CharField(max_length=20, choices=CheckType.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    details = models.JSONField(default=dict, blank=True)
    latency_ms = models.FloatField(null=True, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["asset", "check_type", "-checked_at"]),
        ]

    def __str__(self):
        return f"{self.asset_id} — {self.check_type} — {self.status}"


class Alert(TenantScopedModel):
    class AlertType(models.TextChoices):
        DOWN = "down", "Site indisponible"
        SSL_EXPIRING = "ssl_expiring", "Certificat SSL bientôt expiré"
        SECURITY_HEADERS = "security_headers", "En-têtes de sécurité manquants"
        EMAIL_MISCONFIGURED = "email_misconfigured", "Configuration email incomplète"
        # Phase 7 (ADR-013) : ouverte par apps.threat_intelligence via
        # services.open_or_update_alert, jamais par ce module lui-même —
        # apps.monitoring reste ignorant de threat_intelligence.
        BREACH_COMPROMISE = "breach_compromise", "Compromission détectée"

    class Severity(models.TextChoices):
        WARNING = "warning", "Avertissement"
        CRITICAL = "critical", "Critique"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="alerts")
    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    is_open = models.BooleanField(default=True)
    details = models.JSONField(default=dict, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            # "pas de doublon d'alerte ouverte" enforced at the DB level
            # (partial unique index), not just in the service layer.
            models.UniqueConstraint(
                fields=["asset", "alert_type"],
                condition=models.Q(is_open=True),
                name="unique_open_alert_per_asset_type",
            ),
        ]

    def __str__(self):
        state = "ouverte" if self.is_open else "résolue"
        return f"{self.asset_id} — {self.alert_type} ({state})"
