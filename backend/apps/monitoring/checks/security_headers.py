"""Check (c): HTTP security headers — HSTS, CSP, X-Frame-Options,
X-Content-Type-Options — with a recommendation per missing header."""

from apps.monitoring.models import CheckResult

from .http_client import CheckNetworkError, SSRFError, safe_get

REQUIRED_HEADERS = {
    "Strict-Transport-Security": (
        "Ajoutez l'en-tête HSTS pour forcer les connexions HTTPS sur ce domaine."
    ),
    "Content-Security-Policy": (
        "Ajoutez une politique CSP pour limiter les sources de contenu autorisées."
    ),
    "X-Frame-Options": (
        "Ajoutez X-Frame-Options pour empêcher le détournement de clic (clickjacking)."
    ),
    "X-Content-Type-Options": (
        "Ajoutez X-Content-Type-Options: nosniff pour empêcher le détournement de type MIME."
    ),
}


def check_security_headers(url: str) -> dict:
    try:
        response = safe_get(url)
    except SSRFError as exc:
        return {
            "status": CheckResult.Status.CRITICAL,
            "details": {"error": f"Cible refusée : {exc}"},
        }
    except CheckNetworkError as exc:
        return {"status": CheckResult.Status.CRITICAL, "details": {"error": str(exc)}}

    present = []
    missing = []
    for header, recommendation in REQUIRED_HEADERS.items():
        if header in response.headers:
            present.append(header)
        else:
            missing.append({"header": header, "recommendation": recommendation})

    status = CheckResult.Status.WARNING if missing else CheckResult.Status.OK
    return {"status": status, "details": {"present": present, "missing": missing}}
