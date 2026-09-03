"""Concrete ``BreachIntelligenceProvider`` backed by the real Breachsense
API. Owns exactly two concerns: talking to ``BreachsenseClient`` and
shaping its responses into the provider-interface's plain dataclasses —
budget/pool bookkeeping (QuotaManager, MonitoredAsset) lives one layer up,
in ``threat_intelligence.services``, so this class stays swappable for a
different CTI vendor without dragging our own persistence model with it.
"""

import logging

from django.conf import settings

from ..base import (
    BreachIntelligenceProvider,
    MonitoredAssetRegistration,
    ProviderPoolFullError,
    RawFinding,
    ScanResult,
)
from .client import (
    QUERY_ENDPOINTS,
    BreachsenseClient,
    BreachsenseForbiddenError,
)

logger = logging.getLogger(__name__)

_ENDPOINT_METHODS = (
    QUERY_ENDPOINTS  # stealer, combo, creds, sessions, nhi, darkweb, docs, asm, radar
)


class BreachsenseProvider(BreachIntelligenceProvider):
    def __init__(self, client: BreachsenseClient | None = None):
        self.client = client or BreachsenseClient()

    def _scan(self, *, domain: str | None = None, email: str | None = None) -> ScanResult:
        findings: list[RawFinding] = []
        requests_consumed = 0
        # Le paramètre de recherche s'appelle `s` sur TOUS les endpoints de
        # requête, et il accepte indifféremment un domaine ou une adresse
        # email — il n'existe pas de paramètre `domain` ni `email` côté
        # Breachsense. La distinction domaine/email reste utile ici (elle
        # nomme l'intention de l'appelant), mais elle ne passe pas sur le fil.
        #
        # C'est le défaut qui a rendu tout scan réel impossible : l'API
        # répondait « 400 Request missing the appropriate parameters » sur
        # chaque endpoint. Vérifié contre l'API réelle le 03/09/2026.
        params = {"s": domain or email}

        for endpoint in _ENDPOINT_METHODS:
            method = getattr(self.client, endpoint)
            items, consumed = method(**params)
            requests_consumed += consumed
            findings.extend(RawFinding(endpoint=endpoint, payload=item) for item in items)

        return ScanResult(
            findings=findings, requests_consumed=requests_consumed, remaining_quota=None
        )

    def scan_domain(self, domain: str) -> ScanResult:
        return self._scan(domain=domain)

    def scan_email(self, email: str) -> ScanResult:
        return self._scan(email=email)

    def register_monitored_asset(
        self, *, asset_type: str, value: str
    ) -> MonitoredAssetRegistration:
        try:
            response = self.client.account_add(asset=value, asset_type=asset_type)
        except BreachsenseForbiddenError as exc:
            # Le palier Essentials refuse un ajout au-delà des 15 slots par
            # un 403 (contrainte de licence, pas un problème d'auth) —
            # traduit en erreur métier explicite pour le service appelant.
            raise ProviderPoolFullError(
                "Le pool Breachsense de 15 actifs monitorés est complet."
            ) from exc
        provider_ref = str(response.get("ref") or response.get("id") or value)
        return MonitoredAssetRegistration(
            provider_ref=provider_ref, asset_type=asset_type, value=value
        )

    def unregister_monitored_asset(self, provider_ref: str) -> None:
        self.client.account_del(provider_ref=provider_ref)

    def list_monitored_assets(self) -> list[MonitoredAssetRegistration]:
        items = self.client.account_list()
        # Réponse réelle de `/account?action=list` :
        # ``[{"ast": "exemple.fr"}, ...]`` — un seul champ, `ast`, qui porte
        # à la fois l'identifiant et la valeur. Les clés `ref`/`id`/`asset`
        # supposées jusqu'ici n'existent pas : la liste revenait donc pleine
        # de `provider_ref="None"`, ce qui rendait tout désenregistrement
        # impossible. Vérifié contre l'API réelle le 03/09/2026.
        return [
            MonitoredAssetRegistration(
                provider_ref=str(item.get("ast") or ""),
                asset_type=item.get("type", ""),
                value=item.get("ast", ""),
            )
            for item in items
            if item.get("ast")
        ]

    def get_remaining_quota(self) -> int | None:
        try:
            response = self.client.account_remaining()
        except Exception:  # noqa: BLE001 - le quota devient simplement "inconnu"
            logger.warning("Impossible de récupérer le quota Breachsense restant.", exc_info=True)
            return None
        # L'API répond ``{"Remaining": 985}`` — R majuscule. La clé
        # minuscule était lue jusqu'ici, donc le quota restait éternellement
        # « inconnu » et la garde de budget (`ensure_query_budget_available`)
        # laissait tout passer sans jamais rien protéger : une panne
        # silencieuse, qui ne se serait manifestée qu'en épuisant la licence.
        # Les deux graphies sont acceptées, la casse d'une clé JSON étant une
        # chose qu'un fournisseur peut normaliser sans prévenir.
        remaining = response.get("Remaining", response.get("remaining"))
        return int(remaining) if remaining is not None else None

    def send_test_alert(self) -> bool:
        response = self.client.account_test()
        return bool(response.get("ok", response.get("success", True)))

    def configure_webhook_credentials(self) -> None:
        """Not part of the abstract interface (it's a one-time Breachsense-
        side configuration step, not a per-scan operation) — exposed here
        for the management command used during deployment setup (docs/
        journal.md smoke-test protocol)."""
        self.client.account_creds(
            username=settings.BREACHSENSE_WEBHOOK_USERNAME,
            password=settings.BREACHSENSE_WEBHOOK_PASSWORD,
        )

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
