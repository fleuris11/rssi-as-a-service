from django.apps import AppConfig


class ThreatIntelligenceConfig(AppConfig):
    """Cyber threat intelligence (Phase 7, ADR-013) : détection de
    compromissions (fuites de comptes, identifiants volés) via un
    fournisseur externe (Breachsense), derrière une interface de provider
    abstraite."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.threat_intelligence"
    label = "threat_intelligence"
    verbose_name = "Renseignement sur la menace"

    def ready(self):
        from . import signals  # noqa: F401 — enregistre le récepteur post_save
