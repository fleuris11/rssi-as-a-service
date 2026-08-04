from datetime import time
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Alert, Asset
from apps.notifications import services, tasks

pytestmark = pytest.mark.django_db


class TestSendDueWeatherEmails:
    def test_dispatches_one_task_per_due_tenant(self, tenant):
        now = timezone.localtime()
        services.update_preferences(tenant, weather_time=time(now.hour, now.minute))

        with patch("apps.notifications.tasks.send_weather_email_for_tenant.delay") as mock_delay:
            dispatched = tasks.send_due_weather_emails()

        assert dispatched == 1
        mock_delay.assert_called_once_with(tenant.id)

    def test_dispatches_nothing_when_no_tenant_is_due(self, tenant):
        services.update_preferences(tenant, weather_time=time(3, 0))
        now = timezone.localtime().replace(hour=14, minute=0)

        with patch("django.utils.timezone.localtime", return_value=now):
            with patch(
                "apps.notifications.tasks.send_weather_email_for_tenant.delay"
            ) as mock_delay:
                tasks.send_due_weather_emails()

        mock_delay.assert_not_called()


class TestSendWeatherEmailForTenant:
    def test_sends_the_email(self, tenant, tenant_owner):
        result = tasks.send_weather_email_for_tenant(tenant.id)

        assert result is True
        assert len(mail.outbox) == 1

    def test_unknown_tenant_is_a_no_op(self):
        result = tasks.send_weather_email_for_tenant(999999)
        assert result is None
        assert len(mail.outbox) == 0


class TestSendRealtimeAlertEmailTask:
    @pytest.fixture
    def website_asset(self, tenant, tenant_owner):
        return monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.WEBSITE,
            value="https://example.com",
            ownership_confirmed=True,
        )

    def test_sends_for_a_known_alert(self, tenant, tenant_owner, website_asset):
        alert = Alert.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )

        result = tasks.send_realtime_alert_email(alert.id)

        assert result is True
        assert len(mail.outbox) == 1

    def test_unknown_alert_is_a_no_op(self):
        result = tasks.send_realtime_alert_email(999999)
        assert result is None
        assert len(mail.outbox) == 0
