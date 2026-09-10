"""Le profil d'affichage (V2-5, ADR-031).

Deux garanties, et la seconde est la seule qui compte vraiment :

1. le profil se change à tout moment, sans mot de passe et sans effet de bord ;
2. **il ne change ni les droits, ni les données.** Un même fait doit rester le
   même fait — c'est la consigne V2-5 point 3, et c'est la raison pour
   laquelle le serveur ignore complètement ce réglage.

Le test qui compare les charges utiles octet pour octet est celui qui
interdit la dérive : le jour où quelqu'un ajoutera un `if
user.display_profile == "executive"` dans un sérialiseur, il rougira.
"""

import json

import pytest
from django.urls import reverse
from rest_framework import status

from apps.tenants.models import Membership

pytestmark = pytest.mark.django_db

User_DISPLAY_EXECUTIVE = "executive"
User_DISPLAY_TECHNICAL = "technical"


def _login(api_client, email, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


def _auth(api_client, user, tenant=None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {_login(api_client, user.email)}"}
    if tenant is not None:
        headers["HTTP_X_TENANT_ID"] = str(tenant.id)
    return headers


class TestReglage:
    def test_le_defaut_est_dirigeant(self, tenant_owner):
        """Le lecteur que le produit vise en premier, et le réglage le moins
        risqué : on ne noie personne sous du jargon qu'il n'a pas demandé."""
        assert tenant_owner.display_profile == User_DISPLAY_EXECUTIVE

    def test_est_expose_des_la_connexion(self, api_client, tenant_owner):
        """Le frontend en a besoin avant même d'avoir choisi une entreprise."""
        response = api_client.get(reverse("auth-me"), **_auth(api_client, tenant_owner))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["display_profile"] == User_DISPLAY_EXECUTIVE

    def test_se_change_a_tout_moment(self, api_client, tenant_owner):
        headers = _auth(api_client, tenant_owner)

        response = api_client.patch(
            reverse("auth-me"),
            {"display_profile": User_DISPLAY_TECHNICAL},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["display_profile"] == User_DISPLAY_TECHNICAL
        tenant_owner.refresh_from_db()
        assert tenant_owner.display_profile == User_DISPLAY_TECHNICAL

    def test_refuse_une_valeur_inconnue(self, api_client, tenant_owner):
        response = api_client.patch(
            reverse("auth-me"),
            {"display_profile": "expert-comptable"},
            format="json",
            **_auth(api_client, tenant_owner),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ne_permet_pas_de_changer_autre_chose(self, api_client, tenant_owner):
        """L'email est l'identifiant de connexion : il ne se change pas depuis
        un bouton de la barre du haut."""
        api_client.patch(
            reverse("auth-me"),
            {"display_profile": "technical", "email": "usurpateur@example.com", "is_staff": True},
            format="json",
            **_auth(api_client, tenant_owner),
        )

        tenant_owner.refresh_from_db()
        assert tenant_owner.email != "usurpateur@example.com"
        assert tenant_owner.is_staff is False

    def test_est_propre_a_chaque_utilisateur(self, api_client, tenant, tenant_owner, user_factory):
        """Dans une même PME, le dirigeant et son prestataire regardent les
        mêmes écrans sans avoir besoin de la même lecture."""
        technicien = user_factory(email="prestataire@example.com")
        Membership.all_objects.create(
            tenant=tenant, user=technicien, role=Membership.Role.CONTRIBUTOR
        )

        api_client.patch(
            reverse("auth-me"),
            {"display_profile": User_DISPLAY_TECHNICAL},
            format="json",
            **_auth(api_client, technicien, tenant),
        )

        tenant_owner.refresh_from_db()
        technicien.refresh_from_db()
        assert tenant_owner.display_profile == User_DISPLAY_EXECUTIVE
        assert technicien.display_profile == User_DISPLAY_TECHNICAL


class TestNeChangeRien:
    """Le cœur d'ADR-031 : c'est un réglage de RESTITUTION."""

    @pytest.fixture
    def prepare(self, api_client, tenant, tenant_owner, referential):
        from apps.actions import services as actions_services
        from apps.assessments import services as assessments_services

        assessment = assessments_services.start_or_resume_assessment(
            tenant=tenant, user=tenant_owner, referential=referential
        )
        for mesure in assessments_services.get_assessment_measures(assessment):
            assessments_services.submit_answer(assessment=assessment, measure=mesure, value="no")
        assessments_services.complete_assessment(assessment)
        actions_services.generate_action_plan(assessment)
        return assessment

    @pytest.mark.parametrize(
        "url_name",
        [
            "assessment-referential",
            "action-item-list",
            "monitoring-dashboard",
            "ai-document-catalog",
        ],
    )
    def test_la_reponse_est_identique_dans_les_deux_profils(
        self, api_client, tenant, tenant_owner, prepare, url_name
    ):
        headers = _auth(api_client, tenant_owner, tenant)

        tenant_owner.display_profile = User_DISPLAY_EXECUTIVE
        tenant_owner.save(update_fields=["display_profile"])
        dirigeant = api_client.get(reverse(url_name), **headers)

        tenant_owner.display_profile = User_DISPLAY_TECHNICAL
        tenant_owner.save(update_fields=["display_profile"])
        technique = api_client.get(reverse(url_name), **headers)

        assert dirigeant.status_code == technique.status_code == status.HTTP_200_OK
        # Sérialisé pour comparer le contenu et non l'identité des objets :
        # si un jour une clé apparaît d'un côté et pas de l'autre, ce test le
        # dit avec le diff sous les yeux.
        assert json.dumps(dirigeant.data, sort_keys=True, default=str) == json.dumps(
            technique.data, sort_keys=True, default=str
        )

    def test_le_profil_ne_donne_aucun_droit(self, api_client, tenant, user_factory):
        """Un lecteur en profil technique reste un lecteur : le profil
        d'affichage n'est pas un rôle."""
        lecteur = user_factory(email="lecteur@example.com")
        Membership.all_objects.create(tenant=tenant, user=lecteur, role=Membership.Role.READER)
        lecteur.display_profile = User_DISPLAY_TECHNICAL
        lecteur.save(update_fields=["display_profile"])
        headers = _auth(api_client, lecteur, tenant)

        response = api_client.post(reverse("assessment-start"), **headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_le_profil_ne_retire_aucun_droit(self, api_client, tenant, tenant_owner):
        """Et symétriquement : un administrateur en profil dirigeant garde
        tous ses droits d'administrateur."""
        tenant_owner.display_profile = User_DISPLAY_EXECUTIVE
        tenant_owner.save(update_fields=["display_profile"])
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.patch(
            reverse("ai-settings"), {"ai_enabled": False}, format="json", **headers
        )

        assert response.status_code == status.HTTP_200_OK
