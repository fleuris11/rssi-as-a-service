"""Lot C, point 22 — chercher et filtrer dans les compromissions.

La liste dépasse vingt lignes dès qu'un client a du volume (165 en production
chez CRRH). Trois exigences :

- les filtres trouvent ce qu'ils doivent trouver ;
- ils ne franchissent jamais la frontière d'un client ;
- la recherche ne porte JAMAIS sur l'identifiant en clair : elle servirait
  d'oracle à un rôle qui n'a droit qu'à la forme masquée (ADR-027).
"""

import pytest
from rest_framework import status

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset
from apps.threat_intelligence import services
from apps.threat_intelligence.models import BreachFinding

pytestmark = pytest.mark.django_db

URL = "/api/v1/threat-intelligence/findings/"


def _entetes(api_client, user, tenant, password="Str0ng!Passw0rd123"):
    from django.urls import reverse

    reponse = api_client.post(
        reverse("token-obtain-pair"), {"email": user.email, "password": password}, format="json"
    )
    return {
        "HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


def _actif(tenant, user, valeur):
    return monitoring_services.create_asset(
        tenant=tenant, user=user, type=Asset.Type.WEBSITE, value=valeur, ownership_confirmed=True
    )


def _fuite(tenant, asset, cle, *, severity="high", finding_type="creds", identifiant=""):
    return BreachFinding.all_objects.create(
        tenant=tenant,
        asset=asset,
        source_endpoint=BreachFinding.SourceEndpoint.CREDS,
        finding_type=finding_type,
        severity=severity,
        status=BreachFinding.Status.OPEN,
        identifier_plain=identifiant,
        identifier_masked="ma••••@ex••••.fr" if identifiant else "",
        dedup_hash=f"d-{cle}",
        identity_hash=f"i-{cle}",
        secret_fingerprint=f"s-{cle}",
    )


@pytest.fixture
def jeu(tenant, tenant_owner):
    compta = _actif(tenant, tenant_owner, "https://compta.acme.example")
    boutique = _actif(tenant, tenant_owner, "https://boutique.acme.example")
    _fuite(tenant, compta, "c1", severity="critical", finding_type="stealer")
    _fuite(tenant, compta, "c2", severity="high")
    _fuite(tenant, boutique, "b1", severity="attention", identifiant="marie.durand@acme.example")
    return {"compta": compta, "boutique": boutique}


class TestFiltres:
    def test_filtre_par_gravite(self, tenant, jeu):
        assert services.list_findings(tenant, severity="critical").count() == 1

    def test_filtre_par_actif(self, tenant, jeu):
        assert services.list_findings(tenant, asset_id=jeu["compta"].id).count() == 2

    def test_cherche_dans_l_actif_et_le_type(self, tenant, jeu):
        assert services.list_findings(tenant, search="boutique").count() == 1
        assert services.list_findings(tenant, search="stealer").count() == 1

    def test_les_filtres_se_combinent(self, tenant, jeu):
        resultat = services.list_findings(
            tenant, search="compta", severity="high", status=BreachFinding.Status.OPEN
        )
        assert resultat.count() == 1

    def test_l_api_applique_les_filtres(self, api_client, tenant, tenant_owner, jeu):
        # Chaque paramètre isolé : combinés, l'un peut masquer l'oubli de
        # l'autre (la seule fuite critique est aussi sur « compta »).
        entetes = _entetes(api_client, tenant_owner, tenant)

        recherche = api_client.get(URL, {"q": "boutique"}, **entetes)
        gravite = api_client.get(URL, {"severity": "critical"}, **entetes)
        actif = api_client.get(URL, {"asset": jeu["compta"].id}, **entetes)

        assert recherche.status_code == status.HTTP_200_OK
        assert recherche.data["count"] == 1
        assert gravite.data["count"] == 1
        assert actif.data["count"] == 2

    def test_une_valeur_de_filtre_inconnue_est_ignoree(self, api_client, tenant, tenant_owner, jeu):
        """Un lien partagé avec un ancien filtre reste lisible."""
        reponse = api_client.get(
            URL,
            {"severity": "apocalyptique", "asset": "pas-un-nombre"},
            **_entetes(api_client, tenant_owner, tenant),
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["count"] == 3


class TestCeQueLaRechercheNeFaitJamais:
    def test_elle_ne_cherche_pas_dans_l_identifiant_en_clair(self, tenant, jeu):
        """Sinon, « marie.d » → 1 résultat, « marie.x » → 0 : l'adresse se
        reconstituerait lettre par lettre, même pour qui ne la voit que
        masquée."""
        assert services.list_findings(tenant, search="marie.durand").count() == 0
        assert services.list_findings(tenant, search="durand@").count() == 0

    def test_elle_ne_franchit_pas_la_frontiere_d_un_client(
        self, api_client, tenant, tenant_owner, jeu, user_factory, tenant_factory
    ):
        voisin_proprietaire = user_factory(email="voisin-recherche@example.com")
        voisin = tenant_factory(voisin_proprietaire, name="Voisin recherche")
        actif_voisin = _actif(voisin, voisin_proprietaire, "https://confidentiel.voisin.example")
        _fuite(voisin, actif_voisin, "v1")

        reponse = api_client.get(
            URL, {"q": "confidentiel"}, **_entetes(api_client, tenant_owner, tenant)
        )

        assert reponse.data["count"] == 0

    def test_un_actif_d_un_autre_client_ne_filtre_rien_chez_soi(
        self, api_client, tenant, tenant_owner, jeu, user_factory, tenant_factory
    ):
        voisin_proprietaire = user_factory(email="voisin-actif@example.com")
        voisin = tenant_factory(voisin_proprietaire, name="Voisin actif")
        actif_voisin = _actif(voisin, voisin_proprietaire, "https://autre.voisin.example")
        _fuite(voisin, actif_voisin, "v2")

        reponse = api_client.get(
            URL, {"asset": actif_voisin.id}, **_entetes(api_client, tenant_owner, tenant)
        )

        assert reponse.data["count"] == 0
