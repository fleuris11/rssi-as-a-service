from django.apps import AppConfig


class PlatformAdminConfig(AppConfig):
    """Scaffolded now, built out in a later phase: superviseur back-office
    (tenants, quotas, platform health — US-1.4)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.platform_admin"
    label = "platform_admin"
    verbose_name = "Administration de la plateforme"
