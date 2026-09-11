"""La veille vue du CLIENT (B5.18).

Un écran en lecture seule qui montre ce qui a changé dans son domaine. C'est
un argument commercial autant qu'un service : le client voit que la
plateforme suit l'actualité réglementaire pour lui.

**Ce qui n'y figure pas compte autant que ce qui y figure.** Une suggestion
encore à trier n'est pas une information, c'est une hypothèse — l'annoncer
comme une exigence serait faux, et coûterait plus cher au client qu'une
exigence manquée (ADR-034).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.regulatory_watch import services
from apps.regulatory_watch.models import WatchUpdate

pytestmark = pytest.mark.django_db


def _client_auth(api_client, user, tenant):
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
def publications(source_rss, suggestion, exploitant):
    """Une retenue, une écartée, une encore à trier."""
    retenue = suggestion
    services.review_update(retenue, status=WatchUpdate.Status.KEPT, reviewer=exploitant)

    ecartee = WatchUpdate.objects.create(
        source=source_rss,
        external_id="ecartee-1",
        title="Publication sans effet sur un référentiel",
        url="https://exemple-autorite.test/ecartee",
        status=WatchUpdate.Status.DISMISSED,
    )
    a_trier = WatchUpdate.objects.create(
        source=source_rss,
        external_id="a-trier-1",
        title="Publication pas encore lue par l'exploitant",
        url="https://exemple-autorite.test/a-trier",
        status=WatchUpdate.Status.NEW,
    )
    return {"retenue": retenue, "ecartee": ecartee, "a_trier": a_trier}


class TestCeQueLeClientVoit:
    def test_le_client_voit_les_publications_retenues(
        self, api_client, tenant, tenant_owner, publications
    ):
        response = api_client.get(
            reverse("client-watch-feed"), **_client_auth(api_client, tenant_owner, tenant)
        )

        assert response.status_code == status.HTTP_200_OK
        titres = [p["title"] for p in response.data["results"]]
        assert publications["retenue"].title in titres

    def test_le_client_ne_voit_PAS_la_file_de_tri(
        self, api_client, tenant, tenant_owner, publications
    ):
        """Une suggestion non triée est une hypothèse, pas une exigence."""
        response = api_client.get(
            reverse("client-watch-feed"), **_client_auth(api_client, tenant_owner, tenant)
        )

        titres = [p["title"] for p in response.data["results"]]
        assert publications["a_trier"].title not in titres
        assert publications["ecartee"].title not in titres

    def test_chaque_publication_porte_sa_source_officielle(
        self, api_client, tenant, tenant_owner, publications
    ):
        """« On ne livre pas ce qu'on ne peut pas sourcer » : le client doit
        pouvoir remonter au texte."""
        response = api_client.get(
            reverse("client-watch-feed"), **_client_auth(api_client, tenant_owner, tenant)
        )

        ligne = response.data["results"][0]
        assert ligne["url"]
        assert ligne["publisher"]

    def test_la_promesse_accompagne_le_flux(self, api_client, tenant, tenant_owner, publications):
        """La même phrase que la console : ni « exhaustive », ni « temps réel »."""
        response = api_client.get(
            reverse("client-watch-feed"), **_client_auth(api_client, tenant_owner, tenant)
        )

        promesse = response.data["promise"].lower()
        assert "publications officielles" in promesse
        assert "temps réel" not in promesse

    def test_le_flux_ne_dit_rien_du_fonctionnement_interne(
        self, api_client, tenant, tenant_owner, publications
    ):
        """Ni état des sources, ni compteurs de file : ce sont nos outils, pas
        l'information du client."""
        response = api_client.get(
            reverse("client-watch-feed"), **_client_auth(api_client, tenant_owner, tenant)
        )

        assert "health" not in response.data
        assert "summary" not in response.data
        assert "consecutive_failures" not in str(response.data)


class TestAcces:
    def test_un_visiteur_non_authentifie_n_y_accede_pas(self, api_client, publications):
        response = api_client.get(reverse("client-watch-feed"))

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_le_flux_est_le_meme_pour_tous_les_clients(
        self, api_client, tenant, tenant_owner, publications, tenant_factory, user_factory
    ):
        """La veille n'est PAS scopée par tenant, et c'est voulu : elle porte
        sur des publications publiques et alimente un catalogue partagé. Ce
        test l'épingle pour que personne ne prenne l'absence de scoping pour
        un oubli."""
        voisin_owner = user_factory(email="voisin-veille@example.com")
        voisin = tenant_factory(voisin_owner, name="Voisin Veille")

        chez_lui = api_client.get(
            reverse("client-watch-feed"), **_client_auth(api_client, tenant_owner, tenant)
        )
        chez_voisin = api_client.get(
            reverse("client-watch-feed"), **_client_auth(api_client, voisin_owner, voisin)
        )

        assert chez_lui.data["results"] == chez_voisin.data["results"]
