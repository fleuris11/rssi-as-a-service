"""Factory: the only place in the codebase allowed to decide which
``BreachIntelligenceProvider`` implementation is in use (ADR-013). Every
caller (services.py, tasks.py, views.py) goes through ``get_provider()`` —
never imports ``BreachsenseProvider`` or ``NullProvider`` directly.
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
    "get_provider",
]


def get_provider() -> BreachIntelligenceProvider:
    if not settings.BREACHSENSE_LICENSE_KEY:
        return NullProvider()
    from .breachsense.provider import BreachsenseProvider

    return BreachsenseProvider()
