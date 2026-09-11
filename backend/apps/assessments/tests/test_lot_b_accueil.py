"""Lot B — le Diagnostic devient un ACCUEIL (B3.8, B19).

Le nom d'un référentiel ne dit pas où on en est. Un client qui en a plusieurs
devait ouvrir chacun pour savoir lequel reprendre. L'écran doit porter, pour
chaque référentiel attribué : son nombre de mesures, son état d'avancement,
son score s'il a été évalué, et la date.

Et il doit proposer les COMPOSITIONS. « Les 10 mesures essentielles » existe
pour qu'un dirigeant ne referme pas un questionnaire de 42 questions — encore
faut-il qu'il la voie.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.assessments import services
from apps.assessments.models import Referential

pytestmark = pytest.mark.django_db


def _auth(api_client, user, tenant):
    reponse = api_client.post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": "Str0ng!Passw0rd123"},
        format="json",
    )
    return {
        "HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


@pytest.fixture
def attribue(tenant, referential, tenant_owner):
    services.assign_referential(tenant=tenant, referential=referential, granted_by=tenant_owner)
    return referential


class TestAccueilDuDiagnostic:
    def test_un_referentiel_jamais_evalue_le_dit(self, api_client, tenant, tenant_owner, attribue):
        response = api_client.get(
            reverse("assessment-referential-list"), **_auth(api_client, tenant_owner, tenant)
        )

        ligne = next(r for r in response.data if r["slug"] == attribue.slug)
        assert ligne["assessment_status"] == "not_started"
        assert ligne["last_score"] is None
        assert ligne["last_assessed_at"] is None

    def test_un_diagnostic_en_cours_est_signale(self, api_client, tenant, tenant_owner, attribue):
        services.start_or_resume_assessment(tenant=tenant, user=tenant_owner, referential=attribue)

        response = api_client.get(
            reverse("assessment-referential-list"), **_auth(api_client, tenant_owner, tenant)
        )

        ligne = next(r for r in response.data if r["slug"] == attribue.slug)
        assert ligne["assessment_status"] == "in_progress"
        assert ligne["last_assessed_at"] is not None

    def test_le_catalogue_porte_le_nombre_de_mesures(
        self, api_client, tenant, tenant_owner, attribue
    ):
        response = api_client.get(
            reverse("assessment-referential-list"), **_auth(api_client, tenant_owner, tenant)
        )

        ligne = next(r for r in response.data if r["slug"] == attribue.slug)
        assert ligne["measure_count"] > 0

    def test_les_compositions_sont_proposees(self, api_client, tenant, tenant_owner, attribue):
        """Sans cela, « les 10 mesures essentielles » existe sans que personne
        ne puisse la choisir."""
        mesures = list(services.get_referential_measures(attribue))[:2]
        services.create_subset(
            referential=attribue,
            slug="essentielles-test",
            name="Composition de test",
            measure_codes=[m.code for m in mesures],
        )

        response = api_client.get(
            reverse("assessment-referential-list"), **_auth(api_client, tenant_owner, tenant)
        )

        ligne = next(r for r in response.data if r["slug"] == attribue.slug)
        noms = [s["name"] for s in ligne["available_subsets"]]
        assert "Composition de test" in noms
        composition = next(
            s for s in ligne["available_subsets"] if s["name"] == "Composition de test"
        )
        assert composition["measure_count"] == 2

    def test_un_referentiel_sous_licence_est_visible_mais_non_attribue(
        self, api_client, tenant, tenant_owner
    ):
        """On affiche desactive, jamais masque : un client doit pouvoir savoir
        que le produit sait faire ISO 27001 avant de le demander.

        Le referentiel est SOUS LICENCE a dessein : les referentiels libres de
        droits sont attribues d'office a la creation du client
        (``default_referentials``), un contenu sous licence jamais — c'est
        l'exploitant qui sait ce qu'il a le droit de servir, et a qui
        (ADR-029 §5).
        """
        sous_licence = Referential.objects.create(
            slug="iso-27001-annexe-a",
            name="ISO/IEC 27001 — Annexe A",
            version="2022",
            kind=Referential.Kind.LICENSED,
            licence_notice="Reproduit sous licence ISO — usage interne au client.",
            is_active=True,
        )

        response = api_client.get(
            reverse("assessment-referential-list"), **_auth(api_client, tenant_owner, tenant)
        )

        assert response.status_code == status.HTTP_200_OK
        ligne = next(r for r in response.data if r["slug"] == sous_licence.slug)
        assert ligne["granted"] is False
        # Visible quand meme, avec sa mention de droits.
        assert ligne["licence_notice"]
        # Et la regle elle-meme, epinglee directement : sans cette assertion
        # le test passerait meme si les contenus sous licence s'attribuaient
        # d'office, puisque ce referentiel est cree APRES le client.
        assert sous_licence not in services.default_referentials()
