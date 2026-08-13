"""Offres, abonnements, paiements (Phase 10).

Découpage volontaire avec ``apps.platform_admin`` : ici vit le **modèle
commercial** (ce qu'on vend, à qui, avec quels droits) ; là-bas vivent les
**vues d'administration** qui le pilotent. Un modèle de domaine ne dépend pas
de son back-office.

``Plan`` et ``Subscription`` ne sont PAS tenant-scopés au sens de
``TenantScopedModel`` : un plan est un objet de catalogue commun à toute la
plateforme, et un abonnement se lit depuis l'administration (donc hors
contexte de tenant résolu) autant que depuis l'espace client. La relation au
tenant est portée par une clé étrangère explicite et unique.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenants.models import Tenant

from . import features as feature_registry


class Plan(models.Model):
    """Une offre commerciale. Administrable sans redéploiement (ADR-019)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PUBLISHED = "published", "Publiée"
        RETIRED = "retired", "Retirée"

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    tagline = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    price_yearly = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, default="EUR")
    # « Sur devis » : le prix affiché n'a pas de sens, on montre un appel à
    # contact. Un booléen plutôt qu'un prix nul déguisé — un plan gratuit est
    # une chose, un plan sur devis en est une autre.
    is_quote_only = models.BooleanField(default=False)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_highlighted = models.BooleanField(default=False)

    # --- Quotas ------------------------------------------------------------
    # Le nom dit ce qui est rare : les emplacements de surveillance continue
    # sont pris sur un pool PLATEFORME de 15 (ADR-013), pas sur une réserve
    # propre au client. Vendre ce quota engage donc la plateforme entière —
    # voir apps.billing.capacity.
    monitored_assets = models.PositiveSmallIntegerField(default=1)
    monthly_scans = models.PositiveSmallIntegerField(default=20)
    max_users = models.PositiveSmallIntegerField(default=3)
    # 0 = illimité (offre « Souverain »). Un champ nullable serait plus
    # explicite mais compliquerait chaque comparaison ; 0 est documenté ici et
    # traité en un seul endroit (entitlements.user_limit_reached).
    UNLIMITED = 0

    features = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "price_monthly"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @property
    def enabled_features(self) -> list[str]:
        """Filtré par le registre : une clé inconnue en base est ignorée, pas
        une erreur (features.py)."""
        return feature_registry.sanitize(self.features)

    def has_feature(self, key: str) -> bool:
        return key in self.enabled_features

    @property
    def yearly_equivalent_months(self) -> Decimal | None:
        """Combien de mois le tarif annuel représente — sert à afficher
        « 2 mois offerts » sans coder la remise en dur côté frontend."""
        if not self.price_monthly:
            return None
        return (self.price_yearly / self.price_monthly).quantize(Decimal("0.1"))


class Subscription(models.Model):
    """L'abonnement d'un tenant. Un seul actif par tenant à la fois."""

    class Status(models.TextChoices):
        TRIAL = "trial", "Essai"
        ACTIVE = "active", "Actif"
        SUSPENDED = "suspended", "Suspendu"
        CANCELLED = "cancelled", "Résilié"
        EXPIRED = "expired", "Expiré"

    class Period(models.TextChoices):
        MONTHLY = "monthly", "Mensuel"
        YEARLY = "yearly", "Annuel"

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TRIAL)
    period = models.CharField(max_length=8, choices=Period.choices, default=Period.MONTHLY)

    started_at = models.DateTimeField(default=timezone.now)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    renews_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    # Surcharges négociées : une offre « Souverain » a des quotas sur mesure.
    # ``None`` = on suit le plan. Séparer les surcharges du plan évite de
    # créer un plan fantôme par client négocié.
    override_monitored_assets = models.PositiveSmallIntegerField(null=True, blank=True)
    override_monthly_scans = models.PositiveSmallIntegerField(null=True, blank=True)
    override_max_users = models.PositiveSmallIntegerField(null=True, blank=True)
    override_features = models.JSONField(null=True, blank=True)

    # --- Emplacement du paiement futur (ADR-020) ---------------------------
    # Renseignés le jour où un fournisseur de paiement est branché ; vides
    # aujourd'hui. Les nommer maintenant évite une migration sur une table en
    # production le jour où la décision sera prise.
    billing_provider = models.CharField(max_length=30, blank=True, default="manual")
    external_customer_ref = models.CharField(max_length=120, blank=True)
    external_subscription_ref = models.CharField(max_length=120, blank=True)

    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.tenant.name} — {self.plan.name} ({self.get_status_display()})"

    # --- Droits effectifs (plan + surcharges) ------------------------------

    @property
    def monitored_assets_quota(self) -> int:
        if self.override_monitored_assets is not None:
            return self.override_monitored_assets
        return self.plan.monitored_assets

    @property
    def monthly_scans_quota(self) -> int:
        if self.override_monthly_scans is not None:
            return self.override_monthly_scans
        return self.plan.monthly_scans

    @property
    def max_users_quota(self) -> int:
        if self.override_max_users is not None:
            return self.override_max_users
        return self.plan.max_users

    @property
    def effective_features(self) -> list[str]:
        source = (
            self.override_features if self.override_features is not None else self.plan.features
        )
        return feature_registry.sanitize(source)

    @property
    def is_operational(self) -> bool:
        """Un abonnement suspendu/expiré/résilié conserve l'accès en LECTURE
        (on ne prend jamais les données d'un client en otage) mais ne consomme
        plus de ressource : plus d'analyse, plus de surveillance."""
        return self.status in (self.Status.TRIAL, self.Status.ACTIVE)


class SubscriptionEvent(models.Model):
    """Journal des transitions d'abonnement. Chaque changement d'état est
    explicite et tracé — jamais implicite (exigence de la phase)."""

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=10, blank=True)
    to_status = models.CharField(max_length=10)
    from_plan = models.CharField(max_length=80, blank=True)
    to_plan = models.CharField(max_length=80, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subscription_id} : {self.from_status or '—'} -> {self.to_status}"


class Payment(models.Model):
    """Paiement encaissé, saisi à la main (ADR-020 : aucun fournisseur de
    paiement branché à ce stade)."""

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    received_at = models.DateField()
    reference = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at", "-created_at"]

    def __str__(self):
        return f"{self.amount} {self.currency} — {self.subscription.tenant.name}"
