from datetime import time

import pytest
from django.core import mail
from django.utils import timezone

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Alert, Asset, CheckResult
from apps.notifications import services
from apps.notifications.models import EmailLog, NotificationPreferences
from apps.tenants.models import Membership

pytestmark = pytest.mark.django_db


@pytest.fixture
def website_asset(tenant, tenant_owner):
    return monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://example.com",
        ownership_confirmed=True,
    )


class TestPreferences:
    def test_get_or_create_returns_sane_defaults(self, tenant):
        prefs = services.get_or_create_preferences(tenant)
        assert prefs.weather_enabled is True
        assert prefs.realtime_alerts_enabled is True
        assert prefs.weather_time == time(8, 0)

    def test_get_or_create_is_idempotent(self, tenant):
        first = services.get_or_create_preferences(tenant)
        second = services.get_or_create_preferences(tenant)
        assert first.id == second.id
        assert NotificationPreferences.all_objects.filter(tenant=tenant).count() == 1

    def test_update_preferences(self, tenant):
        services.update_preferences(tenant, weather_time=time(7, 30), weather_enabled=False)
        prefs = services.get_or_create_preferences(tenant)
        assert prefs.weather_time == time(7, 30)
        assert prefs.weather_enabled is False


class TestListPreferencesDueForWeather:
    def test_matches_same_hour_and_15_minute_bucket(self, tenant):
        services.update_preferences(tenant, weather_time=time(8, 5))
        now = timezone.now().replace(hour=8, minute=10)

        due = services.list_preferences_due_for_weather(now)

        assert any(p.tenant_id == tenant.id for p in due)

    def test_does_not_match_a_different_bucket(self, tenant):
        services.update_preferences(tenant, weather_time=time(8, 5))
        now = timezone.now().replace(hour=8, minute=20)  # bucket 1 vs bucket 0

        due = services.list_preferences_due_for_weather(now)

        assert not any(p.tenant_id == tenant.id for p in due)

    def test_disabled_weather_is_never_due(self, tenant):
        services.update_preferences(tenant, weather_time=time(8, 5), weather_enabled=False)
        now = timezone.now().replace(hour=8, minute=5)

        due = services.list_preferences_due_for_weather(now)

        assert not any(p.tenant_id == tenant.id for p in due)


class TestBuildWeatherContext:
    def test_mood_is_sunny_when_everything_is_ok(self, tenant, website_asset):
        CheckResult.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            check_type=CheckResult.CheckType.HTTP_UPTIME,
            status=CheckResult.Status.OK,
        )

        context = services.build_weather_context(tenant)

        assert context["mood_emoji"] == "☀️"
        assert context["open_alerts"] == []

    def test_mood_is_critical_when_a_critical_alert_is_open(self, tenant, website_asset):
        CheckResult.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            check_type=CheckResult.CheckType.HTTP_UPTIME,
            status=CheckResult.Status.OK,
        )
        Alert.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )

        context = services.build_weather_context(tenant)

        assert context["mood_emoji"] == "🔴"
        assert len(context["open_alerts"]) == 1

    def test_mood_is_warning_from_a_check_status_alone(self, tenant, website_asset):
        CheckResult.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            check_type=CheckResult.CheckType.SECURITY_HEADERS,
            status=CheckResult.Status.WARNING,
        )

        context = services.build_weather_context(tenant)

        assert context["mood_emoji"] == "⚠️"


class TestSendWeatherEmail:
    def test_sends_to_tenant_admins_only(self, tenant, tenant_owner, user_factory):
        contributor = user_factory(email="contributor@example.com")
        Membership.all_objects.create(
            tenant=tenant, user=contributor, role=Membership.Role.CONTRIBUTOR
        )

        services.send_weather_email(tenant)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [tenant_owner.email]

    def test_is_idempotent_within_the_same_day(self, tenant, tenant_owner):
        services.send_weather_email(tenant)
        services.send_weather_email(tenant)

        assert len(mail.outbox) == 1
        assert EmailLog.all_objects.filter(tenant=tenant, kind=EmailLog.Kind.WEATHER).count() == 1

    def test_no_admin_recipients_sends_nothing(self, tenant, tenant_owner):
        Membership.all_objects.filter(tenant=tenant, user=tenant_owner).update(
            role=Membership.Role.READER
        )

        result = services.send_weather_email(tenant)

        assert result is None
        assert len(mail.outbox) == 0

    def test_subject_carries_the_mood_emoji(self, tenant, tenant_owner, website_asset):
        Alert.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )

        services.send_weather_email(tenant)

        assert "🔴" in mail.outbox[0].subject


class TestSendRealtimeAlertEmail:
    def test_sends_when_enabled(self, tenant, tenant_owner, website_asset):
        alert = Alert.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )

        services.send_realtime_alert_email(alert)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [tenant_owner.email]

    def test_skips_when_disabled(self, tenant, tenant_owner, website_asset):
        services.update_preferences(tenant, realtime_alerts_enabled=False)
        alert = Alert.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )

        result = services.send_realtime_alert_email(alert)

        assert result is None
        assert len(mail.outbox) == 0
