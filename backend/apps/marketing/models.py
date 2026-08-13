"""Site vitrine public — demandes de démonstration.

Délibérément **hors du périmètre multi-tenant** : une demande de démonstration
émane d'un prospect qui n'a, par définition, pas encore de tenant. Ce modèle
n'hérite donc pas de ``TenantScopedModel`` et n'a pas de ``tenant_id`` — c'est
l'une des rares tables métier dans ce cas, et c'est voulu : lui coller un
tenant obligerait à en inventer un, ou à ouvrir une brèche dans le manager
fail-closed pour l'écrire. La contrepartie est que l'accès en lecture est
réservé au back-office plateforme (``IsAdminUser``), jamais exposé à un tenant.
"""

from django.db import models


class DemoRequest(models.Model):
    """Une demande de démonstration soumise depuis le site public.

    Aucune donnée sensible au sens d'ADR-014 : ce sont des coordonnées
    professionnelles fournies volontairement par le prospect. Elles restent
    néanmoins des données personnelles (RGPD) — d'où la durée de conservation
    documentée dans la politique de confidentialité et le champ ``status``,
    qui permet de clore une demande sans la supprimer.
    """

    class CompanySize(models.TextChoices):
        MICRO = "1-9", "1 à 9 personnes"
        SMALL = "10-49", "10 à 49 personnes"
        MEDIUM = "50-249", "50 à 249 personnes"
        LARGE = "250+", "250 personnes et plus"

    class Slot(models.TextChoices):
        MORNING = "morning", "Plutôt le matin"
        AFTERNOON = "afternoon", "Plutôt l'après-midi"
        ANY = "any", "Peu importe"

    class Status(models.TextChoices):
        NEW = "new", "Nouvelle"
        CONTACTED = "contacted", "Contactée"
        SCHEDULED = "scheduled", "Démonstration planifiée"
        CLOSED = "closed", "Close"

    full_name = models.CharField(max_length=120)
    company = models.CharField(max_length=160)
    role = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    company_size = models.CharField(max_length=10, choices=CompanySize.choices, blank=True)
    preferred_slot = models.CharField(max_length=10, choices=Slot.choices, blank=True)
    message = models.TextField(blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    # Contexte de soumission : utile pour distinguer une vague de spam d'un
    # afflux réel. L'IP est une donnée personnelle — conservée pour la seule
    # finalité anti-abus, et couverte par la même durée de conservation.
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"{self.company} — {self.full_name} ({self.get_status_display()})"
