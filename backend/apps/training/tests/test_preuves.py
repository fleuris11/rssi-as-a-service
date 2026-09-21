"""La formation comme preuve d'une mesure du diagnostic.

Le test central de ce fichier est ``test_proposer_ne_coche_jamais_rien`` : le
produit refuse depuis le début de renseigner une mesure de conformité à la
place de quelqu'un. Tout le reste n'est que le chemin qui mène à une
confirmation humaine.
"""

from datetime import date, timedelta

import pytest

from apps.assessments import services as assessments
from apps.assessments.models import Answer
from apps.training import preuves, services
from apps.training.models import MeasureSuggestion

pytestmark = pytest.mark.django_db


def _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses, combien=3):
    with services.contexte_du_client(tenant):
        services.attribuer_cours(tenant=tenant, course=cours, actor=tenant_owner)
        for rang in range(combien):
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


class TestSeuils:
    def test_une_campagne_trop_petite_ne_prouve_rien(
        self, tenant, tenant_owner, cours, bonnes_reponses
    ):
        # Deux salariés sur deux : statistiquement muet, et cela désigne des
        # personnes.
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses, combien=2)

        with services.contexte_du_client(tenant):
            assert preuves.proposer(tenant) == []

    def test_une_campagne_a_demi_suivie_ne_prouve_rien(
        self, tenant, tenant_owner, cours, bonnes_reponses
    ):
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses, combien=3)
        with services.contexte_du_client(tenant):
            # Deux inscrits de plus qui n'ouvrent rien : 3 terminés sur 5,
            # soit 60 % — sous le seuil unique de réussite.
            for rang in (8, 9):
                salarie = services.creer_apprenant(
                    tenant=tenant, full_name=f"Absent {rang}", email=f"a{rang}@exemple.fr"
                )
                services.inscrire(
                    tenant=tenant,
                    learner=salarie,
                    course=cours,
                    due_date=date.today() + timedelta(days=7),
                    actor=tenant_owner,
                )

            assert preuves.proposer(tenant) == []

    def test_une_campagne_suivie_et_reussie_est_proposee(
        self, tenant, tenant_owner, cours, bonnes_reponses
    ):
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses)

        with services.contexte_du_client(tenant):
            proposees = preuves.proposer(tenant)

        assert len(proposees) == 1
        proposition = proposees[0]
        assert proposition.status == MeasureSuggestion.Status.PENDING
        assert proposition.participation_rate == 100
        assert proposition.success_rate == 100
        assert proposition.learners_total == 3


class TestProposerNeValidePas:
    def test_proposer_ne_coche_jamais_rien(
        self, tenant, tenant_owner, cours, bonnes_reponses, assessment
    ):
        """LE test du lot.

        Une mesure de conformité cochée sans que personne l'ait décidée est
        une affirmation que le client n'a pas faite, et qu'il découvrirait
        devant un auditeur.
        """
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses)

        with services.contexte_du_client(tenant):
            preuves.proposer(tenant)

        assert Answer.all_objects.filter(assessment=assessment).count() == 0

    def test_ne_repropose_pas_ce_qui_a_ete_ecarte(
        self, tenant, tenant_owner, cours, bonnes_reponses
    ):
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses)
        with services.contexte_du_client(tenant):
            proposition = preuves.proposer(tenant)[0]
            preuves.ecarter(suggestion=proposition, actor=tenant_owner)

            # Reproposer chaque nuit ce que le client vient de refuser le
            # transformerait en automate insistant.
            assert preuves.proposer(tenant) == []

    def test_est_idempotent(self, tenant, tenant_owner, cours, bonnes_reponses):
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses)

        with services.contexte_du_client(tenant):
            preuves.proposer(tenant)
            preuves.proposer(tenant)

            assert MeasureSuggestion.objects.count() == 1


class TestConfirmation:
    def test_reporte_la_preuve_dans_le_diagnostic_en_cours(
        self, tenant, tenant_owner, cours, bonnes_reponses, assessment
    ):
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses)

        with services.contexte_du_client(tenant):
            proposition = preuves.proposer(tenant)[0]
            preuves.confirmer(suggestion=proposition, actor=tenant_owner)

        reponse = Answer.all_objects.get(assessment=assessment, measure__code=preuves.MESURE)
        assert reponse.value == "yes"
        # La note porte les chiffres : c'est elle que lira l'auditeur.
        assert "100 % de participation" in reponse.note
        assert cours.title in reponse.note
        assert "confirmé par un administrateur" in reponse.note

    def test_garde_la_trace_de_qui_a_tranche(
        self, tenant, tenant_owner, cours, bonnes_reponses, assessment
    ):
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses)

        with services.contexte_du_client(tenant):
            proposition = preuves.proposer(tenant)[0]
            preuves.confirmer(suggestion=proposition, actor=tenant_owner)

        proposition.refresh_from_db()
        assert proposition.status == MeasureSuggestion.Status.ACCEPTED
        assert proposition.decided_by_id == tenant_owner.id
        assert proposition.decided_at is not None

    def test_refuse_quand_aucun_diagnostic_n_est_ouvert(
        self, tenant, tenant_owner, cours, bonnes_reponses, referential
    ):
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses)

        with services.contexte_du_client(tenant):
            proposition = preuves.proposer(tenant)[0]
            with pytest.raises(preuves.PreuveError) as refus:
                preuves.confirmer(suggestion=proposition, actor=tenant_owner)

        # Ouvrir un diagnostic à la place du client serait précisément la
        # décision qu'on lui laisse.
        assert "Aucun diagnostic n'est en cours" in str(refus.value)

    def test_ne_se_confirme_pas_deux_fois(
        self, tenant, tenant_owner, cours, bonnes_reponses, assessment
    ):
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses)

        with services.contexte_du_client(tenant):
            proposition = preuves.proposer(tenant)[0]
            preuves.confirmer(suggestion=proposition, actor=tenant_owner)

            with pytest.raises(preuves.PreuveError):
                preuves.confirmer(suggestion=proposition, actor=tenant_owner)

    def test_n_ecrit_pas_dans_un_diagnostic_termine(
        self, tenant, tenant_owner, cours, bonnes_reponses, assessment
    ):
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses)
        # Terminer un diagnostic exige que toutes ses mesures soient
        # répondues : on le remplit avant de le clore.
        for mesure in assessments.get_assessment_measures(assessment):
            assessments.submit_answer(assessment=assessment, measure=mesure, value="no")
        assessments.complete_assessment(assessment)

        with services.contexte_du_client(tenant):
            proposition = preuves.proposer(tenant)[0]
            with pytest.raises(preuves.PreuveError):
                preuves.confirmer(suggestion=proposition, actor=tenant_owner)


class TestEtancheite:
    def test_la_proposition_d_un_client_n_existe_pas_pour_un_autre(
        self, tenant, tenant_owner, cours, bonnes_reponses, user_factory, tenant_factory
    ):
        _campagne_reussie(tenant, tenant_owner, cours, bonnes_reponses)
        with services.contexte_du_client(tenant):
            preuves.proposer(tenant)

        autre_proprietaire = user_factory(email="ailleurs@example.com")
        autre = tenant_factory(autre_proprietaire, name="Autre Entreprise")
        with services.contexte_du_client(autre):
            assert list(preuves.en_attente(autre)) == []
