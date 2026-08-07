"""Abstract contract every CTI (cyber threat intelligence) provider must
implement (ADR-013: inversion de dépendance). Nothing outside
``apps.threat_intelligence.providers`` may import a concrete provider
directly — callers obtain one via ``get_provider()`` (see
``providers/__init__.py``) and only ever call methods declared here.

Every method operates on already-normalized primitives (plain strings,
dicts) — never on Django models — so a provider implementation stays
swappable without dragging model imports into the provider layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


class ProviderError(Exception):
    """Base class for every error a provider implementation may raise."""


class ProviderNotConfiguredError(ProviderError):
    """Raised by NullProvider — no license/API key configured for this
    environment. Distinct from a real provider failure so callers (and the
    back-office) can display "CTI non configuré" instead of a 500."""


class ProviderQuotaExceededError(ProviderError):
    """The query budget (global, shared across the whole platform — see
    ADR-013) is exhausted or would fall under the configured safety
    margin."""


class ProviderPoolFullError(ProviderError):
    """The monitored-asset pool (15 slots on the Essentials tier) is full —
    register_monitored_asset refuses cleanly rather than silently failing
    at the HTTP layer."""


@dataclass
class RawFinding:
    """One raw, not-yet-normalized record returned by a provider query or
    webhook delivery. ``payload`` is whatever the provider returned for
    this record — normalization (secret masking, severity mapping) happens
    one layer up, in ``threat_intelligence.services`` /
    ``normalizer.py``, never inside the provider itself, so every provider
    implementation is held to the exact same non-storage-of-secrets
    discipline (ADR-014) instead of reimplementing it per provider.
    """

    endpoint: str
    payload: dict
    is_test: bool = False
    # Populated for webhook-delivered findings only (the provider's own
    # asset reference, e.g. the domain/email Breachsense is reporting
    # against — the ``ast`` field of the webhook item) — used by
    # ``services.py`` to resolve which tenant/monitoring.Asset the finding
    # belongs to via MonitoredAsset.provider_ref. Empty for scan-triggered
    # findings, where the caller already knows the asset directly.
    asset_ref: str = ""


@dataclass
class ScanResult:
    """Every raw finding returned by a diagnostic scan, plus how many HTTP
    requests it consumed (for QuotaManager bookkeeping) and the provider's
    own post-call remaining-quota figure, when it returned one."""

    findings: list[RawFinding] = field(default_factory=list)
    requests_consumed: int = 0
    remaining_quota: int | None = None


@dataclass
class MonitoredAssetRegistration:
    provider_ref: str
    asset_type: str
    value: str
    registered_at: date | None = None


class BreachIntelligenceProvider(ABC):
    """Business-level interface for a CTI provider. Implementations:
    ``BreachsenseProvider`` (real), ``NullProvider`` (no license
    configured)."""

    @abstractmethod
    def scan_domain(self, domain: str) -> ScanResult:
        """Query every endpoint relevant to a domain (website or email
        domain) — stealer logs, combo lists, credentials, sessions, NHI,
        dark web mentions, leaked documents, attack surface, radar."""

    @abstractmethod
    def scan_email(self, email: str) -> ScanResult:
        """Query every endpoint relevant to a single email address."""

    @abstractmethod
    def register_monitored_asset(
        self, *, asset_type: str, value: str
    ) -> MonitoredAssetRegistration:
        """Adds ``value`` to the provider's real-time webhook monitoring
        pool. Raises ProviderPoolFullError if the pool is at capacity."""

    @abstractmethod
    def unregister_monitored_asset(self, provider_ref: str) -> None:
        pass

    @abstractmethod
    def list_monitored_assets(self) -> list[MonitoredAssetRegistration]:
        pass

    @abstractmethod
    def get_remaining_quota(self) -> int | None:
        """Remaining ``query`` requests for the current period, straight
        from the provider (QuotaManager is responsible for caching this) —
        ``None`` if the provider can't report one (e.g. NullProvider)."""

    @abstractmethod
    def send_test_alert(self) -> bool:
        """Asks the provider to fire a test webhook delivery (used to
        verify webhook connectivity once deployed — see docs/journal.md
        smoke-test protocol). Returns whether the request was accepted."""

    @abstractmethod
    def normalize_webhook_payload(self, payload: list[dict]) -> list[RawFinding]:
        """Turns a raw webhook request body (a JSON array of
        ``{"ast": ..., "api": ..., "test": bool, ...}`` objects, per the
        Breachsense webhook format) into ``RawFinding`` instances."""
