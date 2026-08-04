"""Check (b): SSL certificate — validity, issuer, expiry date."""

import socket
import ssl
from datetime import UTC, datetime

from apps.monitoring.models import CheckResult

from .ssrf import SSRFError, resolve_safe_host

CONNECT_TIMEOUT_SECONDS = 10
WARNING_THRESHOLD_DAYS = 30

# %b %d %H:%M:%S %Y %Z, e.g. "Jan  1 00:00:00 2027 GMT" — the format
# Python's ssl module returns notAfter/notBefore in.
_CERT_DATE_FORMAT = "%b %d %H:%M:%S %Y %Z"


def check_ssl_certificate(hostname: str, port: int = 443) -> dict:
    try:
        resolve_safe_host(hostname)
    except SSRFError as exc:
        return {
            "status": CheckResult.Status.CRITICAL,
            "details": {"error": f"Cible refusée : {exc}"},
        }

    context = ssl.create_default_context()
    try:
        with (
            socket.create_connection((hostname, port), timeout=CONNECT_TIMEOUT_SECONDS) as sock,
            context.wrap_socket(sock, server_hostname=hostname) as ssock,
        ):
            cert = ssock.getpeercert()
    except (OSError, ssl.SSLError) as exc:
        return {"status": CheckResult.Status.CRITICAL, "details": {"error": str(exc)}}

    if not cert or "notAfter" not in cert:
        return {
            "status": CheckResult.Status.CRITICAL,
            "details": {"error": "Certificat sans date d'expiration exploitable."},
        }

    not_after = datetime.strptime(cert["notAfter"], _CERT_DATE_FORMAT).replace(tzinfo=UTC)
    days_left = (not_after - datetime.now(UTC)).days
    issuer = dict(x[0] for x in cert.get("issuer", []))

    if days_left < 0:
        status = CheckResult.Status.CRITICAL
    elif days_left <= WARNING_THRESHOLD_DAYS:
        status = CheckResult.Status.WARNING
    else:
        status = CheckResult.Status.OK

    return {
        "status": status,
        "details": {
            "expires_at": not_after.isoformat(),
            "days_left": days_left,
            "issuer": issuer.get("organizationName", ""),
        },
    }
