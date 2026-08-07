"""No-op provider used when ``BREACHSENSE_LICENSE_KEY`` isn't configured
(local dev without a license, or any future environment without CTI
access). Every query-style method returns an empty/neutral result instead
of raising, so a scan silently finds nothing rather than crashing —
except the two account-management methods that would need a real license
to do anything meaningful, which raise ProviderNotConfiguredError so the
back-office can render "CTI non configuré" rather than a wrong success."""

from .base import (
    BreachIntelligenceProvider,
    MonitoredAssetRegistration,
    ProviderNotConfiguredError,
    RawFinding,
    ScanResult,
)


class NullProvider(BreachIntelligenceProvider):
    def scan_domain(self, domain: str) -> ScanResult:
        return ScanResult(findings=[], requests_consumed=0, remaining_quota=None)

    def scan_email(self, email: str) -> ScanResult:
        return ScanResult(findings=[], requests_consumed=0, remaining_quota=None)

    def register_monitored_asset(
        self, *, asset_type: str, value: str
    ) -> MonitoredAssetRegistration:
        raise ProviderNotConfiguredError(
            "Aucune licence Breachsense configurée (BREACHSENSE_LICENSE_KEY absente)."
        )

    def unregister_monitored_asset(self, provider_ref: str) -> None:
        raise ProviderNotConfiguredError(
            "Aucune licence Breachsense configurée (BREACHSENSE_LICENSE_KEY absente)."
        )

    def list_monitored_assets(self) -> list[MonitoredAssetRegistration]:
        return []

    def get_remaining_quota(self) -> int | None:
        return None

    def send_test_alert(self) -> bool:
        return False

    def normalize_webhook_payload(self, payload: list[dict]) -> list[RawFinding]:
        return []
