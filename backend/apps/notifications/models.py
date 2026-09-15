from datetime import time

from django.conf import settings
from django.db import models

from apps.tenants.models import Tenant, TenantScopedModel


class NotificationPreferences(TenantScopedModel):
    """One row per tenant (cadrage §4.6: Tenant 1—1 NotificationPreferences)."""

    weather_enabled = models.BooleanField(default=True)
    # Interpreted in settings.TIME_ZONE (Europe/Paris) — no per-tenant
    # timezone support yet, documented simplification for the MVP.
    weather_time = models.TimeField(default=time(8, 0))
    realtime_alerts_enabled = models.BooleanField(default=True)
    # Phase 4 (cas d'usage 3, cadrage US-5.5 note IA) : reformulation du
    # résumé météo par Haiku via le pipeline de pseudonymisation. Optionnelle
    # par tenant ; le template déterministe reste le fallback (voir
    # apps.notifications.services.build_weather_context) si désactivée, si
    # ai_enabled=false sur le tenant, si le quota est dépassé ou si l'appel
    # échoue — la météo part toujours.
    weather_enrichment_enabled = models.BooleanField(default=False)
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
        # Phase 8A : signal d'exposition publique (radar/dark web) — un
        # canal distinct de REALTIME_ALERT parce que le message dit
        # explicitement l'inverse ("rien n'a encore fuité"), et qu'on doit
        # pouvoir les distinguer dans le journal d'envoi.
        PRE_INCIDENT_SIGNAL = "pre_incident", "Signal avant-coureur"

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


class Notification(models.Model):
    """Une notification DANS l'application (lot C, point 20 ; ADR-037).

    **Pas un ``TenantScopedModel``, et c'est une décision.** Une notification
    appartient à une PERSONNE : celles de l'exploitant ne concernent aucun
    client en particulier, et quelqu'un qui suit trois entreprises lit ses
    notifications dans une seule cloche. ``tenant`` dit de quel client il
    s'agit quand il y en a un ; la lecture est cloisonnée par destinataire,
    puis par appartenance (``inbox.visible_for``).

    On passe par ``apps.notifications.inbox``, jamais par ce modèle.
    """

    class Kind(models.TextChoices):
        # Côté exploitant.
        ACCESS_REQUEST_NEW = "access_request_new", "Nouvelle demande d'un client"
        WATCHED_ACCOUNT_DECLARED = "watched_account_declared", "Compte désigné déclaré"
        # Côté client.
        ACCESS_REQUEST_UPDATED = "access_request_updated", "Suivi d'une demande"
        WATCHED_FINDINGS_NEW = "watched_findings_new", "Nouvelles fuites sur un compte surveillé"
        COMMITTEE_REPORT_READY = "committee_report_ready", "Rapport de comité disponible"
        WATCH_UPDATE_PUBLISHED = "watch_update_published", "Publication de veille retenue"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    kind = models.CharField(max_length=40, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    #: Une route de l'application (« /mes-demandes »), jamais une URL externe.
    link = models.CharField(max_length=200, blank=True)
    #: Vide = pas d'idempotence. Sinon, unique par destinataire.
    dedupe_key = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["recipient", "read_at"], name="notif_destinataire_lu"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "dedupe_key"],
                condition=~models.Q(dedupe_key=""),
                name="unique_notification_dedupe_par_destinataire",
            ),
        ]

    def __str__(self):
        return f"{self.kind} → {self.recipient_id}"
