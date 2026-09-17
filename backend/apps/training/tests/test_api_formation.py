"""Les deux surfaces HTTP, et surtout ce qu'elles refusent.

Trois cloisonnements distincts sont vérifiés ici, et il ne faut pas les
confondre :

1. entre entreprises — un administrateur de B ne voit rien de A ;
2. entre apprenants d'une même entreprise — un jeton ne donne accès qu'à SON
   inscription, jamais à celle d'un collègue ;
3. entre rôles — décider qui doit être formé est un acte de gestion.
"""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from rest_framework import status

from apps.billing import features
from apps.billing.models import Subscription
from apps.tenants.models import Membership
from apps.training import services

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
    """Par défaut, l'offre du client comprend la formation. Les tests de garde
    la retirent explicitement — c'est la variable sous test, elle doit être
    visible dans le test qui la manipule."""
    _accorder(tenant, [features.TRAINING])


def _jeton(entetes_jeton):
    return {"HTTP_X_FORMATION_TOKEN": entetes_jeton}


class TestEspaceApprenant:
    def test_sans_jeton_repond_une_explication_et_non_une_erreur_technique(self, api_client):
        reponse = api_client.get(reverse("formation-session"))
        assert reponse.status_code == status.HTTP_404_NOT_FOUND
        # ``reason`` permet à l'interface d'afficher une page de lien expiré
        # plutôt qu'un message d'erreur — un salarié qui lit « 403 Forbidden »
        # abandonne.
        assert reponse.data["reason"] == "link"

    def test_un_jeton_valable_sert_le_cours_et_la_progression(self, api_client, jeton):
        reponse = api_client.get(reverse("formation-session"), **_jeton(jeton))

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["learner_name"] == "Camille Martin"
        assert reponse.data["screens_total"] == 3
        assert reponse.data["screens_completed"] == 0
        assert reponse.data["quiz_unlocked"] is False

    def test_ne_sert_jamais_les_bonnes_reponses(self, api_client, jeton):
        reponse = api_client.get(reverse("formation-session"), **_jeton(jeton))
        corps = str(reponse.data)
        assert "is_correct" not in corps

    def test_le_parcours_complet_delivre_une_attestation(
        self, api_client, jeton, inscription, bonnes_reponses
    ):
        for ecran in inscription.version.screens.all():
            reponse = api_client.post(
                reverse("formation-ecran"),
                {"screen_id": str(ecran.id)},
                format="json",
                **_jeton(jeton),
            )
            assert reponse.status_code == status.HTTP_200_OK

        assert reponse.data["quiz_unlocked"] is True

        resultat = api_client.post(
            reverse("formation-quiz"),
            {"answers": bonnes_reponses()},
            format="json",
            **_jeton(jeton),
        )
        assert resultat.status_code == status.HTTP_200_OK
        assert resultat.data["passed"] is True
        assert resultat.data["certificate"]["serial"]

        pdf = api_client.get(reverse("formation-attestation"), **_jeton(jeton))
        assert pdf.status_code == status.HTTP_200_OK
        assert pdf["Content-Type"] == "application/pdf"
        assert pdf.content[:4] == b"%PDF"

    def test_le_quiz_soumis_trop_tot_est_refuse_sans_consommer_d_essai(
        self, api_client, jeton, bonnes_reponses
    ):
        reponse = api_client.post(
            reverse("formation-quiz"),
            {"answers": bonnes_reponses()},
            format="json",
            **_jeton(jeton),
        )
        assert reponse.status_code == status.HTTP_409_CONFLICT

    def test_l_attestation_n_existe_pas_avant_la_reussite(self, api_client, jeton):
        reponse = api_client.get(reverse("formation-attestation"), **_jeton(jeton))
        assert reponse.status_code == status.HTTP_404_NOT_FOUND

    def test_les_deux_points_d_entree_decrivent_l_etat_de_la_meme_facon(
        self, api_client, jeton, inscription
    ):
        """L'état initial et l'état renvoyé après un écran terminé ont la même
        forme.

        Le défaut que ce test épingle a été trouvé en navigateur, pas ici :
        le second omettait le quiz, et l'interface — qui remplace sa session
        par la réponse reçue — arrivait au dernier écran avec un questionnaire
        disparu. Chaque point d'entrée, pris isolément, répondait correctement.
        """
        initial = api_client.get(reverse("formation-session"), **_jeton(jeton))
        ecran = inscription.version.screens.first()
        apres = api_client.post(
            reverse("formation-ecran"),
            {"screen_id": str(ecran.id)},
            format="json",
            **_jeton(jeton),
        )

        assert set(initial.data) == set(apres.data)
        assert apres.data["quiz"], "Le quiz doit être servi par les deux points d'entrée."

    def test_un_jeton_inconnu_est_indiscernable_d_un_jeton_expire(self, api_client, jeton):
        inconnu = api_client.get(reverse("formation-session"), **_jeton("jeton-invente"))
        assert inconnu.status_code == status.HTTP_404_NOT_FOUND
        assert inconnu.data["reason"] == "link"


