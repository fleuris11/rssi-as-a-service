from unittest.mock import Mock, patch

from apps.monitoring.checks.http_uptime import check_http_uptime
from apps.monitoring.models import CheckResult

from ._helpers import patch_public_dns

PUBLIC_IP_PATCH = patch_public_dns()


class TestCheckHttpUptime:
    def test_ok_on_2xx_response(self):
        response = Mock(status_code=200, url="https://example.com/", headers={}, is_redirect=False)
        with PUBLIC_IP_PATCH, patch("requests.get", return_value=response):
            result = check_http_uptime("https://example.com/")

        assert result["status"] == CheckResult.Status.OK
        assert result["details"]["status_code"] == 200
        assert result["latency_ms"] is not None

    def test_critical_on_5xx_response(self):
        response = Mock(status_code=503, url="https://example.com/", headers={}, is_redirect=False)
        with PUBLIC_IP_PATCH, patch("requests.get", return_value=response):
            result = check_http_uptime("https://example.com/")

        assert result["status"] == CheckResult.Status.CRITICAL
        assert result["details"]["status_code"] == 503

    def test_critical_on_connection_error(self):
        import requests

        with (
            PUBLIC_IP_PATCH,
            patch("requests.get", side_effect=requests.ConnectionError("refused")),
        ):
            result = check_http_uptime("https://example.com/")

        assert result["status"] == CheckResult.Status.CRITICAL
        assert "refused" in result["details"]["error"]
        assert result["latency_ms"] is None

    def test_critical_on_timeout(self):
        import requests

        with PUBLIC_IP_PATCH, patch("requests.get", side_effect=requests.Timeout("timed out")):
            result = check_http_uptime("https://example.com/")

        assert result["status"] == CheckResult.Status.CRITICAL

    def test_ssrf_target_is_refused_not_fetched(self):
        # 127.0.0.1 resolves instantly (literal IP) — no mocking needed,
        # and requests.get must never be called.
        with patch("requests.get") as mock_get:
            result = check_http_uptime("http://127.0.0.1/admin")

        mock_get.assert_not_called()
        assert result["status"] == CheckResult.Status.CRITICAL
        assert "refus" in result["details"]["error"].lower()

    def test_follows_redirect_and_validates_each_hop(self):
        redirect_response = Mock(
            status_code=302,
            headers={"Location": "https://example.com/final"},
            is_redirect=True,
        )
        final_response = Mock(
            status_code=200, url="https://example.com/final", headers={}, is_redirect=False
        )
        with (
            PUBLIC_IP_PATCH,
            patch("requests.get", side_effect=[redirect_response, final_response]),
        ):
            result = check_http_uptime("https://example.com/")

        assert result["status"] == CheckResult.Status.OK
        assert result["details"]["final_url"] == "https://example.com/final"

    def test_redirect_to_private_ip_is_refused(self):
        redirect_response = Mock(
            status_code=302,
            headers={"Location": "http://127.0.0.1/internal"},
            is_redirect=True,
        )
        with PUBLIC_IP_PATCH, patch("requests.get", return_value=redirect_response) as mock_get:
            result = check_http_uptime("https://example.com/")

        # Only the first (safe) hop should ever have been fetched.
        assert mock_get.call_count == 1
        assert result["status"] == CheckResult.Status.CRITICAL
