"""Low-level HTTP client for the Breachsense API (Essentials tier).

Every request goes through ``RedisTokenBucketThrottle.acquire()`` first
(ADR-013: the 1 req/s, bursts-of-5 licence limit is global, not
per-request-type), and every response is mapped to a specific exception by
status code so callers (``BreachsenseProvider``) never have to inspect a
raw ``requests.Response``.

Pagination contract (ADR-013 — assumption, to verify against the real API
during the licensed smoke test, see docs/journal.md): a ``206`` response
means more pages exist; the response body is either a JSON list of items,
or a JSON object with a ``"results"`` list — the client follows via the
``p`` query parameter (page number, 1-based) until a ``200`` (final page)
is returned or ``MAX_PAGINATION_PAGES`` is reached (safety cap protecting
the monthly query budget from a runaway pagination loop).

Premium-marketplace (a higher licence tier) is explicitly NOT implemented
here — out of scope for the Essentials tier this client targets.
"""

import logging
import time

import requests
from django.conf import settings

from ...throttle import RedisTokenBucketThrottle, ThrottleTimeoutError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15
MAX_PAGINATION_PAGES = 20
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 1

# Endpoints du palier Essentials (prompt Phase 7). Le premium-marketplace
# (palier supérieur) n'est délibérément pas implémenté.
QUERY_ENDPOINTS = (
    "stealer",
    "combo",
    "creds",
    "sessions",
    "nhi",
    "darkweb",
    "docs",
    "asm",
    "radar",
)


class BreachsenseError(Exception):
    """Base class for every error this client can raise."""


class BreachsenseBadRequestError(BreachsenseError):
    pass


class BreachsenseAuthError(BreachsenseError):
    pass


class BreachsenseForbiddenError(BreachsenseError):
    pass


class BreachsenseValidationError(BreachsenseError):
    pass


class BreachsenseRateLimitError(BreachsenseError):
    pass


class BreachsenseServerError(BreachsenseError):
    pass


class BreachsenseNetworkError(BreachsenseError):
    pass


_STATUS_TO_ERROR = {
    400: BreachsenseBadRequestError,
    401: BreachsenseAuthError,
    403: BreachsenseForbiddenError,
    422: BreachsenseValidationError,
    429: BreachsenseRateLimitError,
    500: BreachsenseServerError,
}
_RETRYABLE_STATUSES = {429, 500}


