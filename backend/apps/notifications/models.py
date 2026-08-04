from datetime import time

from django.db import models

from apps.tenants.models import TenantScopedModel


class NotificationPreferences(TenantScopedModel):
    """One row per tenant (cadrage §4.6: Tenant 1—1 NotificationPreferences)."""

    weather_enabled = models.BooleanField(default=True)
    # Interpreted in settings.TIME_ZONE (Europe/Paris) — no per-tenant
    # timezone support yet, documented simplification for the MVP.
    weather_time = models.TimeField(default=time(8, 0))
    realtime_alerts_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="unique_preferences_per_tenant"),
        ]

    def __str__(self):
        return f"Préférences — {self.tenant_id}"


class EmailLog(TenantScopedModel):
    """Sent-email audit trail — also what makes daily weather sending
    idempotent (don't send twice for the same tenant on the same day even
    if the dispatch task is redelivered near the schedule boundary)."""

    class Kind(models.TextChoices):
        WEATHER = "weather", "Météo cyber"
        REALTIME_ALERT = "realtime_alert", "Alerte temps réel"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    sent_at = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["tenant", "kind", "sent_at"]),
        ]

    def __str__(self):
        return f"{self.kind} → {self.recipient} ({self.sent_at:%Y-%m-%d %H:%M})"
