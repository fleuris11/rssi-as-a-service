"""Le parcours, au niveau des services.

Ces tests appellent les services directement, dans un contexte de client posé
explicitement — exactement comme le font les vues. Un test qui s'en
dispenserait passerait à côté du cloisonnement, puisque le manager par défaut
échoue fermé : il rendrait des ensembles vides et les assertions « rien ne
fuite » seraient vraies pour la mauvaise raison.
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.training import services
from apps.training.models import Attempt, Certificate, Enrollment, ScreenProgress

pytestmark = pytest.mark.django_db


def _terminer_les_ecrans(inscription, combien=None):
    ecrans = list(inscription.version.screens.all())
    for ecran in ecrans[: combien if combien is not None else len(ecrans)]:
        services.marquer_ecran_vu(enrollment=inscription, screen_id=ecran.id)


class TestReprise:
    def test_reprend_au_premier_ecran_non_termine(self, tenant, inscription):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription, combien=1)
            etat = services.etat_de_session(inscription)

        assert etat["screens_completed"] == 1
        # Index 1 = le deuxième écran. C'est ce que l'interface annonce :
        # « vous reprenez à l'écran 2 sur 3 ».
        assert etat["resume_index"] == 1
        assert etat["screens_total"] == 3

    def test_revenir_en_arriere_ne_fait_pas_reculer_la_progression(self, tenant, inscription):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            premier = inscription.version.screens.first()
            # Le salarié revient sur l'écran 1 et le « re-termine ».
            services.marquer_ecran_vu(enrollment=inscription, screen_id=premier.id)
            etat = services.etat_de_session(inscription)

        assert etat["screens_completed"] == 3
        assert ScreenProgress.all_objects.filter(enrollment=inscription).count() == 3

    def test_un_ecran_d_un_autre_cours_est_refuse(self, tenant, inscription, db):
        from apps.training.models import Course, CourseVersion, Screen

        autre = Course.objects.create(slug="autre", title="Autre cours")
        version = CourseVersion.objects.create(course=autre, number=1)
        intrus = Screen.objects.create(
            version=version,
            order=1,
            title="Intrus",
            content=[{"type": "paragraphe", "texte": "Ailleurs."}],
        )
        with services.contexte_du_client(tenant), pytest.raises(services.TrainingError):
            services.marquer_ecran_vu(enrollment=inscription, screen_id=intrus.id)


class TestQuizEtSeuil:
    def test_le_quiz_reste_ferme_tant_que_le_cours_n_est_pas_parcouru(
        self, tenant, inscription, bonnes_reponses
    ):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription, combien=2)
            etat = services.etat_de_session(inscription)
            assert etat["quiz_unlocked"] is False

            with pytest.raises(services.QuizRefuse) as refus:
                services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses())
        assert "Terminez d'abord les écrans" in str(refus.value)

    def test_trois_bonnes_sur_quatre_atteint_le_seuil_de_75(
        self, tenant, inscription, bonnes_reponses
    ):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            resultat = services.soumettre_le_quiz(
                enrollment=inscription, reponses=bonnes_reponses(fausses={4})
            )

        assert resultat["score"] == 75
        assert resultat["passed"] is True

    def test_deux_bonnes_sur_quatre_echoue(self, tenant, inscription, bonnes_reponses):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            resultat = services.soumettre_le_quiz(
                enrollment=inscription, reponses=bonnes_reponses(fausses={3, 4})
            )

        assert resultat["score"] == 50
        assert resultat["passed"] is False
        assert Certificate.all_objects.filter(enrollment=inscription).count() == 0

    def test_une_question_sans_reponse_est_refusee_et_non_comptee_fausse(
        self, tenant, inscription, bonnes_reponses
    ):
        reponses = bonnes_reponses()
        reponses.pop(next(iter(reponses)))
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            with pytest.raises(services.QuizRefuse) as refus:
                services.soumettre_le_quiz(enrollment=inscription, reponses=reponses)

        assert "sans réponse" in str(refus.value)
        # Rien n'a été enregistré : ne pas répondre n'est pas se tromper, et
        # ne doit donc pas consommer un essai.
        assert Attempt.all_objects.filter(enrollment=inscription).count() == 0

    def test_les_bonnes_reponses_ne_sont_jamais_envoyees_au_navigateur(self, tenant, inscription):
        with services.contexte_du_client(tenant):
            questions = services.questions_du_quiz(inscription)

        assert questions
        for question in questions:
            for choix in question["choices"]:
                assert "is_correct" not in choix
                assert set(choix) == {"id", "text"}


class TestExplicationsEtRevision:
    def test_chaque_question_est_expliquee_meme_quand_elle_est_juste(
        self, tenant, inscription, bonnes_reponses
    ):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            resultat = services.soumettre_le_quiz(
                enrollment=inscription, reponses=bonnes_reponses(fausses={4})
            )

        assert len(resultat["questions"]) == 4
        for question in resultat["questions"]:
            assert question["explanation"]

    def test_ne_propose_que_les_ecrans_des_questions_ratees(
        self, tenant, inscription, bonnes_reponses
    ):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            resultat = services.soumettre_le_quiz(
                enrollment=inscription, reponses=bonnes_reponses(fausses={4})
            )

        # La question 4 porte sur l'écran 3, et elle seule a été ratée.
        assert [ecran["title"] for ecran in resultat["screens_to_review"]] == ["Écran 3"]

    def test_deux_questions_ratees_sur_le_meme_ecran_ne_le_citent_qu_une_fois(
        self, tenant, inscription, bonnes_reponses
    ):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            # Les questions 1 et 2 portent toutes deux sur l'écran 1.
            resultat = services.soumettre_le_quiz(
                enrollment=inscription, reponses=bonnes_reponses(fausses={1, 2})
            )

        assert [ecran["title"] for ecran in resultat["screens_to_review"]] == ["Écran 1"]


class TestLimiteDEssais:
    def test_les_essais_sont_comptes_et_la_limite_tient(
        self, tenant, inscription, bonnes_reponses
    ):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses({3, 4}))
            services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses({3, 4}))

            with pytest.raises(services.QuizRefuse) as refus:
                services.soumettre_le_quiz(
                    enrollment=inscription, reponses=bonnes_reponses({3, 4})
                )

        assert "essais" in str(refus.value)
        assert Attempt.all_objects.filter(enrollment=inscription).count() == 2

    def test_le_rearmement_rouvre_exactement_un_essai(
        self, tenant, tenant_owner, inscription, bonnes_reponses
    ):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses({3, 4}))
            services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses({3, 4}))

            services.accorder_des_essais(enrollment=inscription, nombre=1, actor=tenant_owner)
            resultat = services.soumettre_le_quiz(
                enrollment=inscription, reponses=bonnes_reponses()
            )

            assert resultat["passed"] is True
            assert resultat["attempts_allowed"] == 3

            with pytest.raises(services.QuizRefuse):
                services.soumettre_le_quiz(
                    enrollment=inscription, reponses=bonnes_reponses()
                )

        inscription.refresh_from_db()
        assert inscription.attempts_granted_by_id == tenant_owner.id
        assert inscription.attempts_granted_at is not None

    def test_un_cours_deja_reussi_ne_se_repasse_pas(self, tenant, inscription, bonnes_reponses):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses())

            with pytest.raises(services.QuizRefuse) as refus:
                services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses())
        assert "déjà réussi" in str(refus.value)


class TestAttestation:
    def test_est_delivree_a_la_reussite_avec_les_libelles_figes(
        self, tenant, inscription, bonnes_reponses, cours
    ):
        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            resultat = services.soumettre_le_quiz(
                enrollment=inscription, reponses=bonnes_reponses()
            )

        attestation = Certificate.all_objects.get(enrollment=inscription)
        assert resultat["certificate"]["serial"] == attestation.serial
        assert attestation.learner_name == "Camille Martin"
        assert attestation.company_name == tenant.name
        assert attestation.score == 100

        # Le cours est renommé APRÈS coup : l'attestation ne bouge pas.
        cours.title = "Un tout autre titre"
        cours.save(update_fields=["title"])
        attestation.refresh_from_db()
        assert attestation.course_title == "Cours de test"

    def test_le_document_dit_ce_qu_il_atteste_et_ce_qu_il_n_atteste_pas(
        self, tenant, inscription, bonnes_reponses
    ):
        from apps.training import certificates

        with services.contexte_du_client(tenant):
            _terminer_les_ecrans(inscription)
            services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses())

        attestation = Certificate.all_objects.get(enrollment=inscription)
        html = certificates.build_html(attestation)

        assert "Attestation de suivi" in html
        # Ces deux mots ont un sens juridique que ce document n'a pas.
        assert "certification" not in html.lower().replace("ni une certification", "")
        assert "habilitation" not in html.lower().replace("ni une habilitation", "")
        # Signée du nom du client, et le nom du fournisseur n'y figure pas.
        assert tenant.name in html
        assert "RSSI as a Service" not in html
        # La limite du lien nominatif est écrite sur le document lui-même.
        assert "n'a pas fait l'objet d'une vérification" in html


class TestLeLien:
    def test_resout_l_inscription_et_note_la_premiere_ouverture(self, inscription, jeton):
        trouvee = services.resoudre_session(jeton)
        assert trouvee.id == inscription.id
        assert trouvee.first_opened_at is not None

        # La deuxième ouverture ne réécrit pas la première.
        premiere = trouvee.first_opened_at
        assert services.resoudre_session(jeton).first_opened_at == premiere

    def test_un_lien_revoque_cesse_immediatement_de_fonctionner(
        self, tenant, tenant_owner, inscription, jeton
    ):
        with services.contexte_du_client(tenant):
            services.revoquer(enrollment=inscription, actor=tenant_owner)

        with pytest.raises(services.SessionIntrouvable):
            services.resoudre_session(jeton)

    def test_un_lien_expire_cesse_de_fonctionner_apres_la_marge(self, inscription, jeton):
        # La veille de l'échéance + marge : encore valable.
        inscription.due_date = date.today() - timedelta(days=6)
        inscription.save(update_fields=["due_date"])
        assert services.resoudre_session(jeton).id == inscription.id

        # Au-delà : plus valable.
        inscription.due_date = date.today() - timedelta(days=8)
        inscription.save(update_fields=["due_date"])
        with pytest.raises(services.SessionIntrouvable):
            services.resoudre_session(jeton)

    def test_le_lien_vaut_jusqu_a_la_fin_du_jour_d_echeance_plus_la_marge(self, inscription):
        attendu = inscription.due_date + timedelta(days=7)
        assert inscription.expires_at.date() == attendu
        # Fin de journée, et non minuit : « valable jusqu'au 12 » inclut le 12.
        assert inscription.expires_at.hour == 23

    def test_un_salarie_desactive_perd_ses_acces(self, inscription, jeton, salarie):
        salarie.is_active = False
        salarie.save(update_fields=["is_active"])
        with pytest.raises(services.SessionIntrouvable):
            services.resoudre_session(jeton)

    def test_renouveler_le_lien_tue_le_precedent(self, tenant, inscription, jeton):
        with services.contexte_du_client(tenant):
            nouveau = services.renouveler_le_lien(enrollment=inscription)

        assert services.resoudre_session(nouveau).id == inscription.id
        with pytest.raises(services.SessionIntrouvable):
            services.resoudre_session(jeton)

    def test_le_jeton_n_est_jamais_stocke_en_clair(self, inscription, jeton):
        inscription.refresh_from_db()
        assert jeton not in inscription.token_hash
        assert len(inscription.token_hash) == 64


class TestDemandeDAcces:
    def test_previent_les_administrateurs_sans_envoyer_de_lien(
        self, tenant, inscription, jeton, mailoutbox
    ):
        inscription.due_date = date.today() - timedelta(days=30)
        inscription.save(update_fields=["due_date"])

        assert services.demander_un_acces(jeton) is True

        assert len(mailoutbox) == 1
        message = mailoutbox[0]
        assert "Camille Martin" in message.subject
        assert "/formation/" not in message.body
        assert jeton not in message.body

    def test_ne_relance_pas_deux_fois_le_meme_jour(self, inscription, jeton, mailoutbox):
        assert services.demander_un_acces(jeton) is True
        assert services.demander_un_acces(jeton) is False
        assert len(mailoutbox) == 1

    def test_un_acces_retire_ne_relance_personne(
        self, tenant, tenant_owner, inscription, jeton, mailoutbox
    ):
        with services.contexte_du_client(tenant):
            services.revoquer(enrollment=inscription, actor=tenant_owner)

        with pytest.raises(services.SessionIntrouvable):
            services.demander_un_acces(jeton)
        assert mailoutbox == []


class TestInscription:
    def test_refuse_une_seconde_inscription_vivante_au_meme_cours(
        self, tenant, tenant_owner, salarie, cours, inscription
    ):
        with services.contexte_du_client(tenant):
            with pytest.raises(services.InscriptionRefusee) as refus:
                services.inscrire(
                    tenant=tenant,
                    learner=salarie,
                    course=cours,
                    due_date=date.today() + timedelta(days=30),
                    actor=tenant_owner,
                )
        assert "déjà inscrit" in str(refus.value)

    def test_accepte_une_reinscription_apres_revocation(
        self, tenant, tenant_owner, salarie, cours, inscription
    ):
        with services.contexte_du_client(tenant):
            services.revoquer(enrollment=inscription, actor=tenant_owner)
            seconde, _jeton = services.inscrire(
                tenant=tenant,
                learner=salarie,
                course=cours,
                due_date=date.today() + timedelta(days=30),
                actor=tenant_owner,
            )

        # L'ancienne inscription survit : c'est l'historique, pas un doublon.
        assert Enrollment.all_objects.filter(learner=salarie).count() == 2
        assert seconde.id != inscription.id

    def test_refuse_un_cours_non_proposé_a_cette_entreprise(
        self, tenant, tenant_owner, salarie, db
    ):
        from apps.training.models import Course, CourseVersion

        autre = Course.objects.create(slug="non-propose", title="Non proposé")
        CourseVersion.objects.create(course=autre, number=1, published_at=timezone.now())

        with services.contexte_du_client(tenant):
            with pytest.raises(services.InscriptionRefusee) as refus:
                services.inscrire(
                    tenant=tenant,
                    learner=salarie,
                    course=autre,
                    due_date=date.today() + timedelta(days=30),
                    actor=tenant_owner,
                )
        assert "pas proposé" in str(refus.value)
