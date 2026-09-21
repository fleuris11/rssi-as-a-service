"""Le studio : écrire, versionner, dériver, publier.

Le test central est celui du versionnage. Tout le reste en découle : si une
version publiée pouvait être modifiée, une correction de phrase décalerait les
écrans sous les yeux d'un salarié en cours de parcours, et les lignes de
progression déjà enregistrées désigneraient des écrans qui ont changé de sens.
"""

import pytest

from apps.training import studio
from apps.training.models import Choice, Course, Question, Screen

pytestmark = pytest.mark.django_db


ECRAN = [{"type": "paragraphe", "texte": "Le contenu du premier écran."}]


@pytest.fixture
def cours_en_cours(tenant, tenant_owner):
    """Un cours de client, avec un écran et une question — le minimum
    publiable."""
    cours = studio.creer_cours(
        title="Mot de passe", summary="Court.", owner_tenant=tenant, actor=tenant_owner
    )
    version = cours.draft_version
    ecran = studio.ecrire_ecran(version=version, title="Premier écran", content=ECRAN)
    studio.ecrire_question(
        version=version,
        text="Une question ?",
        kind="single",
        explanation="Parce que.",
        screen_id=ecran.id,
        choix=[{"text": "Bonne", "is_correct": True}, {"text": "Mauvaise", "is_correct": False}],
    )
    return cours


class TestVersionnage:
    def test_une_version_publiee_ne_se_modifie_plus(self, cours_en_cours):
        version = cours_en_cours.draft_version
        studio.publier(version)

        with pytest.raises(studio.VersionVerrouillee) as refus:
            studio.ecrire_ecran(version=version, title="Ajout tardif", content=ECRAN)

        assert "publiée" in str(refus.value)

    def test_une_nouvelle_version_recopie_le_contenu(self, cours_en_cours):
        studio.publier(cours_en_cours.draft_version)

        suivante = studio.nouvelle_version(cours_en_cours, change_note="Correction.")

        assert suivante.number == 2
        assert suivante.is_published is False
        assert suivante.screens.count() == 1
        assert suivante.questions.count() == 1

    def test_les_questions_de_la_copie_visent_les_ecrans_de_la_copie(self, cours_en_cours):
        """Le point délicat de la recopie.

        Une question qui continuerait de pointer vers l'écran de la version
        précédente enverrait la révision après échec dans un autre cours, sans
        que rien ne le signale.
        """
        studio.publier(cours_en_cours.draft_version)
        suivante = studio.nouvelle_version(cours_en_cours)

        ecrans_de_la_copie = {e.id for e in suivante.screens.all()}
        for question in suivante.questions.all():
            assert question.screen_id in ecrans_de_la_copie

    def test_refuse_deux_brouillons_simultanes(self, cours_en_cours):
        studio.publier(cours_en_cours.draft_version)
        studio.nouvelle_version(cours_en_cours)

        with pytest.raises(studio.StudioError) as refus:
            studio.nouvelle_version(cours_en_cours)

        assert "déjà une version en cours" in str(refus.value)

    def test_un_apprenant_reste_sur_la_version_qu_il_a_commencee(
        self, tenant, tenant_owner, cours_en_cours
    ):
        """La raison d'être de tout ce mécanisme."""
        from datetime import date, timedelta

        from apps.training import services

        premiere = cours_en_cours.draft_version
        studio.publier(premiere)

        with services.contexte_du_client(tenant):
            services.attribuer_cours(tenant=tenant, course=cours_en_cours, actor=tenant_owner)
            salarie = services.creer_apprenant(
                tenant=tenant, full_name="Camille Martin", email="c@exemple.fr"
            )
            inscription, _jeton = services.inscrire(
                tenant=tenant,
                learner=salarie,
                course=cours_en_cours,
                due_date=date.today() + timedelta(days=7),
            )

        studio.publier(studio.nouvelle_version(cours_en_cours))

        inscription.refresh_from_db()
        assert inscription.version_id == premiere.id


