"""Factory: the only place in the codebase allowed to decide which
``BreachIntelligenceProvider`` implementation is in use (ADR-013). Every
caller (services.py, tasks.py, views.py) goes through ``get_provider()`` —
never imports ``BreachsenseProvider``/``ReplayProvider``/``NullProvider``
directly.

Mode selection (Phase 8A, ADR-015) is driven by ``BREACHSENSE_MODE``, not
by the mere presence of a licence key: a configured licence is a
*capability*, not an instruction to spend it. "live" must always be an
explicit opt-in, so no real query leaves the platform during ordinary
development, testing, or a client demo.
"""

from django.conf import settings

from .base import (
    BreachIntelligenceProvider,
    MonitoredAssetRegistration,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderPoolFullError,
    ProviderQuotaExceededError,
    RawFinding,
    ScanResult,
)
from .null_provider import NullProvider
from .replay_provider import ReplayProvider, cassettes_available

__all__ = [
    "BreachIntelligenceProvider",
    "MonitoredAssetRegistration",
    "ProviderError",
    "ProviderNotConfiguredError",
    "ProviderPoolFullError",
    "ProviderQuotaExceededError",
    "RawFinding",
    "ScanResult",
    "NullProvider",
    "ReplayProvider",
    "get_provider",
    "resolve_mode",
]

MODE_LIVE = "live"
MODE_REPLAY = "replay"
MODE_NULL = "null"
MODE_AUTO = "auto"


def resolve_mode() -> str:
    """Turns the configured (possibly "auto") mode into a concrete one.
    Exposed for the back-office/diagnostics so an operator can see which
    source is actually in use, rather than inferring it."""
    mode = (getattr(settings, "BREACHSENSE_MODE", MODE_AUTO) or MODE_AUTO).strip().lower()

    if mode == MODE_LIVE:
        # A "live" request without a licence can't work — fall back rather
        # than raise, so a misconfigured environment degrades to "no data"
        # instead of 500-ing every scan.
        return MODE_LIVE if settings.BREACHSENSE_LICENSE_KEY else MODE_NULL
    if mode in (MODE_REPLAY, MODE_NULL):
        return mode
    # "auto" (and any unknown value, defensively): never live.
    return MODE_REPLAY if cassettes_available() else MODE_NULL


def get_provider() -> BreachIntelligenceProvider:
    mode = resolve_mode()
    if mode == MODE_LIVE:
        from .breachsense.provider import BreachsenseProvider

        return BreachsenseProvider()
    if mode == MODE_REPLAY:
        return ReplayProvider()
    return NullProvider()
