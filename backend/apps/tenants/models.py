import uuid

from django.conf import settings
from django.db import models

from .managers import TenantScopedManager


class Tenant(models.Model):
    """A customer company — the isolation boundary for all business data."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    sector = models.CharField(max_length=120, blank=True)
    headcount = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # US-4.3: kill switch for every AI feature (documents, assistant, météo
    # enrichie) — checked by apps.ai_assistant.services before any call;
    # false makes every AI endpoint return 403 and the frontend hides them.
    ai_enabled = models.BooleanField(default=True)

    # Délai minimal entre deux analyses lancées à la main, POUR CE CLIENT,
    # **en minutes**.
    #
    # La minute est l'unité canonique de bout en bout — modèle, réglage de
    # plateforme, API, cache. L'heure n'existe plus qu'à la saisie, comme
    # commodité d'affichage. Un système qui stocke des heures ici et des
    # minutes là finit par diviser ou multiplier par 60 au mauvais endroit, et
    # ce genre d'erreur ne se voit pas : elle donne un délai plausible.
    #
    # `null` = on applique le réglage de plateforme (console d'administration,
    # à défaut BREACHSENSE_SCAN_COOLDOWN_HOURS, converti en minutes).
    # Une surcharge par client existe parce que le délai n'a pas la même
    # justification partout : il protège un budget de requêtes partagé, et un
    # client qu'on accompagne de près — ou qu'on démarche — n'a pas à subir le
    # rythme calibré pour le parc. `0` est une valeur valide : « aucun délai ».
    #
    # PositiveIntegerField et non Small : 8760 heures tenaient dans un
    # SmallInt, 525 600 minutes n'y tiendraient pas.
    scan_cooldown_minutes = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # --- Fiche commerciale (phase 11) --------------------------------------
    # Renseignées depuis la console. Aucune n'est requise : on crée un client
    # avec un nom, on complète ensuite.
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    website = models.CharField(max_length=200, blank=True)
    account_manager = models.CharField(max_length=120, blank=True)
    internal_notes = models.TextField(blank=True)

    # --- Corbeille (phase 11) ----------------------------------------------
    # Une suppression est d'abord LOGIQUE et réversible : effacer une
    # entreprise détruirait ses diagnostics, ses actifs et son historique de
    # fuites, sans retour possible. La suppression définitive existe, isolée,
    # et n'est proposée qu'après archivage.
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    archive_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


class TenantScopedModel(models.Model):
    """Base class for every model that belongs to exactly one tenant.

    ``objects`` (the default manager) is a ``TenantScopedManager``: it only
    ever returns rows for the tenant currently set by
    ``TenantScopingMiddleware``. ``all_objects`` is the plain, unscoped
    manager for trusted code paths that must cross tenants deliberately.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="+")

    all_objects = models.Manager()
    objects = TenantScopedManager()

    class Meta:
        abstract = True
        default_manager_name = "objects"


class Membership(TenantScopedModel):
    """A user's role within one tenant. A user may belong to several tenants."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrateur"
        CONTRIBUTOR = "contributor", "Contributeur"
        READER = "reader", "Lecteur"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.READER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "user"], name="unique_membership_per_tenant"),
        ]
        ordering = ["tenant_id", "role"]

    def __str__(self):
        return f"{self.user_id} @ {self.tenant_id} ({self.role})"
