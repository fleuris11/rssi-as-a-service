"""SSRF protection shared by every check (CLAUDE.md: "Protection SSRF :
résolution DNS validée contre les plages IP privées avant tout check").

Every function here is defensive: it must run *before* any socket gets
opened to a resolved address, including on each hop of an HTTP redirect
chain — a check that validates the first URL and then blindly follows
redirects would let an attacker point a declared asset at an internal
service via a 302.
"""

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}


class SSRFError(Exception):
    """Raised whenever a target would require connecting to a host/IP
    that isn't safe to reach from this server."""


def _is_unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def resolve_safe_host(hostname: str) -> set[str]:
    """Resolves ``hostname`` and raises SSRFError if any resolved address
    is private/loopback/link-local/reserved/multicast/unspecified.

    Returns the set of resolved IPs (useful for logging/details) on success.
    """
    if not hostname:
        raise SSRFError("Nom d'hôte manquant.")

    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SSRFError(f"Résolution DNS impossible pour {hostname!r}.") from exc

    resolved_ips = {info[4][0] for info in addrinfo}
    if not resolved_ips:
        raise SSRFError(f"Aucune adresse IP résolue pour {hostname!r}.")

    for ip_str in resolved_ips:
        ip = ipaddress.ip_address(ip_str.split("%")[0])  # strip IPv6 zone id
        if _is_unsafe_ip(ip):
            raise SSRFError(f"Adresse IP non autorisée pour {hostname!r} : {ip}")

    return resolved_ips


def validate_url(url: str) -> str:
    """Validates scheme + resolves/validates the host of ``url``. Returns
    the hostname on success, raises SSRFError otherwise."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise SSRFError(f"Schéma non autorisé : {parsed.scheme!r} (http/https uniquement).")
    if not parsed.hostname:
        raise SSRFError(f"URL sans hôte valide : {url!r}")
    resolve_safe_host(parsed.hostname)
    return parsed.hostname
