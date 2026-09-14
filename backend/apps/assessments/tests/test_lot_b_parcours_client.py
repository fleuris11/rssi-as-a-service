"""Lot B — le parcours client sur une composition, et le modèle vide.

Deux contrats dont l'écran dépend et qu'aucun test serveur ne tenait :

1. une évaluation ouverte sur une composition porte l'IDENTIFIANT de cette
   composition. Sans lui, l'écran rechargeait à la reprise la structure du
   référentiel complet — quarante-deux questions pour une évaluation qui
   n'en compte que dix ;
2. le client télécharge EXACTEMENT le même modèle vide que la console. Deux
   modèles qui divergeraient produiraient des fichiers acceptés d'un côté et
   refusés de l'autre.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.assessments import importers, services

pytestmark = pytest.mark.django_db


def _client(api_client, user, tenant):
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
def composition(tenant, referential):
    services.assign_referential(tenant=tenant, referential=referential)
    codes = list(referential.measures.order_by("order", "code").values_list("code", flat=True)[:2])
    return services.create_subset(
        referential=referential, slug="deux-mesures", name="Deux mesures", measure_codes=codes
    )


class TestEvaluationSurComposition:
    def test_l_evaluation_porte_l_identifiant_de_sa_composition(
        self, api_client, tenant, tenant_owner, referential, composition
    ):
        reponse = api_client.post(
            reverse("assessment-start"),
            {"referential": referential.slug, "subset": composition.slug},
            format="json",
            **_client(api_client, tenant_owner, tenant),
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["subset_slug"] == composition.slug

    def test_la_reprise_porte_aussi_l_identifiant(
        self, api_client, tenant, tenant_owner, referential, composition
    ):
        entetes = _client(api_client, tenant_owner, tenant)
        api_client.post(
            reverse("assessment-start"),
            {"referential": referential.slug, "subset": composition.slug},
            format="json",
            **entetes,
        )

        reponse = api_client.get(
            reverse("assessment-current"), {"referential": referential.slug}, **entetes
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["subset_slug"] == composition.slug

    def test_sans_composition_l_identifiant_est_vide(
        self, api_client, tenant, tenant_owner, referential
    ):
        services.assign_referential(tenant=tenant, referential=referential)

        reponse = api_client.post(
            reverse("assessment-start"),
            {"referential": referential.slug},
            format="json",
            **_client(api_client, tenant_owner, tenant),
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["subset_slug"] is None


class TestModeleVideCoteClient:
    def test_le_client_telecharge_le_meme_modele_que_la_console(
        self, api_client, tenant, tenant_owner
    ):
        reponse = api_client.get(
            reverse("assessment-referential-template"),
            **_client(api_client, tenant_owner, tenant),
        )

        assert reponse.status_code == status.HTTP_200_OK
        contenu = reponse.content.decode("utf-8-sig")
        assert contenu.splitlines()[0].split(";") == importers.CSV_COLUMNS
        assert contenu == importers.modele_csv()

    def test_un_visiteur_non_authentifie_n_obtient_rien(self, api_client):
        reponse = api_client.get(reverse("assessment-referential-template"))

        assert reponse.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