class TestEtancheiteEntreApprenants:
    @pytest.fixture
    def collegue(self, tenant, tenant_owner, cours):
        """Un second salarié de LA MÊME entreprise, avec sa propre
        inscription — le cas que le cloisonnement par entreprise ne couvre
        pas."""
        with services.contexte_du_client(tenant):
            salarie = services.creer_apprenant(
                tenant=tenant,
                full_name="Dominique Leroy",
                email="dominique.leroy@exemple.fr",
                actor=tenant_owner,
            )
            return services.inscrire(
                tenant=tenant,
                learner=salarie,
                course=cours,
                due_date=date.today() + timedelta(days=14),
                actor=tenant_owner,
            )

    def test_un_jeton_ne_montre_que_son_propre_parcours(self, api_client, jeton, collegue):
        reponse = api_client.get(reverse("formation-session"), **_jeton(jeton))
        assert reponse.data["learner_name"] == "Camille Martin"
        assert "Dominique" not in str(reponse.data)

    def test_la_progression_de_l_un_n_avance_pas_celle_de_l_autre(
        self, api_client, jeton, inscription, collegue
    ):
        inscription_collegue, jeton_collegue = collegue
        ecran = inscription.version.screens.first()

        api_client.post(
            reverse("formation-ecran"),
            {"screen_id": str(ecran.id)},
            format="json",
            **_jeton(jeton),
        )

        chez_le_collegue = api_client.get(
            reverse("formation-session"), **_jeton(jeton_collegue)
        )
        assert chez_le_collegue.data["screens_completed"] == 0


