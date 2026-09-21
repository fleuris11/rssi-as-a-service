"""L'API du pilotage : qui voit quoi, et ce qui est tracé.

La séparation vérifiée ici n'est pas technique mais juridique : les agrégats
sont ouverts à tout membre, le **nominatif** est réservé aux administrateurs
et sa consultation laisse une trace (ADR-041).
"""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from rest_framework import status

from apps.billing import features
from apps.billing.models import Subscription
from apps.tenants.models import Membership
from apps.training import preuves, services
from apps.training.models import NominativeAccessLog

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "Str0ng!Passw0rd123"


def _auth(api_client, user, tenant):
    reponse = api_client.post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": MOT_DE_PASSE},
        format="json",
    )
    return {
        "HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


def _accorder(tenant, cles):
    abonnement = Subscription.objects.get(tenant=tenant)
    abonnement.override_features = list(cles)
    abonnement.save(update_fields=["override_features"])


@pytest.fixture(autouse=True)
def _formation_incluse(tenant):
    _accorder(tenant, [features.TRAINING])


@pytest.fixture
def entetes(api_client, tenant, tenant_owner):
    return _auth(api_client, tenant_owner, tenant)


@pytest.fixture
def lecteur(tenant, user_factory):
    utilisateur = user_factory(email="lecteur@example.com")
    Membership.all_objects.create(tenant=tenant, user=utilisateur, role=Membership.Role.READER)
    return utilisateur


@pytest.fixture
def campagne(tenant, tenant_owner, cours, bonnes_reponses):
    with services.contexte_du_client(tenant):
        services.attribuer_cours(tenant=tenant, course=cours, actor=tenant_owner)
        salarie = services.creer_apprenant(
            tenant=tenant, full_name="Camille Martin", email="camille@exemple.fr"
        )
        inscription, _jeton = services.inscrire(
            tenant=tenant,
            learner=salarie,
            course=cours,
            due_date=date.today() + timedelta(days=7),
            actor=tenant_owner,
        )
        for ecran in cours.published_version.screens.all():
            services.marquer_ecran_vu(enrollment=inscription, screen_id=ecran.id)
        services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses())
    return inscription