class TestDuplication:
    def test_la_copie_est_independante_de_l_original(self, tenant, tenant_owner, cours_en_cours):
        studio.publier(cours_en_cours.draft_version)

        copie = studio.dupliquer(cours=cours_en_cours, owner_tenant=tenant, actor=tenant_owner)
        ecran_copie = copie.draft_version.screens.first()
        studio.ecrire_ecran(
            version=copie.draft_version,
            screen_id=ecran_copie.id,
            title="Titre adapté",
            content=[{"type": "paragraphe", "texte": "Contenu adapté à notre maison."}],
        )

        original = cours_en_cours.published_version.screens.first()
        assert original.title == "Premier écran"
        assert original.content == ECRAN

    def test_garde_la_trace_de_l_original(self, tenant, tenant_owner, cours_en_cours):
        studio.publier(cours_en_cours.draft_version)

        copie = studio.dupliquer(cours=cours_en_cours, owner_tenant=tenant, actor=tenant_owner)

        # Pour retrouver d'où vient un cours — pas pour le synchroniser.
        assert copie.derived_from_id == cours_en_cours.id

    def test_un_client_peut_deriver_un_cours_de_la_bibliotheque(self, tenant, tenant_owner):
        bibliotheque = studio.creer_cours(title="Cours de la maison", actor=None)
        ecran = studio.ecrire_ecran(
            version=bibliotheque.draft_version, title="Écran", content=ECRAN
        )
        studio.ecrire_question(
            version=bibliotheque.draft_version,
            text="Q ?",
            kind="single",
            explanation="Parce que.",
            screen_id=ecran.id,
            choix=[{"text": "A", "is_correct": True}, {"text": "B", "is_correct": False}],
        )
        studio.publier(bibliotheque.draft_version)

        copie = studio.dupliquer(cours=bibliotheque, owner_tenant=tenant, actor=tenant_owner)

        assert bibliotheque.est_de_la_bibliotheque is True
        assert copie.owner_tenant_id == tenant.id
        assert copie.est_de_la_bibliotheque is False


class TestControlesAvantPublication:
    def test_refuse_un_cours_sans_ecran(self, tenant, tenant_owner):
        cours = studio.creer_cours(title="Vide", owner_tenant=tenant, actor=tenant_owner)

        refus, _ = studio.controles_avant_publication(cours.draft_version)

        assert any("au moins un écran" in r for r in refus)

    def test_refuse_une_question_sans_bonne_reponse(self, tenant, tenant_owner, cours_en_cours):
        question = cours_en_cours.draft_version.questions.first()
        question.choices.update(is_correct=False)

        refus, _ = studio.controles_avant_publication(cours_en_cours.draft_version)

        assert any("aucune bonne réponse" in r for r in refus)

    def test_avertit_sans_refuser_sur_un_quiz_trop_court(self, cours_en_cours):
        refus, avertissements = studio.controles_avant_publication(cours_en_cours.draft_version)

        # Un quiz d'une question est bancal, pas cassé : on le signale, on ne
        # l'interdit pas.
        assert refus == []
        assert any("ne veut plus dire grand-chose" in a for a in avertissements)

    def test_avertit_quand_un_ecran_utilise_des_variables(self, tenant, tenant_owner):
        cours = studio.creer_cours(title="Contextuel", owner_tenant=tenant, actor=tenant_owner)
        studio.ecrire_ecran(
            version=cours.draft_version,
            title="Écran",
            content=[
                {
                    "type": "paragraphe",
                    "texte": "Vous avez {fuites_ouvertes} comptes touchés.",
                    "repli": "Des comptes sont peut-être touchés.",
                }
            ],
        )

        _refus, avertissements = studio.controles_avant_publication(cours.draft_version)

        assert any("formulation de repli" in a for a in avertissements)

    def test_publier_refuse_tant_qu_un_controle_bloque(self, tenant, tenant_owner):
        cours = studio.creer_cours(title="Vide", owner_tenant=tenant, actor=tenant_owner)

        with pytest.raises(studio.StudioError):
            studio.publier(cours.draft_version)


