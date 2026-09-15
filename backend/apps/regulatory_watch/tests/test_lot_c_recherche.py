"""Lot C, point 22 — chercher dans la veille, et en voir plus de vingt.

Le flux client était tronqué à vingt publications, sans recherche ni page
suivante : la vingt et unième n'existait pas pour le client. Ce qui ne change
pas : seules les publications retenues ou intégrées y figurent.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.regulatory_watch.models import WatchSource, WatchUpdate

pytestmark = pytest.mark.django_db

URL = "/api/v1/watch/"


def _entetes(api_client, user, tenant, password="Str0ng!Passw0rd123"):
    reponse = api_client.post(
        reverse("token-obtain-pair"), {"email": user.email, "password": password}, format="json"
    )
    return {
        "HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


@pytest.fixture
def source(db):
    return WatchSource.objects.create(
        slug="autorite-recherche",
        name="Publications",
        publisher="Autorité de test",
        url="https://exemple-autorite.test/publications",
        feed_url="https://exemple-autorite.test/rss.xml",
        format=WatchSource.Format.RSS,
    )


def _publication(source, cle, titre, *, statut=WatchUpdate.Status.KEPT, nature=""):
    publication = WatchUpdate.objects.create(
        source=source,
        external_id=f"pub-{cle}",
        title=titre,
        url=f"https://exemple-autorite.test/{cle}",
        status=statut,
    )
    if nature:
        WatchUpdate.objects.filter(pk=publication.pk).update(kind=nature)
    return publication


class TestRechercheEtNature:
    def test_cherche_dans_le_titre(self, api_client, tenant, tenant_owner, source):
        _publication(source, "a", "Recommandations sur l'intelligence artificielle")
        _publication(source, "b", "Délibération sur les violations de données")

        reponse = api_client.get(
            URL, {"q": "violations"}, **_entetes(api_client, tenant_owner, tenant)
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert [p["title"] for p in reponse.data["results"]] == [
            "Délibération sur les violations de données"
        ]

    def test_filtre_par_nature(self, api_client, tenant, tenant_owner, source):
        # Pas la première valeur : c'est la valeur par défaut, que la seconde
        # publication porte aussi — le test ne distinguerait rien.
        nature = WatchUpdate.Kind.NEW_REQUIREMENT
        _publication(source, "a", "Première", nature=nature)
        _publication(source, "b", "Seconde")

        reponse = api_client.get(
            URL, {"kind": nature}, **_entetes(api_client, tenant_owner, tenant)
        )

        assert [p["title"] for p in reponse.data["results"]] == ["Première"]

    def test_une_nature_inconnue_est_ignoree(self, api_client, tenant, tenant_owner, source):
        _publication(source, "a", "Première")

        reponse = api_client.get(
            URL, {"kind": "rumeur"}, **_entetes(api_client, tenant_owner, tenant)
        )

        assert reponse.data["count"] == 1


class TestAuDelaDeVingt:
    def test_la_vingt_et_unieme_publication_existe(self, api_client, tenant, tenant_owner, source):
        for i in range(23):
            _publication(source, f"p{i}", f"Publication {i}")
        entetes = _entetes(api_client, tenant_owner, tenant)

        premiere = api_client.get(URL, **entetes)
        seconde = api_client.get(URL, {"page": 2}, **entetes)

        assert premiere.data["count"] == 23
        assert len(premiere.data["results"]) == 20
        assert premiere.data["has_next"] is True
        assert len(seconde.data["results"]) == 3
        assert seconde.data["has_next"] is False

    def test_une_page_ne_depasse_jamais_cinquante(self, api_client, tenant, tenant_owner, source):
        for i in range(55):
            _publication(source, f"q{i}", f"Publication {i}")

        reponse = api_client.get(
            URL, {"page_size": 500}, **_entetes(api_client, tenant_owner, tenant)
        )

        assert len(reponse.data["results"]) == 50


class TestCeQuiNeChangePas:
    def test_la_recherche_ne_fait_jamais_apparaitre_une_suggestion_non_triee(
        self, api_client, tenant, tenant_owner, source
    ):
        _publication(source, "n", "Violation non triée", statut=WatchUpdate.Status.NEW)
        _publication(source, "d", "Violation écartée", statut=WatchUpdate.Status.DISMISSED)

        reponse = api_client.get(
            URL, {"q": "violation"}, **_entetes(api_client, tenant_owner, tenant)
        )

        assert reponse.data["count"] == 0

    def test_la_promesse_accompagne_toujours_le_flux(
        self, api_client, tenant, tenant_owner, source
    ):
        reponse = api_client.get(URL, {"q": "rien"}, **_entetes(api_client, tenant_owner, tenant))

        assert reponse.data["promise"]