class TestRapport:
    def test_un_membre_lit_les_agregats(self, api_client, tenant, lecteur, campagne):
        reponse = api_client.get(reverse("formation-rapport"), **_auth(api_client, lecteur, tenant))

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["summary"]["learners_total"] == 1

    def test_l_export_tableur_s_ouvre_dans_un_tableur_francais(self, api_client, entetes, campagne):
        reponse = api_client.get(reverse("formation-rapport-export", args=["csv"]), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        contenu = reponse.content.decode("utf-8")
        # BOM et point-virgule : sans eux, les accents sortent en mojibake et
        # tout atterrit dans une seule colonne.
        assert contenu.startswith("﻿")
        assert ";" in contenu
        assert "Taux de participation" in contenu

    def test_l_export_ne_contient_aucun_nom_de_salarie(self, api_client, entetes, campagne):
        reponse = api_client.get(reverse("formation-rapport-export", args=["csv"]), **entetes)

        # Un export se transfère et finit dans un dossier partagé.
        assert "Camille Martin" not in reponse.content.decode("utf-8")

    def test_l_export_pdf_est_un_pdf(self, api_client, entetes, campagne):
        reponse = api_client.get(reverse("formation-rapport-export", args=["pdf"]), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse["Content-Type"] == "application/pdf"
        assert reponse.content[:4] == b"%PDF"


class TestSuiviNominatif:
    def test_un_lecteur_n_y_a_pas_acces(self, api_client, tenant, lecteur, campagne):
        reponse = api_client.get(reverse("formation-suivi"), **_auth(api_client, lecteur, tenant))

        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_un_administrateur_y_accede_et_c_est_trace(
        self, api_client, tenant, tenant_owner, entetes, campagne
    ):
        reponse = api_client.get(reverse("formation-suivi"), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["results"][0]["full_name"] == "Camille Martin"
        assert "score" not in reponse.data["results"][0]
        assert NominativeAccessLog.all_objects.filter(tenant=tenant).count() == 1

    def test_dit_a_quoi_sert_cette_liste(self, api_client, entetes, campagne):
        reponse = api_client.get(reverse("formation-suivi"), **entetes)

        # La phrase est dans la réponse : celui qui la consulte doit savoir
        # que c'est enregistré.
        assert "enregistrée" in reponse.data["notice"]


class TestRelances:
    def test_un_administrateur_coupe_les_relances(self, api_client, entetes):
        reponse = api_client.put(
            reverse("formation-relances"), {"enabled": False}, format="json", **entetes
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["enabled"] is False

    def test_un_lecteur_ne_regle_rien(self, api_client, tenant, lecteur):
        reponse = api_client.put(
            reverse("formation-relances"),
            {"enabled": False},
            format="json",
            **_auth(api_client, lecteur, tenant),
        )

        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_hors_offre_le_reglage_est_refuse_en_402(self, api_client, tenant, entetes):
        _accorder(tenant, [])

        reponse = api_client.put(
            reverse("formation-relances"), {"enabled": False}, format="json", **entetes
        )

        assert reponse.status_code == status.HTTP_402_PAYMENT_REQUIRED


class TestImport:
    def test_importe_une_liste(self, api_client, entetes, tenant):
        reponse = api_client.post(
            reverse("formation-import"),
            {"content": "Alex Dubois;alex@exemple.fr\nJean Petit;jean@exemple.fr"},
            format="json",
            **entetes,
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert len(reponse.data["crees"]) == 2

    def test_rend_le_detail_ligne_par_ligne(self, api_client, entetes):
        reponse = api_client.post(
            reverse("formation-import"),
            {"content": "Alex Dubois;alex@exemple.fr\nCassé"},
            format="json",
            **entetes,
        )

        assert reponse.data["invalides"][0]["ligne"] == 2

    def test_un_fichier_illisible_est_refuse_avec_une_phrase(self, api_client, entetes):
        reponse = api_client.post(
            reverse("formation-import"), {"content": "n'importe quoi"}, format="json", **entetes
        )

        assert reponse.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "point-virgule" in reponse.data["detail"]


class TestPreuves:
    @pytest.fixture
    def proposition(self, tenant, tenant_owner, cours, bonnes_reponses):
        with services.contexte_du_client(tenant):
            services.attribuer_cours(tenant=tenant, course=cours, actor=tenant_owner)
            for rang in range(3):
                salarie = services.creer_apprenant(
                    tenant=tenant, full_name=f"Salarié {rang}", email=f"s{rang}@exemple.fr"
                )
                inscription, _jeton = services.inscrire(
                    tenant=tenant,
                    learner=salarie,
                    course=cours,
                    due_date=date.today() + timedelta(days=7),
                    actor=tenant_owner,
                )
                for ecran in cours.published_version.screens.all():
                    services.marquer_ecran_vu(enrollment=inscription, screen_id=ecran.id)
                services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses())
            return preuves.proposer(tenant)[0]

    def test_la_proposition_est_servie_avec_sa_preuve(self, api_client, entetes, proposition):
        reponse = api_client.get(reverse("formation-preuves"), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data[0]["participation_rate"] == 100
        # La phrase de preuve est servie telle qu'elle sera déposée.
        assert "Campagne de formation" in reponse.data[0]["evidence"]

    def test_sans_diagnostic_ouvert_la_confirmation_explique(
        self, api_client, entetes, proposition, referential
    ):
        reponse = api_client.post(reverse("formation-preuve", args=[proposition.id]), **entetes)

        assert reponse.status_code == status.HTTP_409_CONFLICT
        assert "Aucun diagnostic" in reponse.data["detail"]

    def test_un_lecteur_ne_confirme_rien(self, api_client, tenant, lecteur, proposition):
        reponse = api_client.post(
            reverse("formation-preuve", args=[proposition.id]),
            **_auth(api_client, lecteur, tenant),
        )

        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_ecarter_une_proposition(self, api_client, entetes, proposition):
        reponse = api_client.delete(reverse("formation-preuve", args=[proposition.id]), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["status"] == "dismissed"

    def test_la_proposition_d_un_autre_client_n_existe_pas(
        self, api_client, proposition, user_factory, tenant_factory
    ):
        autre_proprietaire = user_factory(email="ailleurs@example.com")
        autre = tenant_factory(autre_proprietaire, name="Autre Entreprise")
        _accorder(autre, [features.TRAINING])

        reponse = api_client.post(
            reverse("formation-preuve", args=[proposition.id]),
            **_auth(api_client, autre_proprietaire, autre),
        )

        assert reponse.status_code == status.HTTP_404_NOT_FOUND
