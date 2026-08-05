import pyotp
import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import RecoveryCode, TwoFactorCredential

pytestmark = pytest.mark.django_db

PASSWORD = "UnMotDePasseSolide2026"


def _login(api_client, email, password=PASSWORD):
    return api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )


def _auth_headers(access):
    return {"HTTP_AUTHORIZATION": f"Bearer {access}"}


def _enroll(api_client, user_factory):
    user = user_factory(email="user@example.com", password=PASSWORD)
    response = _login(api_client, "user@example.com")
    access = response.data["access"]
    setup_response = api_client.post(reverse("2fa-setup"), **_auth_headers(access))
    return user, access, setup_response.data["secret"]


class TestTwoFactorSetupAndConfirm:
    def test_setup_returns_secret_qr_code_and_otpauth_uri(self, api_client, user_factory):
        _user, _access, secret = _enroll(api_client, user_factory)

        assert secret
        assert TwoFactorCredential.objects.filter(confirmed=False).exists()

    def test_status_is_disabled_before_confirmation(self, api_client, user_factory):
        _user, access, _secret = _enroll(api_client, user_factory)

        response = api_client.get(reverse("2fa-status"), **_auth_headers(access))

        assert response.data["enabled"] is False

    def test_confirm_with_valid_code_activates_2fa_and_issues_recovery_codes(
        self, api_client, user_factory
    ):
        _user, access, secret = _enroll(api_client, user_factory)
        code = pyotp.TOTP(secret).now()

        response = api_client.post(
            reverse("2fa-confirm"), {"code": code}, format="json", **_auth_headers(access)
        )

        assert response.status_code == status.HTTP_201_CREATED
        recovery_codes = response.data["recovery_codes"]
        assert len(recovery_codes) == 10
        assert len(set(recovery_codes)) == 10  # all distinct
        assert TwoFactorCredential.objects.get().confirmed is True
        assert RecoveryCode.objects.count() == 10

        status_response = api_client.get(reverse("2fa-status"), **_auth_headers(access))
        assert status_response.data["enabled"] is True

    def test_confirm_with_invalid_code_does_not_activate(self, api_client, user_factory):
        _user, access, _secret = _enroll(api_client, user_factory)

        response = api_client.post(
            reverse("2fa-confirm"), {"code": "000000"}, format="json", **_auth_headers(access)
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert TwoFactorCredential.objects.get().confirmed is False

    def test_confirm_rejects_malformed_code(self, api_client, user_factory):
        _user, access, _secret = _enroll(api_client, user_factory)

        response = api_client.post(
            reverse("2fa-confirm"), {"code": "not-a-code"}, format="json", **_auth_headers(access)
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


def _enroll_and_confirm(api_client, user_factory, email="user@example.com"):
    user = user_factory(email=email, password=PASSWORD)
    login_response = _login(api_client, email)
    access = login_response.data["access"]
    setup_response = api_client.post(reverse("2fa-setup"), **_auth_headers(access))
    secret = setup_response.data["secret"]
    code = pyotp.TOTP(secret).now()
    confirm_response = api_client.post(
        reverse("2fa-confirm"), {"code": code}, format="json", **_auth_headers(access)
    )
    return user, secret, confirm_response.data["recovery_codes"]


class TestLoginWithTwoFactorEnabled:
    def test_login_returns_challenge_instead_of_tokens(self, api_client, user_factory):
        _user, _secret, _codes = _enroll_and_confirm(api_client, user_factory)

        response = _login(api_client, "user@example.com")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["mfa_required"] is True
        assert "challenge_token" in response.data
        assert "access" not in response.data

    def test_verify_with_valid_totp_code_returns_tokens(self, api_client, user_factory):
        _user, secret, _codes = _enroll_and_confirm(api_client, user_factory)
        challenge_token = _login(api_client, "user@example.com").data["challenge_token"]
        code = pyotp.TOTP(secret).now()

        response = api_client.post(
            reverse("token-verify-2fa"),
            {"challenge_token": challenge_token, "code": code},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["access"]
        assert response.data["refresh"]

    def test_verify_with_wrong_code_fails(self, api_client, user_factory):
        _user, _secret, _codes = _enroll_and_confirm(api_client, user_factory)
        challenge_token = _login(api_client, "user@example.com").data["challenge_token"]

        response = api_client.post(
            reverse("token-verify-2fa"),
            {"challenge_token": challenge_token, "code": "000000"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_verify_with_unknown_challenge_token_fails(self, api_client, user_factory):
        _user, _secret, _codes = _enroll_and_confirm(api_client, user_factory)

        response = api_client.post(
            reverse("token-verify-2fa"),
            {"challenge_token": "bogus-token", "code": "123456"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_verify_with_recovery_code_returns_tokens_and_consumes_it(
        self, api_client, user_factory
    ):
        _user, _secret, recovery_codes = _enroll_and_confirm(api_client, user_factory)
        challenge_token = _login(api_client, "user@example.com").data["challenge_token"]

        response = api_client.post(
            reverse("token-verify-2fa"),
            {"challenge_token": challenge_token, "recovery_code": recovery_codes[0]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert RecoveryCode.objects.filter(used_at__isnull=False).count() == 1

    def test_reused_recovery_code_is_rejected(self, api_client, user_factory):
        _user, _secret, recovery_codes = _enroll_and_confirm(api_client, user_factory)

        first_challenge = _login(api_client, "user@example.com").data["challenge_token"]
        api_client.post(
            reverse("token-verify-2fa"),
            {"challenge_token": first_challenge, "recovery_code": recovery_codes[0]},
            format="json",
        )

        second_challenge = _login(api_client, "user@example.com").data["challenge_token"]
        response = api_client.post(
            reverse("token-verify-2fa"),
            {"challenge_token": second_challenge, "recovery_code": recovery_codes[0]},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_challenge_token_is_single_use(self, api_client, user_factory):
        _user, secret, _codes = _enroll_and_confirm(api_client, user_factory)
        challenge_token = _login(api_client, "user@example.com").data["challenge_token"]
        code = pyotp.TOTP(secret).now()

        first = api_client.post(
            reverse("token-verify-2fa"),
            {"challenge_token": challenge_token, "code": code},
            format="json",
        )
        assert first.status_code == status.HTTP_200_OK

        second = api_client.post(
            reverse("token-verify-2fa"),
            {"challenge_token": challenge_token, "code": code},
            format="json",
        )
        assert second.status_code == status.HTTP_401_UNAUTHORIZED


class TestDisableTwoFactor:
    def test_disable_removes_credential_and_recovery_codes(self, api_client, user_factory):
        user, secret, _codes = _enroll_and_confirm(api_client, user_factory)
        challenge_token = _login(api_client, "user@example.com").data["challenge_token"]
        code = pyotp.TOTP(secret).now()
        tokens = api_client.post(
            reverse("token-verify-2fa"),
            {"challenge_token": challenge_token, "code": code},
            format="json",
        ).data
        access = tokens["access"]

        wrong_password_response = api_client.post(
            reverse("2fa-disable"),
            {"password": "mauvais-mot-de-passe"},
            format="json",
            **_auth_headers(access),
        )
        assert wrong_password_response.status_code == status.HTTP_400_BAD_REQUEST
        assert TwoFactorCredential.objects.filter(user=user, confirmed=True).exists()

        response = api_client.post(
            reverse("2fa-disable"), {"password": PASSWORD}, format="json", **_auth_headers(access)
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not TwoFactorCredential.objects.filter(user=user).exists()
        assert not RecoveryCode.objects.filter(user=user).exists()

        # 2FA is now off: logging in returns tokens directly again.
        login_response = _login(api_client, "user@example.com")
        assert login_response.data.get("mfa_required") is None
        assert login_response.data["access"]
