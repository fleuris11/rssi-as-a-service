"""Les rapports : des agrégats exacts, et aucun classement.

Deux tests portent une règle de droit plutôt qu'une règle de calcul : le suivi
nominatif ne contient aucun score, et sa consultation laisse une trace.
"""

from datetime import date, timedelta

import pytest

from apps.training import rapports, services
from apps.training.models import NominativeAccessLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def trois_salaries(tenant, tenant_owner, cours, bonnes_reponses):
    """Trois situations : pas commencé, en cours, terminé.

    C'est le jeu minimal qui rend les trois taux vérifiables de tête.
    """
    inscriptions = {}
    with services.contexte_du_client(tenant):
        services.attribuer_cours(tenant=tenant, course=cours, actor=tenant_owner)
        for nom, email in (
            ("Camille Martin", "camille@exemple.fr"),
            ("Dominique Leroy", "dominique@exemple.fr"),
            ("Alex Dubois", "alex@exemple.fr"),
        ):
            salarie = services.creer_apprenant(tenant=tenant, full_name=nom, email=email)
            inscription, _jeton = services.inscrire(
                tenant=tenant,
                learner=salarie,
                course=cours,
                due_date=date.today() + timedelta(days=7),
                actor=tenant_owner,
            )
            inscriptions[nom] = inscription

        ecrans = list(cours.published_version.screens.all())

        # Dominique a commencé sans finir.
        services.marquer_ecran_vu(
            enrollment=inscriptions["Dominique Leroy"], screen_id=ecrans[0].id
        )

        # Alex a tout terminé, en ratant une question au premier essai.
        alex = inscriptions["Alex Dubois"]
        for ecran in ecrans:
            services.marquer_ecran_vu(enrollment=alex, screen_id=ecran.id)
        services.soumettre_le_quiz(enrollment=alex, reponses=bonnes_reponses(fausses={1, 2}))
        services.soumettre_le_quiz(enrollment=alex, reponses=bonnes_reponses())

    return inscriptions


class TestAgregats:
    def test_compte_exactement_les_trois_etats(self, tenant, trois_salaries, cours):
        chiffres = rapports.agregats(tenant, course=cours)

        assert chiffres["learners_total"] == 3
        assert chiffres["not_started"] == 1
        assert chiffres["in_progress"] == 1
        assert chiffres["completed"] == 1
        assert chiffres["participation_rate"] == 67
        assert chiffres["success_rate"] == 33

    def test_la_moyenne_porte_sur_les_tentatives(self, tenant, trois_salaries, cours):
        # Alex a fait deux tentatives : 50 % puis 100 %. La moyenne est 75.
        chiffres = rapports.agregats(tenant, course=cours)

        assert chiffres["attempts_total"] == 2
        assert chiffres["average_score"] == 75

    def test_sans_personne_aucun_taux_ne_divise_par_zero(self, tenant, cours):
        chiffres = rapports.agregats(tenant, course=cours)

        assert chiffres["learners_total"] == 0
        assert chiffres["participation_rate"] == 0
        assert chiffres["average_score"] is None


class TestQuestionsLesPlusRatees:
    def test_ignore_une_question_trop_peu_repondue(self, tenant, trois_salaries, cours):
        # Deux tentatives seulement : en dessous de trois réponses, une
        # question ne dit rien — et sur une ou deux, elle désignerait
        # quelqu'un.
        assert rapports.questions_les_plus_ratees(tenant, course=cours) == []

    def test_classe_par_taux_d_echec(
        self, tenant, tenant_owner, cours, bonnes_reponses, trois_salaries
    ):
        # On amène la question 1 à quatre réponses, dont trois fausses.
        with services.contexte_du_client(tenant):
            for nom in ("Dominique Leroy",):
                inscription = trois_salaries[nom]
                for ecran in cours.published_version.screens.all():
                    services.marquer_ecran_vu(enrollment=inscription, screen_id=ecran.id)
                services.soumettre_le_quiz(
                    enrollment=inscription, reponses=bonnes_reponses(fausses={1, 3})
                )
                services.accorder_des_essais(enrollment=inscription, nombre=1)
                services.soumettre_le_quiz(
                    enrollment=inscription, reponses=bonnes_reponses(fausses={1})
                )

        lignes = rapports.questions_les_plus_ratees(tenant, course=cours)

        assert lignes
        # La question 1 a été ratée le plus souvent : elle arrive en tête.
        assert lignes[0]["failure_rate"] >= lignes[-1]["failure_rate"]
        assert lignes[0]["answers"] >= 3
        assert "screen_title" in lignes[0]


class TestEvolution:
    def test_une_campagne_est_un_cours_et_une_echeance(self, tenant, trois_salaries, cours):
        campagnes = rapports.campagnes(tenant)

        assert len(campagnes) == 1
        assert campagnes[0]["course_title"] == cours.title
        assert campagnes[0]["learners_total"] == 3
        assert campagnes[0]["participation_rate"] == 67


class TestSuiviNominatif:
    def test_ne_contient_aucun_score(self, tenant, tenant_owner, trois_salaries):
        """La règle du lot : pas de classement des salariés par score.

        Un module de sensibilisation qui produit un palmarès devient un outil
        de notation.
        """
        lignes = rapports.suivi_nominatif(tenant, actor=tenant_owner)

        assert lignes
        for ligne in lignes:
            assert "score" not in ligne
            assert "average_score" not in ligne
            assert set(ligne) == {
                "enrollment_id",
                "full_name",
                "email",
                "course_title",
                "due_date",
                "state",
                "overdue",
            }

    def test_trace_la_consultation(self, tenant, tenant_owner, trois_salaries):
        rapports.suivi_nominatif(tenant, actor=tenant_owner)

        trace = NominativeAccessLog.all_objects.filter(tenant=tenant).first()
        assert trace is not None
        assert trace.actor_id == tenant_owner.id
        assert trace.rows == 3

    def test_le_journal_ne_recopie_pas_les_donnees_qu_il_protege(
        self, tenant, tenant_owner, trois_salaries
    ):
        rapports.suivi_nominatif(tenant, actor=tenant_owner)

        trace = NominativeAccessLog.all_objects.get(tenant=tenant)
        # Un journal d'accès qui recopierait les noms serait un second fichier
        # du même traitement.
        assert not hasattr(trace, "learners")
        assert trace.rows == 3

    def test_classe_par_etat_puis_par_nom_jamais_par_resultat(
        self, tenant, tenant_owner, trois_salaries
    ):
        lignes = rapports.suivi_nominatif(tenant, actor=tenant_owner)

        etats = [ligne["state"] for ligne in lignes]
        assert etats == ["pas_commence", "en_cours", "termine"]


class TestEtancheite:
    def test_un_client_ne_voit_pas_les_chiffres_d_un_autre(
        self, tenant, trois_salaries, user_factory, tenant_factory
    ):
        autre_proprietaire = user_factory(email="ailleurs@example.com")
        autre = tenant_factory(autre_proprietaire, name="Autre Entreprise")

        assert rapports.agregats(autre)["learners_total"] == 0
        assert rapports.campagnes(autre) == []
        assert rapports.suivi_nominatif(autre, actor=autre_proprietaire) == []
