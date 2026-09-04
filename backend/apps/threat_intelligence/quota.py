"""Tracks and guards the platform-wide (not per-tenant — ADR-013) monthly
``query`` budget of the Breachsense licence. Source of truth is always
Breachsense's own ``/account?action=remaining`` endpoint, mediated through
a short cache so checking the budget doesn't itself burn through it.
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from . import client_messages

logger = logging.getLogger(__name__)

REMAINING_CACHE_KEY = "breachsense:quota:remaining"
REMAINING_CACHE_TIMEOUT_SECONDS = 300  # 5 min — court (ADR-013 : "mis en cache court")


class QuotaExceededError(Exception):
    pass


class QuotaManager:
    """Stateless besides the injected provider — the actual counter lives
    in Redis (cache) and in Breachsense itself, never in this object."""

    def __init__(self, provider=None):
        self._provider = provider

    def _get_provider(self):
        if self._provider is None:
            from .providers import get_provider

            self._provider = get_provider()
        return self._provider

    def get_remaining(self, *, force_refresh: bool = False) -> int | None:
        if not force_refresh:
            cached = cache.get(REMAINING_CACHE_KEY)
            if cached is not None:
                return cached
        remaining = self._get_provider().get_remaining_quota()
        if remaining is not None:
            cache.set(REMAINING_CACHE_KEY, remaining, timeout=REMAINING_CACHE_TIMEOUT_SECONDS)
        return remaining

    def ensure_query_budget_available(self, *, margin: int | None = None) -> None:
        """Raises QuotaExceededError if the remaining budget is at or below
        the safety margin. Silently passes when the provider can't report a
        remaining figure (NullProvider, or a transient lookup failure) —
        callers relying on a real ceiling must be running against a
        configured licence in the first place."""
        margin = margin if margin is not None else settings.BREACHSENSE_QUOTA_SAFETY_MARGIN
        remaining = self.get_remaining()
        if remaining is None:
            return
        if remaining <= margin:
            # Le chiffre exact est celui de la LICENCE, partagée par tous les
            # clients : l'afficher revient à publier la consommation du parc.
            # L'exploitant le trouve dans les journaux, le client lit une
            # indisponibilité temporaire — ce qu'elle est réellement pour lui.
            logger.warning(
                "Budget de requêtes fournisseur insuffisant : %s restantes, marge %s.",
                remaining,
                margin,
            )
            raise QuotaExceededError(client_messages.SCAN_TEMPORARILY_UNAVAILABLE)

    def record_usage(
        self,
        *,
        tenant,
        endpoint: str,
        requests_consumed: int,
        remaining_after: int | None,
        triggered_by: str,
        findings_created: int = 0,
    ):
        from .models import BreachIntelligenceUsage

        usage = BreachIntelligenceUsage.all_objects.create(
            tenant=tenant,
            endpoint=endpoint,
            requests_consumed=requests_consumed,
            remaining_after=remaining_after,
            triggered_by=triggered_by,
            findings_created=findings_created,
        )
        if remaining_after is not None:
            cache.set(REMAINING_CACHE_KEY, remaining_after, timeout=REMAINING_CACHE_TIMEOUT_SECONDS)
        return usage


def get_quota_summary() -> dict:
    """Back-office view (§9 du prompt Phase 7) : état du quota mensuel
    partagé par toute la plateforme."""
    from .models import BreachIntelligenceUsage

    manager = QuotaManager()
    period_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_used = (
        BreachIntelligenceUsage.all_objects.filter(created_at__gte=period_start).aggregate(
            total=Sum("requests_consumed")
        )["total"]
        or 0
    )
    return {
        "remaining": manager.get_remaining(),
        "safety_margin": settings.BREACHSENSE_QUOTA_SAFETY_MARGIN,
        "monthly_requests_used": monthly_used,
        "period_start": period_start,
    }
