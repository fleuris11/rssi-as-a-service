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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


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
