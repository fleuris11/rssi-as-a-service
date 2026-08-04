"""Check (a): HTTP uptime — GET with timeout, status + latency."""

import time

from apps.monitoring.models import CheckResult

from .http_client import CheckNetworkError, SSRFError, safe_get


def check_http_uptime(url: str) -> dict:
    start = time.monotonic()
    try:
        response = safe_get(url)
    except SSRFError as exc:
        return {
            "status": CheckResult.Status.CRITICAL,
            "latency_ms": None,
            "details": {"error": f"Cible refusée : {exc}"},
        }
    except CheckNetworkError as exc:
        return {
            "status": CheckResult.Status.CRITICAL,
            "latency_ms": None,
            "details": {"error": str(exc)},
        }

    latency_ms = round((time.monotonic() - start) * 1000, 1)
    details = {"status_code": response.status_code, "final_url": response.url}

    if 200 <= response.status_code < 400:
        status = CheckResult.Status.OK
    else:
        status = CheckResult.Status.CRITICAL

    return {"status": status, "latency_ms": latency_ms, "details": details}
