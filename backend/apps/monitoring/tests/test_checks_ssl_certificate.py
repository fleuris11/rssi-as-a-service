from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from apps.monitoring.checks.ssl_certificate import check_ssl_certificate
from apps.monitoring.models import CheckResult

from ._helpers import patch_public_dns

PUBLIC_IP_PATCH = patch_public_dns()


def _fake_cert(days_from_now):
    not_after = datetime.now(UTC) + timedelta(days=days_from_now)
    return {
        "notAfter": not_after.strftime("%b %d %H:%M:%S %Y GMT"),
        "issuer": ((("organizationName", "Let's Encrypt"),),),
    }


def _mock_context_manager(return_value):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=return_value)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _patched_connection(cert):
    ssl_socket = _mock_context_manager(MagicMock(getpeercert=MagicMock(return_value=cert)))
    raw_socket = _mock_context_manager(MagicMock())
    ssl_context = MagicMock()
    ssl_context.wrap_socket.return_value = ssl_socket
    return (
        patch("socket.create_connection", return_value=raw_socket),
        patch("ssl.create_default_context", return_value=ssl_context),
    )


class TestCheckSslCertificate:
    def test_ok_when_far_from_expiry(self):
        conn_patch, ctx_patch = _patched_connection(_fake_cert(90))
        with PUBLIC_IP_PATCH, conn_patch, ctx_patch:
            result = check_ssl_certificate("example.com")

        assert result["status"] == CheckResult.Status.OK
        # 89 or 90 depending on the sub-second gap between building the
        # fake cert and the check computing "now" itself.
        assert result["details"]["days_left"] in (89, 90)
        assert result["details"]["issuer"] == "Let's Encrypt"

    def test_warning_within_30_days(self):
        conn_patch, ctx_patch = _patched_connection(_fake_cert(14))
        with PUBLIC_IP_PATCH, conn_patch, ctx_patch:
            result = check_ssl_certificate("example.com")

        assert result["status"] == CheckResult.Status.WARNING
        assert result["details"]["days_left"] in (13, 14)

    def test_critical_when_already_expired(self):
        conn_patch, ctx_patch = _patched_connection(_fake_cert(-5))
        with PUBLIC_IP_PATCH, conn_patch, ctx_patch:
            result = check_ssl_certificate("example.com")

        assert result["status"] == CheckResult.Status.CRITICAL
        assert result["details"]["days_left"] < 0

    def test_critical_on_connection_failure(self):
        with PUBLIC_IP_PATCH, patch("socket.create_connection", side_effect=OSError("refused")):
            result = check_ssl_certificate("example.com")

        assert result["status"] == CheckResult.Status.CRITICAL
        assert "refused" in result["details"]["error"]

    def test_ssrf_target_is_refused_not_connected(self):
        with patch("socket.create_connection") as mock_connect:
            result = check_ssl_certificate("127.0.0.1")

        mock_connect.assert_not_called()
        assert result["status"] == CheckResult.Status.CRITICAL
