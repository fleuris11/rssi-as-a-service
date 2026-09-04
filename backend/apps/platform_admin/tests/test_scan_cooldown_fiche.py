"""Le délai entre deux analyses se règle depuis la fiche du client.

Le réglage de plateforme annonçait, dans sa propre description : « Un client
précis peut recevoir sa propre valeur depuis sa fiche ». C'était faux au
moment où la phrase a été écrite : la colonne existait sur le modèle, la
cascade de résolution fonctionnait, mais **rien n'exposait le champ** — ni
l'API de la console, ni l'écran. Une description qui promet un réglage
inexistant est pire qu'une absence de réglage : l'exploitant cherche.

Le piège tenu ici est le même que côté services, et il vaut d'être testé deux
fois parce qu'il se rejoue à chaque couche traversée :

    `null` = pas de surcharge, on applique le réglage de plateforme
    `0`    = aucun délai, décidé pour ce client

Une couche qui confondrait les deux appliquerait 24 h à un client à qui
l'exploitant vient d'accorder l'inverse.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.threat_intelligence import services as threat_intelligence_services

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd123"


@pytest.fixture
def staff_client(api_client, user_factory):
    staff = user_factory(email="exploitant@example.com")
    staff.is_staff = True
    staff.save(update_fields=["is_staff"])
    response = api_client.post(
        reverse("token-obtain-pair"),
        {"email": staff.email, "password": PASSWORD},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api_client


def _url(tenant):
    return reverse("platform-client-detail", args=[tenant.id])


class TestLaFicheExposeLeDelai:
    def test_la_fiche_montre_le_delai_reellement_applique(self, staff_client, tenant):
        """Sans ce champ, la fiche afficherait « (vide) » sans dire ce qui
        s'applique à la place : l'exploitant devrait aller lire la console."""
        response = staff_client.get(_url(tenant))

        assert response.status_code == status.HTTP_200_OK
        fiche = response.data["fiche"]
        assert fiche["scan_cooldown_minutes"] is None
        assert fiche["effective_scan_cooldown_minutes"] == 1440

    def test_on_peut_donner_sa_propre_valeur_a_un_client(self, staff_client, tenant):
        response = staff_client.patch(_url(tenant), {"scan_cooldown_minutes": 2}, format="json")

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_202_ACCEPTED)
        tenant.refresh_from_db()
        assert threat_intelligence_services.scan_cooldown_minutes(tenant) == 2

    def test_zero_veut_dire_aucun_delai_et_non_pas_vide(self, staff_client, tenant):
        """Le piège, à travers toute la pile cette fois : sérialiseur, modèle,
        résolution. Un 0 traité comme « non renseigné » rendrait le réglage
        impossible à exprimer."""
        response = staff_client.patch(_url(tenant), {"scan_cooldown_minutes": 0}, format="json")

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_202_ACCEPTED)
        tenant.refresh_from_db()
        assert tenant.scan_cooldown_minutes == 0
        assert threat_intelligence_services.scan_cooldown_minutes(tenant) == 0

    def test_vider_le_champ_remet_le_reglage_de_plateforme(self, staff_client, tenant):
        tenant.scan_cooldown_minutes = 2
        tenant.save(update_fields=["scan_cooldown_minutes"])

        staff_client.patch(_url(tenant), {"scan_cooldown_minutes": None}, format="json")

        tenant.refresh_from_db()
        assert tenant.scan_cooldown_minutes is None
        assert threat_intelligence_services.scan_cooldown_minutes(tenant) == 1440

    def test_une_valeur_absurde_est_refusee(self, staff_client, tenant):
        """Un an d'attente n'est pas un réglage, c'est une panne. La borne
        évite qu'une faute de frappe bloque un client sans que personne ne
        comprenne pourquoi."""
        response = staff_client.patch(
            _url(tenant), {"scan_cooldown_minutes": 999999}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        tenant.refresh_from_db()
        assert tenant.scan_cooldown_minutes is None
