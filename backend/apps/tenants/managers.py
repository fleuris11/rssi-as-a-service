from django.db import models

from .context import get_current_tenant_id


class TenantScopedManager(models.Manager):
    """Default manager for tenant-owned models.

    Fails closed: if no tenant has been set in the current request context
    (see ``context.py`` / ``middleware.py``), queries return an empty
    queryset rather than every tenant's rows. This is what makes a missing
    ``X-Tenant-Id`` header (or a bug that forgets to scope) safe by default
    instead of a data leak.

    Trusted code that legitimately needs to bypass scoping (the middleware
    itself, platform admin, tenant-resolution services) must use the
    model's ``all_objects`` manager explicitly instead.
    """

    def get_queryset(self):
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            return super().get_queryset().none()
        return super().get_queryset().filter(tenant_id=tenant_id)