class BreachsenseClient:
    def __init__(
        self,
        *,
        license_key: str | None = None,
        base_url: str | None = None,
        throttle: RedisTokenBucketThrottle | None = None,
        session: requests.Session | None = None,
    ):
        self.license_key = (
            license_key if license_key is not None else settings.BREACHSENSE_LICENSE_KEY
        )
        self.base_url = (base_url or settings.BREACHSENSE_BASE_URL).rstrip("/")
        self.throttle = throttle or RedisTokenBucketThrottle()
        self.session = session or requests.Session()

    # --- Requête bas niveau, une seule page ---------------------------------

    def _request_once(
        self, method: str, path: str, *, params: dict | None = None
    ) -> requests.Response:
        try:
            self.throttle.acquire()
        except ThrottleTimeoutError as exc:
            raise BreachsenseNetworkError(str(exc)) from exc

        url = f"{self.base_url}{path}"
        headers = {"lic": self.license_key}
        try:
            return self.session.request(
                method, url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            raise BreachsenseNetworkError(str(exc)) from exc

    def _request_with_retries(
        self, method: str, path: str, *, params: dict | None = None
    ) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._request_once(method, path, params=params)
            except BreachsenseNetworkError as exc:
                last_exc = exc
                if attempt >= MAX_RETRIES:
                    raise
                self._sleep_backoff(attempt)
                continue

            if response.status_code in (200, 206):
                return response
            if response.status_code in _RETRYABLE_STATUSES and attempt < MAX_RETRIES:
                logger.warning(
                    "Breachsense %s %s -> %s (tentative %s/%s), nouvelle tentative après backoff",
                    method,
                    path,
                    response.status_code,
                    attempt + 1,
                    MAX_RETRIES,
                )
                self._sleep_backoff(attempt)
                continue
            self._raise_for_status(response)

        # Ne devrait être atteint que si toutes les tentatives réseau ont échoué.
        raise last_exc or BreachsenseNetworkError("Échec réseau Breachsense sans détail.")

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(RETRY_BACKOFF_BASE_SECONDS * (2**attempt))

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        error_cls = _STATUS_TO_ERROR.get(response.status_code, BreachsenseError)
        detail = response.text[:500]
        raise error_cls(f"Breachsense a répondu {response.status_code} : {detail}")

    # --- Requête paginée -----------------------------------------------------

    @staticmethod
    def _extract_items(body) -> list:
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            return body.get("results", body.get("data", []))
        return []

    def get_paginated(self, path: str, *, params: dict | None = None) -> tuple[list[dict], int]:
        """Follows ``206`` pages until a ``200`` (final page) or the safety
        cap. Returns ``(items, requests_consumed)`` — the caller (provider)
        needs ``requests_consumed`` to report accurate usage to
        QuotaManager, since one logical query may cost several HTTP
        requests."""
        base_params = params or {}
        items: list[dict] = []
        requests_consumed = 0
        page = 1

        while True:
            # Un nouveau dict à chaque page (pas de mutation d'un dict
            # partagé) : session.request() construit sa requête de façon
            # synchrone, donc muter params après coup serait déjà sans
            # danger fonctionnel, mais un objet neuf par appel reste plus
            # sûr et plus facile à raisonner (et à tester).
            page_params = {**base_params, "p": page}
            response = self._request_with_retries("GET", path, params=page_params)
            requests_consumed += 1
            body = response.json() if response.content else []
            items.extend(self._extract_items(body))

            if response.status_code == 200:
                break
            if page >= MAX_PAGINATION_PAGES:
                logger.warning(
                    "Breachsense %s : plafond de pagination (%s pages) atteint, arrêt.",
                    path,
                    MAX_PAGINATION_PAGES,
                )
                break
            page += 1

        return items, requests_consumed

    # --- Endpoints de requête (palier Essentials) -----------------------------

    def stealer(self, **params) -> tuple[list[dict], int]:
        return self.get_paginated("/stealer", params=params)

    def combo(self, **params) -> tuple[list[dict], int]:
        return self.get_paginated("/combo", params=params)

    def creds(self, **params) -> tuple[list[dict], int]:
        return self.get_paginated("/creds", params=params)

    def sessions(self, **params) -> tuple[list[dict], int]:
        return self.get_paginated("/sessions", params=params)

    def nhi(self, **params) -> tuple[list[dict], int]:
        return self.get_paginated("/nhi", params=params)

    def darkweb(self, **params) -> tuple[list[dict], int]:
        return self.get_paginated("/darkweb", params=params)

    def docs(self, **params) -> tuple[list[dict], int]:
        return self.get_paginated("/docs", params=params)

    def asm(self, **params) -> tuple[list[dict], int]:
        return self.get_paginated("/asm", params=params)

    def radar(self, **params) -> tuple[list[dict], int]:
        return self.get_paginated("/radar", params=params)

    # --- Gestion de compte / du pool de 15 actifs -----------------------------

    def account_add(self, *, asset: str, asset_type: str, webhook_url: str | None = None) -> dict:
        # `ast` est le nom réel du paramètre d'actif (confirmé par la réponse
        # de `action=list`, qui renvoie `[{"ast": "..."}]`). `asset` et `type`
        # n'existent pas côté API — un ajout partait donc en 400.
        #
        # `asset_type` reste dans la signature : c'est notre vocabulaire
        # métier (domaine, email), utile à l'appelant et stocké dans
        # MonitoredAsset. Breachsense, lui, déduit le type de la valeur — il
        # n'a pas de paramètre pour le recevoir, on ne l'envoie donc pas.
        params = {"action": "add", "ast": asset}
        if webhook_url:
            params["notify"] = webhook_url
        response = self._request_with_retries("GET", "/account", params=params)
        return response.json() if response.content else {}

    def account_del(self, *, provider_ref: str) -> dict:
        response = self._request_with_retries(
            "GET", "/account", params={"action": "del", "ast": provider_ref}
        )
        return response.json() if response.content else {}

    def account_list(self) -> list[dict]:
        items, _requests_consumed = self.get_paginated("/account", params={"action": "list"})
        return items

    def account_test(self) -> dict:
        response = self._request_with_retries("GET", "/account", params={"action": "test"})
        return response.json() if response.content else {}

    def account_rotate(self) -> dict:
        response = self._request_with_retries("GET", "/account", params={"action": "rotate"})
        return response.json() if response.content else {}

    def account_audit(self) -> list[dict]:
        items, _requests_consumed = self.get_paginated("/account", params={"action": "audit"})
        return items

    def account_remaining(self) -> dict:
        # Le budget restant se demande par `r=1`, PAS par `action=remaining` —
        # « remaining » n'est pas une action valide (add/del/list/test/rotate/
        # audit le sont). L'API répondait donc 200 avec un corps VIDE, ce qui
        # ne ressemble pas à une erreur : le quota était simplement toujours
        # inconnu. Une garde qui ne garde rien, sans le dire.
        response = self._request_with_retries("GET", "/account", params={"r": 1})
        return response.json() if response.content else {}

    def account_creds(self, *, username: str, password: str) -> dict:
        """Configure les identifiants HTTP Basic du webhook côté Breachsense
        (``/account?action=add&creds=...``, prompt Phase 7 point 7) —
        distinct de ``account_add`` (enregistrement d'un actif)."""
        response = self._request_with_retries(
            "GET",
            "/account",
            params={"action": "add", "creds": f"{username}:{password}"},
        )
        return response.json() if response.content else {}
