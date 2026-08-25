"""Cassette-replaying provider (Phase 8A, ADR-015). Serves pre-recorded
Breachsense responses from ``tests/fixtures/breachsense/`` with **zero**
network calls, so day-to-day development and CI exercise the real ingestion
pipeline (normalisation, dédoublonnage, alerte) against realistic data
without ever spending the platform's precious shared query quota
(1000 req/mois).

Cassettes are recorded by ``record_breachsense_cassette`` from a single real
scan, and are **always already masked** before being written to disk
(ADR-014 applies to fixtures too — a cassette never contains a secret in
clear). Re-running a masked payload through the normalizer on replay is
harmless: the mask markers are simply re-masked, never a real secret.
"""

import json
from pathlib import Path

from django.conf import settings

from .base import (
    BreachIntelligenceProvider,
    MonitoredAssetRegistration,
    RawFinding,
    ScanResult,
)


def cassette_dir() -> Path:
    configured = getattr(settings, "BREACHSENSE_CASSETTE_DIR", "")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "breachsense"


def cassette_path(domain: str) -> Path:
    return cassette_dir() / f"{slugify_domain(domain)}.json"


def slugify_domain(domain: str) -> str:
    return domain.strip().lower().replace("://", "_").replace("/", "_").replace(":", "_")


def cassettes_available() -> bool:
    directory = cassette_dir()
    return directory.is_dir() and any(directory.glob("*.json"))


class ReplayProvider(BreachIntelligenceProvider):
    def _load_cassette(self, domain: str) -> dict:
        path = cassette_path(domain)
        if not path.is_file():
            return {}
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def _scan(self, key: str) -> ScanResult:
        cassette = self._load_cassette(key)
        endpoints = cassette.get("endpoints", {})
        findings = [
            RawFinding(endpoint=endpoint, payload=item)
            for endpoint, items in endpoints.items()
            for item in items
        ]
        # No network request was made — replay must never inflate the usage
        # figures QuotaManager records.
        return ScanResult(findings=findings, requests_consumed=0, remaining_quota=None)

    def scan_domain(self, domain: str) -> ScanResult:
        return self._scan(domain)

    def scan_email(self, email: str) -> ScanResult:
        return self._scan(email)

    def register_monitored_asset(
        self, *, asset_type: str, value: str
    ) -> MonitoredAssetRegistration:
        # Synthetic registration so the "Surveiller" action works in a demo
        # without a real pool call — provider_ref is deterministic per value.
        return MonitoredAssetRegistration(
            provider_ref=f"replay-{slugify_domain(value)}", asset_type=asset_type, value=value
        )

    def unregister_monitored_asset(self, provider_ref: str) -> None:
        return None

    def list_monitored_assets(self) -> list[MonitoredAssetRegistration]:
        return []

    def get_remaining_quota(self) -> int | None:
        # A plausible, stable figure so the back-office shows a number rather
        # than "inconnu" during a demo — never a real API-reported value.
        return getattr(settings, "BREACHSENSE_REPLAY_REMAINING_QUOTA", 950)

    def send_test_alert(self) -> bool:
        return True

    def normalize_webhook_payload(self, payload: list[dict]) -> list[RawFinding]:
        findings = []
        for item in payload:
            item = dict(item)
            asset_ref = str(item.pop("ast", ""))
            endpoint = str(item.pop("api", "webhook"))
            is_test = bool(item.pop("test", False))
            findings.append(
                RawFinding(endpoint=endpoint, payload=item, is_test=is_test, asset_ref=asset_ref)
            )
        return findings


def send_test_alert() -> bool:
    """Send à test in background after à replay scan."" """

    return True
