"""Unit tests for apps.monitoring.services: asset CRUD, due-check
selection, and — the most safety-critical part — the alert engine (3-strikes
DOWN confirmation, SSL 30/14/7 thresholds, auto-resolve, no duplicate open
alert).
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.monitoring import services
from apps.monitoring.models import Alert, Asset, CheckResult

pytestmark = pytest.mark.django_db


@pytest.fixture
def website_asset(tenant, tenant_owner):
    return services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://example.com",
        ownership_confirmed=True,
    )


def _record(asset, check_type, status, details=None, minutes_ago=0):
    result = CheckResult.all_objects.create(
        tenant=asset.tenant,
        asset=asset,
        check_type=check_type,
        status=status,
        details=details or {},
    )
    if minutes_ago:
        CheckResult.all_objects.filter(id=result.id).update(
            checked_at=timezone.now() - timedelta(minutes=minutes_ago)
        )
        result.refresh_from_db()
    return result


class TestCreateAsset:
    def test_requires_ownership_confirmed(self, tenant, tenant_owner):
        with pytest.raises(services.InvalidAssetError):
            services.create_asset(
                tenant=tenant,
                user=tenant_owner,
                type=Asset.Type.WEBSITE,
                value="https://example.com",
                ownership_confirmed=False,
            )
        assert Asset.all_objects.count() == 0

    def test_creates_when_confirmed(self, tenant, tenant_owner):
        asset = services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.WEBSITE,
            value="https://example.com",
            ownership_confirmed=True,
        )
        assert asset.ownership_confirmed is True
        assert asset.tenant_id == tenant.id


class TestListDueAssets:
    def test_never_checked_asset_is_due(self, website_asset):
        due = services.list_due_assets(CheckResult.CheckType.HTTP_UPTIME)
        assert website_asset in due

    def test_recently_checked_asset_is_not_due(self, website_asset):
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.OK)
        due = services.list_due_assets(CheckResult.CheckType.HTTP_UPTIME)
        assert website_asset not in due

    def test_stale_check_makes_it_due_again(self, website_asset):
        _record(
            website_asset,
            CheckResult.CheckType.HTTP_UPTIME,
            CheckResult.Status.OK,
            minutes_ago=10,  # interval is 5 minutes
        )
        due = services.list_due_assets(CheckResult.CheckType.HTTP_UPTIME)
        assert website_asset in due

    def test_inactive_asset_is_never_due(self, website_asset):
        services.set_asset_active(website_asset, False)
        due = services.list_due_assets(CheckResult.CheckType.HTTP_UPTIME)
        assert website_asset not in due

    def test_email_check_does_not_apply_to_website_assets(self, website_asset):
        due = services.list_due_assets(CheckResult.CheckType.EMAIL_DNS)
        assert website_asset not in due


class TestDownAlertConfirmation:
    """CLAUDE.md: "confirmer un DOWN par 3 échecs consécutifs"."""

    def test_one_failure_does_not_open_an_alert(self, website_asset):
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.CRITICAL)
        alert = services._evaluate_down_alert(website_asset)

        assert alert is None
        assert not Alert.all_objects.filter(asset=website_asset, is_open=True).exists()

    def test_two_failures_do_not_open_an_alert(self, website_asset):
        for _ in range(2):
            _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.CRITICAL)
        alert = services._evaluate_down_alert(website_asset)

        assert alert is None
        assert not Alert.all_objects.filter(asset=website_asset, is_open=True).exists()

    def test_three_consecutive_failures_open_a_critical_alert(self, website_asset):
        for _ in range(3):
            _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.CRITICAL)
        alert = services._evaluate_down_alert(website_asset)

        assert alert is not None
        assert alert.alert_type == Alert.AlertType.DOWN
        assert alert.severity == Alert.Severity.CRITICAL
        assert alert.is_open is True

    def test_a_single_ok_amid_failures_resets_the_streak(self, website_asset):
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.CRITICAL)
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.OK)
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.CRITICAL)
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.CRITICAL)
        alert = services._evaluate_down_alert(website_asset)

        # Latest 3 are [CRITICAL, CRITICAL, OK] in recency order -> not all critical.
        assert alert is None

    def test_does_not_duplicate_an_already_open_alert(self, website_asset):
        for _ in range(3):
            _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.CRITICAL)
        first = services._evaluate_down_alert(website_asset)
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.CRITICAL)
        second = services._evaluate_down_alert(website_asset)

        assert first is not None
        assert second is None  # already open, no re-notification
        assert Alert.all_objects.filter(asset=website_asset, is_open=True).count() == 1

    def test_recovery_resolves_the_open_alert(self, website_asset):
        for _ in range(3):
            _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.CRITICAL)
        services._evaluate_down_alert(website_asset)

        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.OK)
        services._evaluate_down_alert(website_asset)

        alert = Alert.all_objects.get(asset=website_asset, alert_type=Alert.AlertType.DOWN)
        assert alert.is_open is False
        assert alert.resolved_at is not None


class TestSslExpiringAlert:
    def test_no_alert_when_far_from_expiry(self, website_asset):
        result = _record(
            website_asset,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.Status.OK,
            details={"days_left": 90},
        )
        alert = services._evaluate_ssl_alert(website_asset, result)
        assert alert is None

    def test_crossing_30_days_opens_a_warning_alert(self, website_asset):
        result = _record(
            website_asset,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.Status.WARNING,
            details={"days_left": 29, "expires_at": "2027-01-01T00:00:00+00:00"},
        )
        alert = services._evaluate_ssl_alert(website_asset, result)

        assert alert is not None
        assert alert.severity == Alert.Severity.WARNING
        assert alert.details["notified_thresholds"] == [30]

    def test_crossing_14_then_7_days_notifies_again_each_time(self, website_asset):
        result_30 = _record(
            website_asset,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.Status.WARNING,
            details={"days_left": 25},
        )
        services._evaluate_ssl_alert(website_asset, result_30)

        result_14 = _record(
            website_asset,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.Status.WARNING,
            details={"days_left": 13},
        )
        alert_14 = services._evaluate_ssl_alert(website_asset, result_14)
        assert alert_14 is not None
        assert alert_14.details["notified_thresholds"] == [14, 30]

        result_still_13 = _record(
            website_asset,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.Status.WARNING,
            details={"days_left": 12},
        )
        alert_no_new_threshold = services._evaluate_ssl_alert(website_asset, result_still_13)
        assert alert_no_new_threshold is None  # still within the 14-day bucket, no re-notify

        result_7 = _record(
            website_asset,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.Status.CRITICAL,
            details={"days_left": 6},
        )
        alert_7 = services._evaluate_ssl_alert(website_asset, result_7)
        assert alert_7 is not None
        assert alert_7.severity == Alert.Severity.CRITICAL
        assert alert_7.details["notified_thresholds"] == [7, 14, 30]

        # Still one Alert row throughout, never duplicated.
        assert Alert.all_objects.filter(asset=website_asset, is_open=True).count() == 1

    def test_renewal_resolves_the_alert(self, website_asset):
        result = _record(
            website_asset,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.Status.WARNING,
            details={"days_left": 10},
        )
        services._evaluate_ssl_alert(website_asset, result)

        renewed = _record(
            website_asset,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.Status.OK,
            details={"days_left": 365},
        )
        services._evaluate_ssl_alert(website_asset, renewed)

        alert = Alert.all_objects.get(asset=website_asset, alert_type=Alert.AlertType.SSL_EXPIRING)
        assert alert.is_open is False

    def test_no_alert_when_cert_fetch_failed(self, website_asset):
        result = _record(
            website_asset,
            CheckResult.CheckType.SSL_CERTIFICATE,
            CheckResult.Status.CRITICAL,
            details={"error": "connection refused"},
        )
        alert = services._evaluate_ssl_alert(website_asset, result)
        assert alert is None


class TestSecurityHeadersAlert:
    def test_missing_headers_open_a_warning_alert(self, website_asset):
        result = _record(
            website_asset,
            CheckResult.CheckType.SECURITY_HEADERS,
            CheckResult.Status.WARNING,
            details={"missing": [{"header": "Content-Security-Policy", "recommendation": "..."}]},
        )
        alert = services._evaluate_headers_alert(website_asset, result)
        assert alert is not None
        assert alert.severity == Alert.Severity.WARNING

    def test_no_missing_headers_resolves_open_alert(self, website_asset):
        bad = _record(
            website_asset,
            CheckResult.CheckType.SECURITY_HEADERS,
            CheckResult.Status.WARNING,
            details={"missing": [{"header": "X-Frame-Options", "recommendation": "..."}]},
        )
        services._evaluate_headers_alert(website_asset, bad)

        good = _record(
            website_asset,
            CheckResult.CheckType.SECURITY_HEADERS,
            CheckResult.Status.OK,
            details={"missing": []},
        )
        services._evaluate_headers_alert(website_asset, good)

        alert = Alert.all_objects.get(
            asset=website_asset, alert_type=Alert.AlertType.SECURITY_HEADERS
        )
        assert alert.is_open is False


class TestEmailMisconfiguredAlert:
    @pytest.fixture
    def email_asset(self, tenant, tenant_owner):
        return services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="example.com",
            ownership_confirmed=True,
        )

    def test_issues_open_an_alert_with_matching_severity(self, email_asset):
        result = _record(
            email_asset,
            CheckResult.CheckType.EMAIL_DNS,
            CheckResult.Status.CRITICAL,
            details={"issues": [{"type": "spf_missing", "message": "..."}]},
        )
        alert = services._evaluate_email_alert(email_asset, result)
        assert alert is not None
        assert alert.severity == Alert.Severity.CRITICAL

    def test_no_issues_resolves_open_alert(self, email_asset):
        bad = _record(
            email_asset,
            CheckResult.CheckType.EMAIL_DNS,
            CheckResult.Status.WARNING,
            details={"issues": [{"type": "dmarc_missing", "message": "..."}]},
        )
        services._evaluate_email_alert(email_asset, bad)

        good = _record(
            email_asset,
            CheckResult.CheckType.EMAIL_DNS,
            CheckResult.Status.OK,
            details={"issues": []},
        )
        services._evaluate_email_alert(email_asset, good)

        alert = Alert.all_objects.get(
            asset=email_asset, alert_type=Alert.AlertType.EMAIL_MISCONFIGURED
        )
        assert alert.is_open is False


class TestNoDuplicateOpenAlert:
    def test_db_constraint_prevents_two_open_alerts_same_type(self, website_asset):
        Alert.all_objects.create(
            tenant=website_asset.tenant,
            asset=website_asset,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Alert.all_objects.create(
                tenant=website_asset.tenant,
                asset=website_asset,
                alert_type=Alert.AlertType.DOWN,
                severity=Alert.Severity.CRITICAL,
            )


class TestUptimePercentage:
    def test_none_without_any_checks(self, website_asset):
        assert services.compute_uptime_percentage(website_asset) is None

    def test_computes_percentage_of_ok_checks(self, website_asset):
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.OK)
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.OK)
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.OK)
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.CRITICAL)

        assert services.compute_uptime_percentage(website_asset) == 75.0

    def test_ignores_checks_outside_the_window(self, website_asset):
        _record(
            website_asset,
            CheckResult.CheckType.HTTP_UPTIME,
            CheckResult.Status.CRITICAL,
            minutes_ago=60 * 30,
        )
        _record(website_asset, CheckResult.CheckType.HTTP_UPTIME, CheckResult.Status.OK)

        assert services.compute_uptime_percentage(website_asset, hours=24) == 100.0
