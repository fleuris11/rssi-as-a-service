"""Lot C, C3 — les documents organisés par usage, prévisualisés, pré-remplis.

Ce que ces tests tiennent :

- chaque document a UN usage et un destinataire (point 12 et 13) ;
- l'aperçu donne le texte exact de la génération, sans rien enregistrer
  (point 14) — ni ligne, ni version consommée ;
- l'aperçu de la charte n'appelle jamais l'IA ;
- ce que la plateforme sait n'est plus laissé « à compléter » (point 16) ;
- l'aperçu d'un client ne montre jamais les données d'un autre.
"""

from unittest import mock

import pytest
from django.urls import reverse
from rest_framework import status

from apps.ai_assistant import services
from apps.ai_assistant.documents import context, registry
from apps.ai_assistant.models import GeneratedDocument
from apps.tenants.models import Membership

pytestmark = pytest.mark.django_db


def _login(api_client, email, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


def _auth(api_client, user, tenant):
    return {
        "HTTP_AUTHORIZATION": f"Bearer {_login(api_client, user.email)}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


class TestRangementParUsage:
    def test_chaque_document_a_un_usage_connu_et_un_destinataire(self):
        for spec in registry.all_specs():
            assert spec.usage in registry.USAGES, spec.type
            assert spec.audience.strip(), f"{spec.type} n'a pas de destinataire"

    def test_les_quatre_usages_de_la_consigne_sont_tous_servis(self):
        servis = {spec.usage for spec in registry.all_specs()}
        assert servis == set(registry.USAGES)

    def test_le_catalogue_sert_l_usage_et_le_destinataire(self, api_client, tenant, tenant_owner):
        response = api_client.get(
            reverse("ai-document-catalog"), **_auth(api_client, tenant_owner, tenant)
        )

        assert response.status_code == status.HTTP_200_OK
        entree = next(e for e in response.data if e["type"] == "incident_register")
        assert entree["usage"] == registry.USAGE_ANSWER
        assert entree["usage_label"] == "Pour répondre à un client ou un assureur"
        assert "délégué à la protection des données" in entree["audience"]


class TestApercu:
    def test_l_apercu_est_le_texte_exact_de_la_generation(self, tenant, tenant_owner):
        apercu = services.preview_document(tenant=tenant, document_type="incident_procedure")
        document = services.compose_document(
            tenant=tenant, user=tenant_owner, document_type="incident_procedure"
        )

        assert apercu["source"] == registry.SOURCE_COMPOSED
        assert apercu["content_markdown"] == document.content_markdown

    def test_l_apercu_n_enregistre_rien_et_ne_consomme_aucune_version(self, tenant, tenant_owner):
        services.preview_document(tenant=tenant, document_type="continuity_plan")
        services.preview_document(tenant=tenant, document_type="continuity_plan")

        assert GeneratedDocument.all_objects.filter(tenant=tenant).count() == 0
        document = services.compose_document(
            tenant=tenant, user=tenant_owner, document_type="continuity_plan"
        )
        assert document.version == 1

    def test_l_apercu_de_la_charte_montre_son_plan_sans_appeler_l_ia(self, tenant):
        with mock.patch.object(services, "call_claude") as appel:
            apercu = services.preview_document(tenant=tenant, document_type="it_charter")

        appel.assert_not_called()
        assert apercu["source"] == registry.SOURCE_AI
        assert apercu["content_markdown"] is None
        assert "Accès et mots de passe" in apercu["outline"]

    def test_un_type_inconnu_est_refuse(self, api_client, tenant, tenant_owner):
        response = api_client.get(
            reverse("ai-document-preview", args=["contrat-de-travail"]),
            **_auth(api_client, tenant_owner, tenant),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_un_lecteur_peut_previsualiser(self, api_client, tenant, user_factory):
        lecteur = user_factory(email="lecteur-apercu@example.com")
        Membership.all_objects.create(tenant=tenant, user=lecteur, role=Membership.Role.READER)

        response = api_client.get(
            reverse("ai-document-preview", args=["awareness_sheet"]),
            **_auth(api_client, lecteur, tenant),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["content_markdown"]


class TestEtancheite:
    def test_l_apercu_ne_montre_jamais_les_donnees_d_un_autre_client(
        self, api_client, tenant, tenant_owner, user_factory, tenant_factory
    ):
        voisin_proprietaire = user_factory(email="voisin-docs@example.com")
        tenant_factory(voisin_proprietaire, name="Cabinet Voisin Confidentiel")

        response = api_client.get(
            reverse("ai-document-preview", args=["incident_procedure"]),
            **_auth(api_client, tenant_owner, tenant),
        )

        assert response.status_code == status.HTTP_200_OK
        assert tenant.name in response.data["content_markdown"]
        assert "Cabinet Voisin Confidentiel" not in response.data["content_markdown"]
        assert "voisin-docs@example.com" not in response.data["content_markdown"]

    def test_l_en_tete_x_tenant_d_un_autre_client_est_refuse(
        self, api_client, tenant_owner, user_factory, tenant_factory
    ):
        autre = tenant_factory(user_factory(email="autre-docs@example.com"), name="Autre")

        response = api_client.get(
            reverse("ai-document-preview", args=["incident_procedure"]),
            **_auth(api_client, tenant_owner, autre),
        )

        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)


class TestPreRemplissage:
    def test_le_referent_securite_est_l_administrateur_connu(self, tenant, tenant_owner):
        """La plateforme connaît les administrateurs du client : les laisser
        « à compléter » faisait ressaisir au client ce qu'elle sait."""
        tenant_owner.first_name = "Claire"
        tenant_owner.last_name = "Martin"
        tenant_owner.save(update_fields=["first_name", "last_name"])

        for document_type in ("incident_procedure", "continuity_plan", "awareness_sheet"):
            texte = services.preview_document(tenant=tenant, document_type=document_type)[
                "content_markdown"
            ]
            assert "Claire Martin" in texte, document_type
            assert tenant_owner.email in texte, document_type

    def test_un_administrateur_desactive_n_est_pas_designe(self, tenant, tenant_owner):
        """Désactiver un membre coupe le COMPTE (tenants.set_member_active) :
        c'est ce drapeau que la proposition de référent doit lire."""
        tenant_owner.is_active = False
        tenant_owner.save(update_fields=["is_active"])

        assert context.company(tenant)["referents"] == []

    def test_un_simple_contributeur_n_est_pas_designe_referent(
        self, tenant, tenant_owner, user_factory
    ):
        contributeur = user_factory(email="contributeur-docs@example.com")
        Membership.all_objects.create(
            tenant=tenant, user=contributeur, role=Membership.Role.CONTRIBUTOR
        )

        emails = [r["email"] for r in context.company(tenant)["referents"]]
        assert contributeur.email not in emails
        assert tenant_owner.email in emails

    def test_ce_que_la_plateforme_ignore_reste_a_completer(self, tenant):
        """L'assureur et la banque ne sont connus nulle part : les deviner
        serait pire que les demander."""
        texte = services.preview_document(tenant=tenant, document_type="continuity_plan")[
            "content_markdown"
        ]
        ligne_assureur = next(ligne for ligne in texte.splitlines() if "Assureur" in ligne)
        assert context.A_COMPLETER in ligne_assureur
