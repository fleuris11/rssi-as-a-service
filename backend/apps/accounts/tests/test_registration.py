import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.tenants.models import Membership

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_register_creates_user_and_admin_membership(api_client):
    url = reverse("auth-register")
    payload = {
        "email": "diregeante@example.com",
        "password": "UnMotDePasseSolide2026",
        "first_name": "Alex",
        "last_name": "Martin",
        "company_name": "Cabinet Comptable Martin",
    }

    response = api_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email="diregeante@example.com")
    assert user.check_password(payload["password"])

    membership = Membership.all_objects.get(user=user)
    assert membership.role == Membership.Role.ADMIN
    assert membership.tenant.name == "Cabinet Comptable Martin"

    assert response.data["memberships"][0]["role"] == Membership.Role.ADMIN
    assert "password" not in response.data


def test_register_rejects_duplicate_email(api_client, user_factory):
    user_factory(email="deja-inscrit@example.com")
    url = reverse("auth-register")
    payload = {
        "email": "deja-inscrit@example.com",
        "password": "UnMotDePasseSolide2026",
        "company_name": "Autre Entreprise",
    }

    response = api_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


def test_register_rejects_weak_password(api_client):
    url = reverse("auth-register")
    payload = {
        "email": "faible@example.com",
        "password": "1234",
        "company_name": "Entreprise Faible",
    }

    response = api_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data
    assert not User.objects.filter(email="faible@example.com").exists()


def test_register_is_refused_when_the_platform_has_no_capacity_left(api_client, settings):
    """Une inscription ouvre un essai, et un essai engage des emplacements sur
    un pool partagé par toute la plateforme. Quand il est plein, on refuse
    explicitement : livrer un compte dont chaque fonction se bloquerait
    ensuite serait pire, et laisserait constater le dépassement après coup."""
    from apps.tenants.models import Tenant

    settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE = 0
    url = reverse("auth-register")
    payload = {
        "email": "trop-tard@example.com",
        "password": "UnMotDePasseSolide2026",
        "company_name": "Entreprise Sans Place",
    }

    response = api_client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # Rien n'est laissé derrière : ni compte, ni entreprise à moitié créée.
    assert not User.objects.filter(email="trop-tard@example.com").exists()
    assert not Tenant.objects.filter(name="Entreprise Sans Place").exists()
    # Le message ne divulgue pas les plafonds de la licence à un visiteur.
    assert "15" not in str(response.data)
