from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts import services

pytestmark = pytest.mark.django_db

PASSWORD = "UnMotDePasseSolide2026"


def _login(api_client, email, password):
    return api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )


class TestNonEnumeratingErrors:
    def test_wrong_password_and_unknown_email_give_the_same_message(self, api_client, user_factory):
        user_factory(email="reelle@example.com", password=PASSWORD)

        wrong_password = _login(api_client, "reelle@example.com", "mauvais-mot-de-passe")
        unknown_email = _login(api_client, "inconnu@example.com", "peu-importe-1234")

        assert (
            wrong_password.status_code == unknown_email.status_code == status.HTTP_401_UNAUTHORIZED
        )
        assert wrong_password.data["detail"] == unknown_email.data["detail"]

    def test_registration_duplicate_email_message_does_not_confirm_existence(
        self, api_client, user_factory
    ):
        user_factory(email="deja-la@example.com", password=PASSWORD)

        response = api_client.post(
            reverse("auth-register"),
            {
                "email": "deja-la@example.com",
                "password": "UnAutreMotDePasse2026",
                "company_name": "Autre Entreprise",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        message = str(response.data["email"][0])
        assert "existe déjà" not in message.lower()
        assert "already exists" not in message.lower()


class TestProgressiveLockout:
    def test_account_is_locked_after_repeated_failures(self, api_client, user_factory):
        user_factory(email="cible@example.com", password=PASSWORD)

        for _ in range(5):
            response = _login(api_client, "cible@example.com", "mauvais-mot-de-passe")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

        locked_response = _login(api_client, "cible@example.com", "mauvais-mot-de-passe")
        assert locked_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # Even the CORRECT password is rejected while locked out — the
        # lockout blocks the account outright, it doesn't just keep
        # re-checking credentials.
        still_locked = _login(api_client, "cible@example.com", PASSWORD)
        assert still_locked.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_lockout_trigger_is_logged_without_the_raw_identifier(self, api_client, user_factory):
        user_factory(email="journalise@example.com", password=PASSWORD)

        with patch.object(services, "security_logger") as mock_logger:
            for _ in range(5):
                _login(api_client, "journalise@example.com", "mauvais-mot-de-passe")

        assert mock_logger.warning.called
        logged_args = [call.args for call in mock_logger.warning.call_args_list]
        assert any("Verrouillage progressif déclenché" in args[0] for args in logged_args)
        assert not any("journalise@example.com" in str(arg) for args in logged_args for arg in args)

    def test_successful_login_clears_the_failure_counter(self, api_client, user_factory):
        user_factory(email="cible2@example.com", password=PASSWORD)

        for _ in range(3):
            _login(api_client, "cible2@example.com", "mauvais-mot-de-passe")

        ok_response = _login(api_client, "cible2@example.com", PASSWORD)
        assert ok_response.status_code == status.HTTP_200_OK

        services.check_not_locked_out(email="cible2@example.com", ip="127.0.0.1")  # no raise

    def test_lockout_is_scoped_per_account_and_ip_not_global(self, api_client, user_factory):
        user_factory(email="victime@example.com", password=PASSWORD)
        user_factory(email="autre@example.com", password=PASSWORD)

        # Attacker floods "victime" from one IP...
        for _ in range(6):
            api_client.post(
                reverse("token-obtain-pair"),
                {"email": "victime@example.com", "password": "mauvais-mot-de-passe"},
                format="json",
                REMOTE_ADDR="10.0.0.1",
            )

        # ...a different account, logging in correctly from a different IP,
        # is unaffected: neither its own account counter nor its own IP
        # counter ever recorded a failure.
        other_account_response = api_client.post(
            reverse("token-obtain-pair"),
            {"email": "autre@example.com", "password": PASSWORD},
            format="json",
            REMOTE_ADDR="10.0.0.2",
        )
        assert other_account_response.status_code == status.HTTP_200_OK

        # The targeted account is locked even from a fresh IP (account-scoped).
        victim_from_elsewhere = api_client.post(
            reverse("token-obtain-pair"),
            {"email": "victime@example.com", "password": PASSWORD},
            format="json",
            REMOTE_ADDR="10.0.0.3",
        )
        assert victim_from_elsewhere.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestAuthEndpointThrottling:
    def test_register_endpoint_returns_429_after_the_limit(self, api_client):
        for i in range(10):
            api_client.post(
                reverse("auth-register"),
                {
                    "email": f"rate-{i}@example.com",
                    "password": "UnMotDePasseSolide2026",
                    "company_name": "Entreprise",
                },
                format="json",
            )

        response = api_client.post(
            reverse("auth-register"),
            {
                "email": "rate-overflow@example.com",
                "password": "UnMotDePasseSolide2026",
                "company_name": "Entreprise",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_login_endpoint_returns_429_after_the_limit(self, api_client, user_factory):
        # Uses the CORRECT password every time, on purpose: a successful
        # login clears the lockout counters instead of feeding them, which
        # isolates the throttle (10/min per IP) from the separate
        # progressive-lockout mechanism (covered by TestProgressiveLockout)
        # — otherwise the lockout would trip first, for a different reason.
        user_factory(email="throttle-target@example.com", password=PASSWORD)

        for _ in range(10):
            ok_response = _login(api_client, "throttle-target@example.com", PASSWORD)
            assert ok_response.status_code == status.HTTP_200_OK

        response = _login(api_client, "throttle-target@example.com", PASSWORD)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
