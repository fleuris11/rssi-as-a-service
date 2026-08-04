from unittest.mock import Mock, patch

from apps.monitoring.checks.security_headers import check_security_headers
from apps.monitoring.models import CheckResult

from ._helpers import patch_public_dns

PUBLIC_IP_PATCH = patch_public_dns()

ALL_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000",
    "Content-Security-Policy": "default-src 'self'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}


class TestCheckSecurityHeaders:
    def test_ok_when_all_headers_present(self):
        response = Mock(status_code=200, headers=ALL_HEADERS, is_redirect=False)
        with PUBLIC_IP_PATCH, patch("requests.get", return_value=response):
            result = check_security_headers("https://example.com/")

        assert result["status"] == CheckResult.Status.OK
        assert result["details"]["missing"] == []
        assert set(result["details"]["present"]) == set(ALL_HEADERS)

    def test_warning_with_a_recommendation_per_missing_header(self):
        headers = {"X-Frame-Options": "DENY"}
        response = Mock(status_code=200, headers=headers, is_redirect=False)
        with PUBLIC_IP_PATCH, patch("requests.get", return_value=response):
            result = check_security_headers("https://example.com/")

        assert result["status"] == CheckResult.Status.WARNING
        missing_names = {m["header"] for m in result["details"]["missing"]}
        assert missing_names == {
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "X-Content-Type-Options",
        }
        for entry in result["details"]["missing"]:
            assert entry["recommendation"]  # never empty

    def test_ssrf_target_is_refused_not_fetched(self):
        with patch("requests.get") as mock_get:
            result = check_security_headers("http://10.0.0.5/")

        mock_get.assert_not_called()
        assert result["status"] == CheckResult.Status.CRITICAL
