import base64
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.threat_intelligence.models import BreachFinding, MonitoredAsset

pytestmark = pytest.mark.django_db


def _basic_auth_header(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


class TestWebhookAuth:
    def test_missing_authorization_header_rejected(self, api_client, settings):
        settings.BREACHSENSE_WEBHOOK_USERNAME = "wh_user"
        settings.BREACHSENSE_WEBHOOK_PASSWORD = "wh_pass"

        response = api_client.post(reverse("breachsense-webhook"), [], format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response["WWW-Authenticate"] == 'Basic realm="breachsense-webhook"'

    def test_wrong_credentials_rejected(self, api_client, settings):
        settings.BREACHSENSE_WEBHOOK_USERNAME = "wh_user"
        settings.BREACHSENSE_WEBHOOK_PASSWORD = "wh_pass"

        response = api_client.post(
            reverse("breachsense-webhook"),
            [],
            format="json",
            HTTP_AUTHORIZATION=_basic_auth_header("wh_user", "wrong-password"),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_credentials_not_configured_always_rejects(self, api_client, settings):
        settings.BREACHSENSE_WEBHOOK_USERNAME = ""
        settings.BREACHSENSE_WEBHOOK_PASSWORD = ""

        response = api_client.post(
            reverse("breachsense-webhook"),
            [],
            format="json",
            HTTP_AUTHORIZATION=_basic_auth_header("anything", "anything"),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_correct_credentials_accepted(self, api_client, settings):
        settings.BREACHSENSE_WEBHOOK_USERNAME = "wh_user"
        settings.BREACHSENSE_WEBHOOK_PASSWORD = "wh_pass"

        response = api_client.post(
            reverse("breachsense-webhook"),
            [],
            format="json",
            HTTP_AUTHORIZATION=_basic_auth_header("wh_user", "wh_pass"),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_non_list_body_rejected(self, api_client, settings):
        settings.BREACHSENSE_WEBHOOK_USERNAME = "wh_user"
        settings.BREACHSENSE_WEBHOOK_PASSWORD = "wh_pass"

        response = api_client.post(
            reverse("breachsense-webhook"),
            {"not": "a list"},
            format="json",
            HTTP_AUTHORIZATION=_basic_auth_header("wh_user", "wh_pass"),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestWebhookIngestionEndToEnd:
    def test_valid_payload_creates_finding(
        self, api_client, tenant, website_asset, fake_provider, settings
    ):
        settings.BREACHSENSE_WEBHOOK_USERNAME = "wh_user"
        settings.BREACHSENSE_WEBHOOK_PASSWORD = "wh_pass"
        MonitoredAsset.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            provider_ref="example.com",
            provider_asset_type="domain",
        )
        payload = [
            {"ast": "example.com", "api": "stealer", "email": "a@example.com", "password": "x"}
        ]

        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            response = api_client.post(
                reverse("breachsense-webhook"),
                payload,
                format="json",
                HTTP_AUTHORIZATION=_basic_auth_header("wh_user", "wh_pass"),
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["findings_created"] == 1
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1

    def test_redelivered_payload_is_idempotent(
        self, api_client, tenant, website_asset, fake_provider, settings
    ):
        settings.BREACHSENSE_WEBHOOK_USERNAME = "wh_user"
        settings.BREACHSENSE_WEBHOOK_PASSWORD = "wh_pass"
        MonitoredAsset.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            provider_ref="example.com",
            provider_asset_type="domain",
        )
        payload = [
            {"ast": "example.com", "api": "stealer", "email": "a@example.com", "id": "stable-id"}
        ]

        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            api_client.post(
                reverse("breachsense-webhook"),
                payload,
                format="json",
                HTTP_AUTHORIZATION=_basic_auth_header("wh_user", "wh_pass"),
            )
            response = api_client.post(
                reverse("breachsense-webhook"),
                payload,
                format="json",
                HTTP_AUTHORIZATION=_basic_auth_header("wh_user", "wh_pass"),
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["findings_created"] == 0
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 1

    def test_no_csrf_token_required(self, tenant, website_asset, fake_provider, settings):
        """The webhook is an external, unauthenticated-by-session endpoint —
        must not require a CSRF token (Django's ``enforce_csrf_checks``
        client simulates a real browser-style CSRF check)."""
        from django.test import Client

        settings.BREACHSENSE_WEBHOOK_USERNAME = "wh_user"
        settings.BREACHSENSE_WEBHOOK_PASSWORD = "wh_pass"
        MonitoredAsset.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            provider_ref="example.com",
            provider_asset_type="domain",
        )
        csrf_enforcing_client = Client(enforce_csrf_checks=True)

        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            response = csrf_enforcing_client.post(
                reverse("breachsense-webhook"),
                data=[{"ast": "example.com", "api": "stealer", "email": "a@example.com"}],
                content_type="application/json",
                HTTP_AUTHORIZATION=_basic_auth_header("wh_user", "wh_pass"),
            )

        assert response.status_code == status.HTTP_200_OK