class TestEtancheiteEntreEntreprises:
    @pytest.fixture
    def autre_entreprise(self, user_factory, tenant_factory, cours):
        proprietaire = user_factory(email="ailleurs@example.com")
        autre = tenant_factory(proprietaire, name="Autre Entreprise")
        _accorder(autre, [features.TRAINING])
        with services.contexte_du_client(autre):
            services.attribuer_cours(tenant=autre, course=cours, actor=proprietaire)
            salarie = services.creer_apprenant(
                tenant=autre,
                full_name="Alex Dubois",
                email="alex.dubois@ailleurs.fr",
                actor=proprietaire,
            )
            services.inscrire(
                tenant=autre,
                learner=salarie,
                course=cours,
                due_date=date.today() + timedelta(days=14),
                actor=proprietaire,
            )
        return autre, proprietaire

    def test_un_administrateur_ne_voit_que_les_inscriptions_de_son_entreprise(
        self, api_client, tenant, tenant_owner, inscription, autre_entreprise
    ):
        entetes = _auth(api_client, tenant_owner, tenant)
        reponse = api_client.get(reverse("formation-inscriptions"), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        noms = [ligne["learner"]["full_name"] for ligne in reponse.data]
        assert noms == ["Camille Martin"]

    def test_un_administrateur_ne_voit_que_ses_salaries(
        self, api_client, tenant, tenant_owner, salarie, autre_entreprise
    ):
        entetes = _auth(api_client, tenant_owner, tenant)
        reponse = api_client.get(reverse("formation-salaries"), **entetes)

        assert [ligne["email"] for ligne in reponse.data] == ["camille.martin@exemple.fr"]

    def test_ne_peut_pas_agir_sur_l_inscription_d_une_autre_entreprise(
        self, api_client, tenant, tenant_owner, autre_entreprise
    ):
        from apps.training.models import Enrollment

        autre, _proprietaire = autre_entreprise
        etrangere = Enrollment.all_objects.get(tenant=autre)

        entetes = _auth(api_client, tenant_owner, tenant)
        reponse = api_client.delete(
            reverse("formation-inscription", args=[etrangere.id]), **entetes
        )

        assert reponse.status_code == status.HTTP_404_NOT_FOUND
        etrangere.refresh_from_db()
        assert etrangere.revoked_at is None


class TestRoles:
    @pytest.fixture
    def lecteur(self, tenant, user_factory):
        utilisateur = user_factory(email="lecteur@example.com")
        Membership.all_objects.create(
            tenant=tenant, user=utilisateur, role=Membership.Role.READER
        )
        return utilisateur

    @pytest.fixture
    def contributeur(self, tenant, user_factory):
        utilisateur = user_factory(email="contrib@example.com")
        Membership.all_objects.create(
            tenant=tenant, user=utilisateur, role=Membership.Role.CONTRIBUTOR
        )
        return utilisateur

    def test_un_membre_peut_lire_la_liste(self, api_client, tenant, lecteur):
        entetes = _auth(api_client, lecteur, tenant)
        reponse = api_client.get(reverse("formation-inscriptions"), **entetes)
        assert reponse.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize("role", ["lecteur", "contributeur"])
    def test_seul_un_administrateur_inscrit_un_salarie(
        self, request, api_client, tenant, salarie, cours, role
    ):
        utilisateur = request.getfixturevalue(role)
        entetes = _auth(api_client, utilisateur, tenant)
        reponse = api_client.post(
            reverse("formation-inscriptions"),
            {
                "learner_id": str(salarie.id),
                "course_slug": cours.slug,
                "due_date": str(date.today() + timedelta(days=14)),
            },
            format="json",
            **entetes,
        )
        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_un_anonyme_n_atteint_pas_le_pilotage(self, api_client):
        reponse = api_client.get(reverse("formation-inscriptions"))
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_un_membre_du_client_ne_peut_pas_composer_sa_propre_offre(
        self, api_client, tenant, tenant_owner, salarie, cours
    ):
        """L'administrateur de l'ENTREPRISE gère ses formations ; il ne
        s'accorde pas la fonctionnalité. Retirée de son offre, elle le reste."""
        _accorder(tenant, [])
        entetes = _auth(api_client, tenant_owner, tenant)
        reponse = api_client.post(
            reverse("formation-inscriptions"),
            {
                "learner_id": str(salarie.id),
                "course_slug": cours.slug,
                "due_date": str(date.today() + timedelta(days=14)),
            },
            format="json",
            **entetes,
        )
        assert reponse.status_code == status.HTTP_402_PAYMENT_REQUIRED


class TestGardeDeFonctionnalite:
    def test_hors_offre_la_lecture_reste_servie(self, api_client, tenant, tenant_owner, salarie):
        """Un client qui perd la fonctionnalité garde l'accès en lecture à ce
        qu'il a produit (ADR-019) : les attestations déjà délivrées ne
        disparaissent pas parce que l'abonnement a changé."""
        _accorder(tenant, [])
        entetes = _auth(api_client, tenant_owner, tenant)

        assert (
            api_client.get(reverse("formation-inscriptions"), **entetes).status_code
            == status.HTTP_200_OK
        )
        assert (
            api_client.get(reverse("formation-salaries"), **entetes).status_code
            == status.HTTP_200_OK
        )

    def test_hors_offre_l_ecriture_est_refusee_en_402(
        self, api_client, tenant, tenant_owner
    ):
        _accorder(tenant, [])
        entetes = _auth(api_client, tenant_owner, tenant)
        reponse = api_client.post(
            reverse("formation-salaries"),
            {"full_name": "Nouvelle Recrue", "email": "recrue@exemple.fr"},
            format="json",
            **entetes,
        )
        assert reponse.status_code == status.HTTP_402_PAYMENT_REQUIRED
        assert "feature" in reponse.data


class TestEmissionDuLien:
    def test_le_lien_n_est_rendu_qu_a_l_emission(
        self, api_client, tenant, tenant_owner, salarie, cours
    ):
        entetes = _auth(api_client, tenant_owner, tenant)
        creation = api_client.post(
            reverse("formation-inscriptions"),
            {
                "learner_id": str(salarie.id),
                "course_slug": cours.slug,
                "due_date": str(date.today() + timedelta(days=14)),
            },
            format="json",
            **entetes,
        )
        assert creation.status_code == status.HTTP_201_CREATED
        assert "/formation/" in creation.data["link"]

        # La relecture de la liste ne le redonne jamais : il n'est stocké que
        # haché, il n'existe en clair que dans la réponse ci-dessus.
        liste = api_client.get(reverse("formation-inscriptions"), **entetes)
        assert all("link" not in ligne for ligne in liste.data)
