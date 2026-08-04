"""SSRF protection tests (CLAUDE.md: "résolution DNS validée contre les
plages IP privées avant tout check"). Rejection cases use literal IP
addresses as the target — socket.getaddrinfo resolves those instantly
without a real DNS query, so these run fully offline. The "safe" cases
mock getaddrinfo so the success path is offline and deterministic too.
"""

from unittest.mock import patch

import pytest

from apps.monitoring.checks.ssrf import SSRFError, resolve_safe_host, validate_url


class TestRejectsUnsafeIPs:
    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",  # loopback
            "10.0.0.5",  # private (RFC1918)
            "172.16.0.1",  # private (RFC1918)
            "192.168.1.1",  # private (RFC1918)
            "169.254.1.1",  # link-local
            "0.0.0.0",  # unspecified
            "::1",  # IPv6 loopback
            "fe80::1",  # IPv6 link-local
        ],
    )
    def test_rejects_literal_unsafe_ip(self, ip):
        with pytest.raises(SSRFError):
            resolve_safe_host(ip)

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "https://10.0.0.5:8080/admin",
            "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        ],
    )
    def test_rejects_unsafe_url(self, url):
        with pytest.raises(SSRFError):
            validate_url(url)


class TestRejectsDisallowedSchemes:
    @pytest.mark.parametrize("url", ["ftp://example.com/", "file:///etc/passwd", "gopher://x/"])
    def test_rejects_non_http_scheme(self, url):
        with pytest.raises(SSRFError):
            validate_url(url)


class TestAllowsSafePublicHost:
    def test_allows_resolved_public_ip(self):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
            ips = resolve_safe_host("example.com")
        assert ips == {"93.184.216.34"}

    def test_validate_url_returns_hostname_for_safe_url(self):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
            hostname = validate_url("https://example.com/path")
        assert hostname == "example.com"


class TestDnsFailure:
    def test_unresolvable_host_raises(self):
        import socket

        with patch("socket.getaddrinfo", side_effect=socket.gaierror("no such host")):
            with pytest.raises(SSRFError):
                resolve_safe_host("does-not-exist.invalid")

    def test_missing_hostname_raises(self):
        with pytest.raises(SSRFError):
            validate_url("http:///no-host")