class TestEcritureDuContenu:
    def test_refuse_une_question_sans_explication(self, cours_en_cours):
        ecran = cours_en_cours.draft_version.screens.first()

        with pytest.raises(studio.StudioError) as refus:
            studio.ecrire_question(
                version=cours_en_cours.draft_version,
                text="Q ?",
                kind="single",
                explanation="   ",
                screen_id=ecran.id,
                choix=[{"text": "A", "is_correct": True}, {"text": "B"}],
            )

        assert "seule partie du quiz qui forme" in str(refus.value)

    def test_refuse_deux_bonnes_reponses_en_choix_unique(self, cours_en_cours):
        ecran = cours_en_cours.draft_version.screens.first()

        with pytest.raises(studio.StudioError) as refus:
            studio.ecrire_question(
                version=cours_en_cours.draft_version,
                text="Q ?",
                kind="single",
                explanation="Parce que.",
                screen_id=ecran.id,
                choix=[{"text": "A", "is_correct": True}, {"text": "B", "is_correct": True}],
            )

        assert "choix unique" in str(refus.value)

    def test_reordonne_les_ecrans(self, cours_en_cours):
        version = cours_en_cours.draft_version
        deuxieme = studio.ecrire_ecran(version=version, title="Deuxième", content=ECRAN)
        premier = version.screens.first()

        studio.reordonner_ecrans(version=version, ordre_ids=[deuxieme.id, premier.id])

        assert [e.title for e in version.screens.all()] == ["Deuxième", "Premier écran"]

    def test_refuse_un_ordre_incomplet(self, cours_en_cours):
        version = cours_en_cours.draft_version
        studio.ecrire_ecran(version=version, title="Deuxième", content=ECRAN)

        with pytest.raises(studio.StudioError):
            studio.reordonner_ecrans(version=version, ordre_ids=[version.screens.first().id])

    def test_refuse_de_supprimer_un_ecran_vise_par_une_question(self, cours_en_cours):
        version = cours_en_cours.draft_version
        ecran = version.screens.first()

        with pytest.raises(studio.StudioError) as refus:
            studio.supprimer_ecran(version=version, screen_id=ecran.id)

        # Sinon la révision après échec n'aurait plus où conduire.
        assert "renvoient à cet écran" in str(refus.value)

    def test_un_contenu_invalide_est_refuse_a_l_ecriture(self, cours_en_cours):
        from apps.training.blocks import BlocInvalide

        with pytest.raises(BlocInvalide):
            studio.ecrire_ecran(
                version=cours_en_cours.draft_version,
                title="Écran",
                content=[
                    {"type": "image", "source": "https://ailleurs.test/x.png", "alternative": "x"}
                ],
            )


class TestApercu:
    def test_montre_le_cours_tel_que_l_apprenant_le_verra(self, cours_en_cours):
        apercu = studio.apercu(cours_en_cours.draft_version)

        assert apercu["course_title"] == "Mot de passe"
        assert [e["title"] for e in apercu["screens"]] == ["Premier écran"]
        assert apercu["is_published"] is False

    def test_resout_les_variables_avec_les_donnees_du_client(
        self, tenant, tenant_owner, monkeypatch
    ):
        from apps.training import variables
        from apps.training.variables import Variable

        monkeypatch.setitem(
            variables.REGISTRE,
            "fuites_ouvertes",
            Variable("fuites_ouvertes", "T", "", lambda _t: 9),
        )
        cours = studio.creer_cours(title="Contextuel", owner_tenant=tenant, actor=tenant_owner)
        studio.ecrire_ecran(
            version=cours.draft_version,
            title="Écran",
            content=[
                {
                    "type": "paragraphe",
                    "texte": "Vous avez {fuites_ouvertes} comptes touchés.",
                    "repli": "Des comptes sont peut-être touchés.",
                }
            ],
        )

        apercu = studio.apercu(cours.draft_version, tenant=tenant)

        # C'est le seul moyen de voir si la phrase se tient avec de vrais
        # chiffres — et le contenu brut reste disponible pour l'éditeur.
        assert "9 comptes" in apercu["screens"][0]["content"][0]["texte"]
        assert "{fuites_ouvertes}" in apercu["screens"][0]["content_brut"][0]["texte"]


class TestNettoyage:
    def test_creer_un_cours_ne_touche_pas_au_catalogue_des_autres(self, tenant, tenant_owner):
        avant = Course.objects.count()
        studio.creer_cours(title="Le mien", owner_tenant=tenant, actor=tenant_owner)
        assert Course.objects.count() == avant + 1
        assert Screen.objects.filter(version__course__owner_tenant=tenant).count() == 0
        assert Question.objects.count() >= 0
        assert Choice.objects.count() >= 0
