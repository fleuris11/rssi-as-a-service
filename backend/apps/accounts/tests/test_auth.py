import pytest
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.django_db


def _obtain_tokens(api_client, email, password):
    url = reverse("token-obtain-pair")
    response = api_client.post(url, {"email": email, "password": password}, format="json")
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"], response.data["refresh"]


def test_token_obtain_pair_returns_access_and_refresh(api_client, user_factory):
    user_factory(email="user@example.com", password="UnMotDePasseSolide2026")

    access, refresh = _obtain_tokens(api_client, "user@example.com", "UnMotDePasseSolide2026")

    assert access
    assert refresh


def test_token_obtain_pair_rejects_wrong_password(api_client, user_factory):
    user_factory(email="user@example.com", password="UnMotDePasseSolide2026")
    url = reverse("token-obtain-pair")

    response = api_client.post(
        url, {"email": "user@example.com", "password": "mauvais-mot-de-passe"}, format="json"
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_token_refresh_rotates_and_blacklists_old_refresh_token(api_client, user_factory):
    user_factory(email="user@example.com", password="UnMotDePasseSolide2026")
    _access, refresh = _obtain_tokens(api_client, "user@example.com", "UnMotDePasseSolide2026")
    refresh_url = reverse("token-refresh")

    first_refresh_response = api_client.post(refresh_url, {"refresh": refresh}, format="json")
    assert first_refresh_response.status_code == status.HTTP_200_OK
    new_refresh = first_refresh_response.data["refresh"]
    assert new_refresh != refresh

    reuse_response = api_client.post(refresh_url, {"refresh": refresh}, format="json")
    assert reuse_response.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_endpoint_requires_authentication(api_client):
    url = reverse("auth-me")

    response = api_client.get(url)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_endpoint_returns_user_and_memberships(api_client, user_factory, tenant_factory):
    user = user_factory(email="user@example.com", password="UnMotDePasseSolide2026")
    tenant_factory(user, name="Entreprise de Test")
    access, _refresh = _obtain_tokens(api_client, "user@example.com", "UnMotDePasseSolide2026")
    url = reverse("auth-me")

    response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {access}")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == "user@example.com"
    assert response.data["memberships"][0]["tenant_name"] == "Entreprise de Test"
    assert response.data["memberships"][0]["role"] == "admin"
