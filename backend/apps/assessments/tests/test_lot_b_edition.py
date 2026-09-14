"""Lot B — éditer le catalogue depuis la console, et importer côté client.

La V2-4 avait livré les modèles et une partie de l'API ; l'exploitant ne
pouvait ni créer un référentiel, ni composer un questionnaire, ni reformuler
un énoncé pour un client sans passer par une commande Django.

Ces tests portent aussi DEUX DÉFAUTS D'INTÉGRITÉ ENTRE CLIENTS trouvés en
écrivant ces écrans, et c'est la partie qui compte le plus :

1. ``import_referential`` identifiait le référentiel par son slug et le
   METTAIT À JOUR. Un import portant l'identifiant du référentiel ANSSI en
   remplaçait le questionnaire — pour tous les clients ;
2. ``create_subset`` faisait de même pour les compositions : un client qui
   composait avec l'identifiant d'un modèle de plateforme en réécrivait les
   mesures pour tous les autres.
"""

import json
import pathlib

import pytest
from django.urls import reverse
from rest_framework import status

from apps.assessments import importers, services
from apps.assessments.models import Measure, MeasureSubset, Referential
from apps.platform_admin.models import PlatformAdminProfile

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "Str0ng!Passw0rd123"


def _jeton(api_client, user):
    reponse = api_client.post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": MOT_DE_PASSE},
        format="json",
    )
    return reponse.data["access"]


def _console(api_client, user):
    return {"HTTP_AUTHORIZATION": f"Bearer {_jeton(api_client, user)}"}


