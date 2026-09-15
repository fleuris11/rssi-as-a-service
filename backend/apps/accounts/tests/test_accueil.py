"""Lot C, point 21 — la séquence d'accueil d'un nouveau client.

Le serveur ne mémorise que ce qu'il ne peut pas lire ailleurs : la personne a
compris son premier résultat, ou a choisi de masquer l'accueil. Les deux
premières étapes (un actif déclaré, un diagnostic terminé) se lisent dans les
données du client et ne sont pas dupliquées ici.
"""

import pytest
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.django_db


def _entetes(api_client, user, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": user.email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}


class TestEtatDeLAccueil:
    def test_un_nouveau_compte_n_a_franchi_aucune_etape(self, api_client, tenant_owner):
        response = api_client.get(reverse("auth-me"), **_entetes(api_client, tenant_owner))

        assert response.data["onboarding"] == {"result_seen": False, "dismissed": False}

    def test_comprendre_son_premier_resultat_est_memorise(self, api_client, tenant_owner):
        entetes = _entetes(api_client, tenant_owner)

        response = api_client.post(
            reverse("auth-me-onboarding"), {"step": "result_seen"}, format="json", **entetes
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["onboarding"]["result_seen"] is True
        tenant_owner.refresh_from_db()
        assert tenant_owner.onboarding_result_seen_at is not None

    def test_la_date_de_la_premiere_fois_n_est_pas_reecrite(self, api_client, tenant_owner):
        entetes = _entetes(api_client, tenant_owner)
        api_client.post(
            reverse("auth-me-onboarding"), {"step": "result_seen"}, format="json", **entetes
        )
        tenant_owner.refresh_from_db()
        premiere = tenant_owner.onboarding_result_seen_at

        api_client.post(
            reverse("auth-me-onboarding"), {"step": "result_seen"}, format="json", **entetes
        )

        tenant_owner.refresh_from_db()
        assert tenant_owner.onboarding_result_seen_at == premiere

    def test_masquer_l_accueil(self, api_client, tenant_owner):
        response = api_client.post(
            reverse("auth-me-onboarding"),
            {"step": "dismissed"},
            format="json",
            **_entetes(api_client, tenant_owner),
        )

        assert response.data["onboarding"] == {"result_seen": False, "dismissed": True}

    def test_une_etape_inconnue_est_refusee(self, api_client, tenant_owner):
        response = api_client.post(
            reverse("auth-me-onboarding"),
            {"step": "diagnostic_termine"},
            format="json",
            **_entetes(api_client, tenant_owner),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCloisonnement:
    def test_on_ne_peut_franchir_que_ses_propres_etapes(
        self, api_client, tenant_owner, user_factory
    ):
        """Aucun paramètre ne désigne une autre personne : même en en passant
        un, c'est l'utilisateur connecté qui est concerné."""
        autre = user_factory(email="autre-accueil@example.com")

        api_client.post(
            reverse("auth-me-onboarding"),
            {"step": "dismissed", "user": str(autre.id), "id": str(autre.id)},
            format="json",
            **_entetes(api_client, tenant_owner),
        )

        autre.refresh_from_db()
        tenant_owner.refresh_from_db()
        assert autre.onboarding_dismissed_at is None
        assert tenant_owner.onboarding_dismissed_at is not None

    def test_exige_une_connexion(self, api_client):
        response = api_client.post(
            reverse("auth-me-onboarding"), {"step": "dismissed"}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_ne_change_ni_le_profil_ni_les_droits(self, api_client, tenant_owner):
        api_client.post(
            reverse("auth-me-onboarding"),
            {"step": "result_seen", "display_profile": "technical", "is_staff": True},
            format="json",
            **_entetes(api_client, tenant_owner),
        )

        tenant_owner.refresh_from_db()
        assert tenant_owner.display_profile == "executive"
        assert tenant_owner.is_staff is False
