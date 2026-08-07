"""Wires the "scan initial à la déclaration d'un actif" behaviour (ADR-013)
without apps.monitoring ever importing apps.threat_intelligence — a
post_save signal is the standard Django way to keep the dependency
pointing the right way (threat_intelligence -> monitoring only).
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.monitoring.models import Asset

logger = logging.getLogger(__name__)

# Both asset types map to a domain Breachsense can query (website -> its
# hostname, email_domain -> itself) — see services.derive_scan_domain.
_SCANNABLE_ASSET_TYPES = {Asset.Type.WEBSITE, Asset.Type.EMAIL_DOMAIN}


@receiver(post_save, sender=Asset, dispatch_uid="threat_intelligence_initial_scan")
def trigger_initial_scan(sender, instance, created, **kwargs):
    if not created or instance.type not in _SCANNABLE_ASSET_TYPES:
        return
    from .tasks import run_breach_scan_task

    try:
        run_breach_scan_task.delay(
            tenant_id=str(instance.tenant_id), asset_id=instance.id, triggered_by="initial"
        )
    except Exception:  # noqa: BLE001 - la déclaration d'actif ne doit jamais échouer à cause du CTI
        logger.warning(
            "Impossible de planifier le scan initial Breachsense pour l'actif %s",
            instance.id,
            exc_info=True,
        )