def _client(api_client, user, tenant):
    return {
        "HTTP_AUTHORIZATION": f"Bearer {_jeton(api_client, user)}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


@pytest.fixture
def exploitant(user_factory):
    user = user_factory(email="edition@example.com", is_staff=True)
    PlatformAdminProfile.objects.create(user=user, level=PlatformAdminProfile.Level.FULL)
    return user


@pytest.fixture
def commercial(user_factory):
    user = user_factory(email="commercial-edition@example.com", is_staff=True)
    PlatformAdminProfile.objects.create(user=user, level=PlatformAdminProfile.Level.COMMERCIAL)
    return user


@pytest.fixture
def voisin(user_factory, tenant_factory):
    proprietaire = user_factory(email="voisin-edition@example.com")
    return proprietaire, tenant_factory(proprietaire, name="Voisin Édition")


@pytest.fixture
def sous_licence(db):
    """Un référentiel qui ne s'attribue pas tout seul, avec une mesure."""
    referentiel = services.create_referential(
        slug="iso-test",
        name="ISO de test",
        version="2022",
        kind=Referential.Kind.LICENSED,
    )
    services.add_domain(referential=referentiel, code="organisation", name="Organisation")
    services.add_measure(
        referential=referentiel,
        domain_code="organisation",
        code="A.5.1",
        official_title="Politiques de sécurité",
        plain_language="Avez-vous une politique de sécurité écrite ?",
    )
    return referentiel


def _codes(referentiel, n=2):
    return list(
        Measure.objects.filter(referential=referentiel)
        .order_by("order", "code")
        .values_list("code", flat=True)[:n]
    )


# --- Création à la main (B2.4) ----------------------------------------------


class TestCreationALaMain:
    def test_cree_un_referentiel_vide(self, api_client, exploitant):
        reponse = api_client.post(
            reverse("platform-referential-list"),
            {
                "slug": "mon-referentiel",
                "name": "Mon référentiel",
                "version": "1",
                "kind": "licensed",
            },
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_201_CREATED
        assert reponse.data["domains"] == []
        assert Referential.objects.get(slug="mon-referentiel").kind == "licensed"

    def test_refuse_un_identifiant_deja_pris(self, api_client, exploitant, referential):
        """Créer un référentiel qui en écraserait un autre changerait le
        questionnaire de clients qui ne l'ont pas demandé."""
        reponse = api_client.post(
            reverse("platform-referential-list"),
            {"slug": referential.slug, "name": "Doublon", "version": "1"},
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_409_CONFLICT
        referential.refresh_from_db()
        assert referential.name != "Doublon"

    def test_refuse_un_identifiant_invalide(self, api_client, exploitant):
        reponse = api_client.post(
            reverse("platform-referential-list"),
            {"slug": "Mon Référentiel", "name": "X", "version": "1"},
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_400_BAD_REQUEST

    def test_un_domaine_vide_apparait_pour_y_ajouter_la_premiere_mesure(
        self, api_client, exploitant, sous_licence
    ):
        api_client.post(
            reverse("platform-referential-domains", args=[sous_licence.slug]),
            {"code": "technique", "name": "Mesures techniques"},
            format="json",
            **_console(api_client, exploitant),
        )

        reponse = api_client.get(
            reverse("platform-referential-outline", args=[sous_licence.slug]),
            **_console(api_client, exploitant),
        )

        domaine = next(d for d in reponse.data["domains"] if d["code"] == "technique")
        assert domaine["measures"] == []

    def test_ajoute_une_mesure_dans_son_domaine(self, api_client, exploitant, sous_licence):
        reponse = api_client.post(
            reverse("platform-referential-measures", args=[sous_licence.slug]),
            {
                "domain_code": "organisation",
                "code": "A.5.2",
                "official_title": "Fonctions et responsabilités",
                "plain_language": "Les rôles de sécurité sont-ils attribués nommément ?",
                "effort": "low",
                "impact": "high",
            },
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_201_CREATED
        mesure = Measure.objects.get(referential=sous_licence, code="A.5.2")
        assert mesure.impact == "high"

    def test_refuse_une_mesure_sans_enonce(self, api_client, exploitant, sous_licence):
        """Une mesure sans énoncé donnerait une question vide à l'écran."""
        reponse = api_client.post(
            reverse("platform-referential-measures", args=[sous_licence.slug]),
            {"domain_code": "organisation", "code": "A.5.3", "official_title": "Titre"},
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_400_BAD_REQUEST
        assert not Measure.objects.filter(referential=sous_licence, code="A.5.3").exists()

    def test_refuse_un_effort_inconnu(self, api_client, exploitant, sous_licence):
        reponse = api_client.post(
            reverse("platform-referential-measures", args=[sous_licence.slug]),
            {
                "domain_code": "organisation",
                "code": "A.5.4",
                "official_title": "Titre",
                "plain_language": "Énoncé ?",
                "effort": "enorme",
            },
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_400_BAD_REQUEST

    def test_un_commercial_lit_mais_n_edite_pas(self, api_client, commercial, sous_licence):
        entetes = _console(api_client, commercial)

        lecture = api_client.get(
            reverse("platform-referential-outline", args=[sous_licence.slug]), **entetes
        )
        ecriture = api_client.post(
            reverse("platform-referential-domains", args=[sous_licence.slug]),
            {"code": "interdit", "name": "Interdit"},
            format="json",
            **entetes,
        )

        assert lecture.status_code == status.HTTP_200_OK
        assert ecriture.status_code == status.HTTP_403_FORBIDDEN


# --- Composition (B2.5, B2.7) -----------------------------------------------


class TestComposition:
    def test_compose_un_modele_de_plateforme(
        self, api_client, exploitant, referential, tenant, voisin
    ):
        reponse = api_client.post(
            reverse("platform-referential-subsets", args=[referential.slug]),
            {"name": "Pour commencer", "measure_codes": _codes(referential)},
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_201_CREATED
        _, tenant_voisin = voisin
        # Un modèle de plateforme est proposable à tous.
        assert services.list_subsets(tenant).filter(slug="pour-commencer").exists()
        assert services.list_subsets(tenant_voisin).filter(slug="pour-commencer").exists()

    def test_compose_pour_un_client_et_lui_seul(
        self, api_client, exploitant, referential, tenant, voisin
    ):
        services.assign_referential(tenant=tenant, referential=referential)

        reponse = api_client.post(
            reverse("platform-referential-subsets", args=[referential.slug]),
            {
                "name": "Questionnaire du client",
                "measure_codes": _codes(referential),
                "tenant_id": str(tenant.id),
            },
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_201_CREATED
        _, tenant_voisin = voisin
        assert services.list_subsets(tenant).filter(slug="questionnaire-du-client").exists()
        assert (
            not services.list_subsets(tenant_voisin).filter(slug="questionnaire-du-client").exists()
        )

    def test_refuse_de_composer_pour_un_client_sans_attribution(
        self, api_client, exploitant, sous_licence, tenant
    ):
        # Precondition POSEE, pas supposee. Le conftest attribue aux clients les
        # referentiels deja crees, et l'ordre depend de la signature du test :
        # au premier passage, ce referentiel sous licence avait ete attribue
        # au client par ce seul effet d'ordre, et le test echouait pour une
        # raison etrangere a la garde qu'il verifie.
        services.assign_referential(tenant=tenant, referential=sous_licence)
        services.revoke_referential(tenant=tenant, referential=sous_licence)
        assert not services.is_readable(tenant, sous_licence)

        reponse = api_client.post(
            reverse("platform-referential-subsets", args=[sous_licence.slug]),
            {
                "name": "Impossible",
                "measure_codes": _codes(sous_licence, 1),
                "tenant_id": str(tenant.id),
            },
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_un_client_ne_peut_pas_reecrire_un_modele_de_plateforme(
        self, api_client, tenant, tenant_owner, referential
    ):
        """LE test d'intégrité : avant la garde, les mesures d'un modèle
        partagé étaient remplacées par celles du client, pour tout le monde."""
        codes = _codes(referential, 2)
        services.create_subset(
            referential=referential, slug="modele-partage", name="Modèle", measure_codes=codes
        )
        services.assign_referential(tenant=tenant, referential=referential)

        reponse = api_client.post(
            reverse("assessment-subset-list"),
            {
                "referential": referential.slug,
                "slug": "modele-partage",
                "name": "Détourné",
                "measure_codes": codes[:1],
            },
            format="json",
            **_client(api_client, tenant_owner, tenant),
        )

        assert reponse.status_code == status.HTTP_400_BAD_REQUEST
        modele = MeasureSubset.objects.get(referential=referential, slug="modele-partage")
        assert modele.owner_tenant_id is None
        assert len(services.subset_measure_ids(modele)) == 2


# --- Reformulation pour un client (B2.6) ------------------------------------


class TestReformulation:
    def test_pose_une_surcharge_sans_toucher_l_original(
        self, api_client, exploitant, referential, tenant, voisin
    ):
        services.assign_referential(tenant=tenant, referential=referential)
        mesure = Measure.objects.filter(referential=referential).first()
        origine = mesure.plain_language

        reponse = api_client.put(
            reverse("platform-client-overrides", args=[tenant.id]),
            {"measure_id": mesure.id, "plain_language": "Dit autrement, pour ce client ?"},
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_200_OK
        mesure.refresh_from_db()
        assert mesure.plain_language == origine
        assert services.list_overrides(tenant).count() == 1
        _, tenant_voisin = voisin
        assert services.list_overrides(tenant_voisin).count() == 0

    def test_retirer_la_surcharge_rend_l_enonce_d_origine(
        self, api_client, exploitant, referential, tenant
    ):
        services.assign_referential(tenant=tenant, referential=referential)
        mesure = Measure.objects.filter(referential=referential).first()
        services.set_measure_override(tenant=tenant, measure=mesure, plain_language="Autre")

        reponse = api_client.delete(
            reverse("platform-client-overrides", args=[tenant.id]),
            {"measure_id": mesure.id},
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert services.list_overrides(tenant).count() == 0

    def test_refuse_sur_un_referentiel_que_le_client_ne_lit_pas(
        self, api_client, exploitant, sous_licence, tenant
    ):
        # Precondition POSEE, pas supposee. Le conftest attribue aux clients les
        # referentiels deja crees, et l'ordre depend de la signature du test :
        # au premier passage, ce referentiel sous licence avait ete attribue
        # au client par ce seul effet d'ordre, et le test echouait pour une
        # raison etrangere a la garde qu'il verifie.
        services.assign_referential(tenant=tenant, referential=sous_licence)
        services.revoke_referential(tenant=tenant, referential=sous_licence)
        assert not services.is_readable(tenant, sous_licence)

        mesure = Measure.objects.get(referential=sous_licence, code="A.5.1")

        reponse = api_client.put(
            reverse("platform-client-overrides", args=[tenant.id]),
            {"measure_id": mesure.id, "plain_language": "Sans effet"},
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert services.list_overrides(tenant).count() == 0

    def test_refuse_une_reformulation_vide(self, api_client, exploitant, referential, tenant):
        services.assign_referential(tenant=tenant, referential=referential)
        mesure = Measure.objects.filter(referential=referential).first()

        reponse = api_client.put(
            reverse("platform-client-overrides", args=[tenant.id]),
            {"measure_id": mesure.id, "plain_language": "   "},
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_400_BAD_REQUEST


# --- Import par le client (B4.15) -------------------------------------------


def _fichier_json(slug="n-importe-quoi"):
    return json.dumps(
        {
            "slug": slug,
            "name": "Nom du fichier",
            "version": "1",
            "domains": [
                {
                    "code": "interne",
                    "name": "Règles internes",
                    "measures": [
                        {
                            "code": "1",
                            "title": "Charte signée",
                            "statement": "La charte est-elle signée ?",
                        }
                    ],
                }
            ],
        }
    )


class TestImportParLeClient:
    def test_l_apercu_n_ecrit_rien(self, api_client, tenant, tenant_owner):
        reponse = api_client.post(
            reverse("assessment-referential-import"),
            {"content": _fichier_json(), "name": "Nos règles"},
            format="json",
            **_client(api_client, tenant_owner, tenant),
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["preview"]["slug"].startswith(f"{tenant.slug}-")
        assert not Referential.objects.filter(slug=reponse.data["preview"]["slug"]).exists()

    def test_confirme_cree_un_referentiel_propre_et_attribue(
        self, api_client, tenant, tenant_owner
    ):
        reponse = api_client.post(
            reverse("assessment-referential-import"),
            {"content": _fichier_json(), "name": "Nos règles", "confirm": True},
            format="json",
            **_client(api_client, tenant_owner, tenant),
        )

        assert reponse.status_code == status.HTTP_201_CREATED
        referentiel = Referential.objects.get(slug=reponse.data["slug"])
        assert referentiel.kind == Referential.Kind.CUSTOM
        assert referentiel.owner_tenant_id == tenant.id
        assert services.is_granted(tenant, referentiel)

    def test_l_identifiant_du_fichier_ne_remplace_jamais_un_autre_referentiel(
        self, api_client, tenant, tenant_owner, referential
    ):
        """Un fichier qui porte l'identifiant d'un référentiel de plateforme
        ne doit pas pouvoir en remplacer le questionnaire pour tous."""
        avant = Measure.objects.filter(referential=referential).count()

        reponse = api_client.post(
            reverse("assessment-referential-import"),
            {"content": _fichier_json(slug=referential.slug), "name": "Piège", "confirm": True},
            format="json",
            **_client(api_client, tenant_owner, tenant),
        )

        assert reponse.status_code == status.HTTP_201_CREATED
        assert reponse.data["slug"] != referential.slug
        referential.refresh_from_db()
        assert referential.owner_tenant_id is None
        assert Measure.objects.filter(referential=referential).count() == avant

    def test_un_voisin_ne_le_voit_pas_et_ne_peut_pas_le_lire(
        self, api_client, tenant, tenant_owner, voisin
    ):
        cree = api_client.post(
            reverse("assessment-referential-import"),
            {"content": _fichier_json(), "name": "Confidentiel", "confirm": True},
            format="json",
            **_client(api_client, tenant_owner, tenant),
        )
        slug = cree.data["slug"]
        proprietaire_voisin, tenant_voisin = voisin
        entetes = _client(api_client, proprietaire_voisin, tenant_voisin)

        catalogue = api_client.get(reverse("assessment-referential-list"), **entetes)
        detail = api_client.get(reverse("assessment-referential-detail", args=[slug]), **entetes)

        assert slug not in [ligne["slug"] for ligne in catalogue.data]
        assert detail.status_code == status.HTTP_403_FORBIDDEN

    def test_la_console_ne_s_approprie_pas_un_referentiel_client_par_import(
        self, api_client, exploitant, tenant, tenant_owner
    ):
        cree = api_client.post(
            reverse("assessment-referential-import"),
            {"content": _fichier_json(), "name": "À nous", "confirm": True},
            format="json",
            **_client(api_client, tenant_owner, tenant),
        )
        slug = cree.data["slug"]

        reponse = api_client.post(
            reverse("platform-referential-import"),
            {
                "content": importers.modele_csv(),
                "format": "csv",
                "slug": slug,
                "name": "Réécrit",
                "version": "2",
                "confirm": True,
            },
            format="json",
            **_console(api_client, exploitant),
        )

        assert reponse.status_code == status.HTTP_409_CONFLICT
        referentiel = Referential.objects.get(slug=slug)
        assert referentiel.owner_tenant_id == tenant.id
        assert referentiel.name == "À nous"


# --- Règle d'architecture ---------------------------------------------------


class TestFrontieresEntreApps:
    def test_la_console_n_importe_pas_les_modeles_d_assessments(self):
        """CLAUDE.md, règle 1 : une app passe par les services d'une autre.
        Le correctif du compteur l'avait enfreinte ; le compte passe
        désormais par ``count_active_assignments``."""
        console = (
            pathlib.Path(__file__).resolve().parents[2] / "platform_admin" / "console_views.py"
        )

        assert "from apps.assessments.models import" not in console.read_text(encoding="utf-8")
