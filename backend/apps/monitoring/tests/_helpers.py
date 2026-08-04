"""Shared test support (not a test module itself — no test_ prefix)."""

import socket
from unittest.mock import patch

_real_getaddrinfo = socket.getaddrinfo


def patch_public_dns(hostname="example.com", ip="93.184.216.34"):
    """Mocks DNS resolution for ``hostname`` only, to a public IP — any
    other host (in particular a literal IP like 127.0.0.1, e.g. a
    redirect target in an SSRF test) falls through to the real resolver,
    which handles literal IPs instantly with no network call."""

    def fake_getaddrinfo(host, *args, **kwargs):
        if host == hostname:
            return [(2, 1, 6, "", (ip, 0))]
        return _real_getaddrinfo(host, *args, **kwargs)

    return patch("socket.getaddrinfo", side_effect=fake_getaddrinfo)
