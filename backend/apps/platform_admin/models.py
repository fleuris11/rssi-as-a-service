"""Traçabilité des actions d'administration plateforme (Phase 10).

Principe : **les administrateurs plateforme ne sont pas au-dessus de l'audit.**
Ils disposent des droits les plus étendus de la plateforme (suspendre un
client, changer son offre, modifier le catalogue) ; ce sont précisément les
actions qu'il faut pouvoir reconstituer après coup.

Complémentaire de ``SecretRevealAudit`` (ADR-014) sans le remplacer : celui-ci
trace l'accès à une donnée d'un tenant, celui-là trace un acte de gestion. Le
journal consolidé du back-office affiche les deux.
"""

from django.conf import settings
from django.db import models

from apps.tenants.models import Tenant


class AdminAuditLog(models.Model):
    class Action(models.TextChoices):
        SUBSCRIPTION_ACTIVATED = "subscription_activated", "Abonnement activé"
        SUBSCRIPTION_SUSPENDED = "subscription_suspended", "Abonnement suspendu"
        SUBSCRIPTION_CANCELLED = "subscription_cancelled", "Abonnement résilié"
        PLAN_CHANGED = "plan_changed", "Offre modifiée"
        TRIAL_STARTED = "trial_started", "Essai ouvert"
        PAYMENT_RECORDED = "payment_recorded", "Paiement enregistré"
        PLAN_CREATED = "plan_created", "Offre créée"
        PLAN_UPDATED = "plan_updated", "Offre mise à jour"
        PLAN_PUBLISHED = "plan_published", "Offre publiée"
        PLAN_RETIRED = "plan_retired", "Offre retirée"
        DEMO_REQUEST_UPDATED = "demo_request_updated", "Demande de démonstration traitée"
        TENANT_CREATED = "tenant_created", "Entreprise créée"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    action = models.CharField(max_length=40, choices=Action.choices)
    # Nullable : une action peut porter sur le catalogue et non sur un client.
    tenant = models.ForeignKey(
        Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # Ce sur quoi on a agi, en clair : un identifiant seul serait illisible
    # une fois l'objet supprimé.
    target = models.CharField(max_length=200, blank=True)
    detail = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"]), models.Index(fields=["action"])]

    def __str__(self):
        return f"{self.get_action_display()} — {self.target or '—'}"
