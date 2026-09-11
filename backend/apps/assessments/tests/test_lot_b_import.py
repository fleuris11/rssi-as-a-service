"""Lot B — importer un référentiel depuis la console (B2.3).

Trois exigences, et la troisième est celle qui protège le client :

1. **un modèle vide à remplir** — un format documenté ne suffit pas,
   personne ne lit une spécification pour remplir un tableur ;
2. **les erreurs ligne par ligne, toutes en une fois** — corriger un fichier
   une erreur à la fois est le plus sûr moyen de ne jamais le corriger ;
3. **rien n'est écrit tant qu'on n'a pas confirmé** sur un aperçu. Un
   référentiel fautif ne reste pas dans la console : il se propage dans les
   questionnaires de tous les clients à qui on l'attribue.
"""

import json

import pytest
from django.urls import reverse
from rest_framework import status

from apps.assessments import importers
from apps.assessments.models import Referential
from apps.platform_admin.models import PlatformAdminProfile

pytestmark = pytest.mark.django_db


@pytest.fixture
def exploitant(user_factory):
    user = user_factory(email="import@example.com", is_staff=True)
    PlatformAdminProfile.objects.create(user=user, level=PlatformAdminProfile.Level.FULL)
    return user


def _auth(api_client, user):
    response = api_client.post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": "Str0ng!Passw0rd123"},
        format="json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}


ENTETE = {"slug": "test-import", "name": "Référentiel de test", "version": "1.0"}


class TestModele:
    """B2.3 — le modèle vide."""

    def test_le_modele_se_telecharge(self, api_client, exploitant):
        response = api_client.get(
            reverse("platform-referential-template"), **_auth(api_client, exploitant)
        )

        assert response.status_code == status.HTTP_200_OK
        assert "modele-referentiel.csv" in response["Content-Disposition"]

    def test_le_modele_porte_exactement_les_colonnes_du_parseur(self):
        """Un modèle qui diverge du parseur produit un fichier ACCEPTÉ dont
        les énoncés sont vides — l'erreur ne se voit alors qu'à l'écran du
        client."""
        entetes = importers.modele_csv().splitlines()[0].split(";")

        assert entetes == importers.CSV_COLUMNS

    def test_le_modele_se_reimporte_sans_erreur(self):
        """Le test qui compte : le modèle qu'on distribue doit passer."""
        resultat = importers.analyser(importers.modele_csv(), fmt="csv", header=ENTETE)

        assert resultat["erreurs"] == []
        assert resultat["apercu"]["measure_count"] == 1


class TestErreursLigneParLigne:
    """B2.3 — montrer TOUTES les erreurs, avec leur ligne."""

    def test_collecte_plusieurs_lignes_fautives(self):
        fichier = (
            importers.modele_csv()
            + "autre;Autre;2;;;Titre;Enonce;standard;1;low;high\n"
            + ";Encore;3;9;9;Titre;Enonce;standard;1;low;high\n"
        )

        erreurs = importers.analyser(fichier, fmt="csv", header=ENTETE)["erreurs"]

        assert len(erreurs) == 2
        assert [e["ligne"] for e in erreurs] == [3, 4]

    def test_l_erreur_structurelle_porte_sa_ligne(self):
        """« Ligne 3 » se corrige ; « une mesure n'a pas d'énoncé » se cherche
        dans trois cents lignes."""
        fichier = (
            importers.modele_csv()
            + "sensibiliser-former;Sensibiliser;1;2;2;Titre;;standard;1;low;high\n"
        )

        erreurs = importers.analyser(fichier, fmt="csv", header=ENTETE)["erreurs"]

        assert len(erreurs) == 1
        assert erreurs[0]["ligne"] == 3
        assert "langage clair" in erreurs[0]["message"]

    def test_signale_les_codes_en_double(self):
        fichier = (
            importers.modele_csv()
            + "sensibiliser-former;Sensibiliser;1;1;2;Titre;Enonce;standard;1;low;high\n"
        )

        erreurs = importers.analyser(fichier, fmt="csv", header=ENTETE)["erreurs"]

        assert any("double" in e["message"] for e in erreurs)

    def test_un_separateur_virgule_est_lu_aussi(self):
        """Excel francophone exporte en point-virgule, les outils anglophones
        en virgule. Imposer l'un ferait lire tout le fichier en une colonne,
        et l'erreur rendue n'aurait aucun rapport avec la cause."""
        fichier = importers.modele_csv().replace(";", ",")

        assert importers.analyser(fichier, fmt="csv", header=ENTETE)["erreurs"] == []


class TestDeuxTemps:
    """B2.3 — aperçu d'abord, écriture seulement sur confirmation."""

    def test_sans_confirmation_rien_n_est_cree(self, api_client, exploitant):
        response = api_client.post(
            reverse("platform-referential-import"),
            {"content": importers.modele_csv(), "format": "csv", **ENTETE},
            format="json",
            **_auth(api_client, exploitant),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["imported"] is False
        assert response.data["preview"]["measure_count"] == 1
        assert not Referential.objects.filter(slug="test-import").exists()

    def test_un_fichier_fautif_ne_cree_rien_meme_confirme(self, api_client, exploitant):
        fichier = importers.modele_csv() + "autre;Autre;2;;;T;E;standard;1;low;high\n"

        response = api_client.post(
            reverse("platform-referential-import"),
            {"content": fichier, "format": "csv", "confirm": True, **ENTETE},
            format="json",
            **_auth(api_client, exploitant),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["errors"]
        assert not Referential.objects.filter(slug="test-import").exists()

    def test_confirme_l_import_cree_le_referentiel(self, api_client, exploitant):
        response = api_client.post(
            reverse("platform-referential-import"),
            {"content": importers.modele_csv(), "format": "csv", "confirm": True, **ENTETE},
            format="json",
            **_auth(api_client, exploitant),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["imported"] is True
        referentiel = Referential.objects.get(slug="test-import")
        assert referentiel.measures.count() == 1

    def test_importe_aussi_du_json(self, api_client, exploitant):
        charge = {
            "slug": "test-json",
            "name": "Test JSON",
            "version": "1",
            "domains": [
                {
                    "code": "d1",
                    "name": "Domaine 1",
                    "measures": [
                        {
                            "code": "1",
                            # Noms du format DOCUMENTE, pas des champs internes.
                            "title": "Intitulé officiel",
                            "statement": "Énoncé en langage clair ?",
                        }
                    ],
                }
            ],
        }

        response = api_client.post(
            reverse("platform-referential-import"),
            {"content": json.dumps(charge), "format": "json", "confirm": True},
            format="json",
            **_auth(api_client, exploitant),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Referential.objects.filter(slug="test-json").exists()


class TestAccesReserve:
    """L'import cree du contenu servi a TOUS les clients : il se garde."""

    def test_un_client_ne_peut_pas_importer(self, api_client, tenant, tenant_owner):
        jeton = api_client.post(
            reverse("token-obtain-pair"),
            {"email": tenant_owner.email, "password": "Str0ng!Passw0rd123"},
            format="json",
        ).data["access"]

        response = api_client.post(
            reverse("platform-referential-import"),
            {"content": importers.modele_csv(), "format": "csv", **ENTETE},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {jeton}",
            HTTP_X_TENANT_ID=str(tenant.id),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
