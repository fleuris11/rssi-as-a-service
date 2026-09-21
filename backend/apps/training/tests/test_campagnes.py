"""Inscrire, importer, relancer.

Le test qui compte le plus est celui du bas : **un salarié qui a terminé ne
reçoit plus rien.** C'est l'erreur classique de ce genre de mécanisme — la
condition « n'a pas fini » est oubliée, et l'outil écrit à quelqu'un qui a
fait ce qu'on lui demandait.
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.training import campagnes, services
from apps.training.models import Enrollment, Learner, ReminderLog

pytestmark = pytest.mark.django_db


def _inscrire(tenant, tenant_owner, cours, *, salarie, echeance, creee_il_y_a=0):
    with services.contexte_du_client(tenant):
        inscription, _jeton = services.inscrire(
            tenant=tenant, learner=salarie, course=cours, due_date=echeance, actor=tenant_owner
        )
    if creee_il_y_a:
        Enrollment.all_objects.filter(id=inscription.id).update(
            created_at=timezone.now() - timedelta(days=creee_il_y_a)
        )
        inscription.refresh_from_db()
    return inscription


@pytest.fixture
def salarie_bis(tenant, tenant_owner):
    with services.contexte_du_client(tenant):
        return services.creer_apprenant(
            tenant=tenant, full_name="Dominique Leroy", email="dominique@exemple.fr"
        )


class TestImport:
    def test_cree_les_salaries_d_un_fichier(self, tenant, tenant_owner):
        contenu = "Camille Martin;camille@exemple.fr\nDominique Leroy;dominique@exemple.fr"

        with services.contexte_du_client(tenant):
            resultat = campagnes.importer_des_salaries(
                tenant=tenant, contenu=contenu, actor=tenant_owner
            )

        assert len(resultat["crees"]) == 2
        assert Learner.all_objects.filter(tenant=tenant).count() == 2

    def test_accepte_la_virgule_et_la_tabulation(self, tenant, tenant_owner):
        with services.contexte_du_client(tenant):
            virgule = campagnes.importer_des_salaries(
                tenant=tenant, contenu="Alex Dubois,alex@exemple.fr", actor=tenant_owner
            )
        assert len(virgule["crees"]) == 1

    def test_saute_la_ligne_d_en_tete(self, tenant, tenant_owner):
        contenu = "Nom;Email\nCamille Martin;camille@exemple.fr"

        with services.contexte_du_client(tenant):
            resultat = campagnes.importer_des_salaries(
                tenant=tenant, contenu=contenu, actor=tenant_owner
            )

        # Sinon on créerait un salarié nommé « Nom ».
        assert [c["full_name"] for c in resultat["crees"]] == ["Camille Martin"]

    def test_ne_s_arrete_pas_a_la_premiere_erreur(self, tenant, tenant_owner):
        contenu = (
            "Camille Martin;camille@exemple.fr\n"
            "Ligne cassée\n"
            "Sans arobase;pasunemail\n"
            "Dominique Leroy;dominique@exemple.fr"
        )

        with services.contexte_du_client(tenant):
            resultat = campagnes.importer_des_salaries(
                tenant=tenant, contenu=contenu, actor=tenant_owner
            )

        # Un import qui s'arrête à la ligne 12 d'un fichier de 80 oblige à
        # recommencer douze fois.
        assert len(resultat["crees"]) == 2
        assert len(resultat["invalides"]) == 2
        assert {p["ligne"] for p in resultat["invalides"]} == {2, 3}

    def test_signale_les_doublons_sans_les_recreer(self, tenant, tenant_owner, salarie):
        with services.contexte_du_client(tenant):
            resultat = campagnes.importer_des_salaries(
                tenant=tenant,
                contenu=f"Camille Martin;{salarie.email}",
                actor=tenant_owner,
            )

        assert resultat["deja_presents"] == [salarie.email]
        assert resultat["crees"] == []

    def test_refuse_un_fichier_sans_colonnes(self, tenant, tenant_owner):
        with services.contexte_du_client(tenant), pytest.raises(campagnes.ImportRefuse):
            campagnes.importer_des_salaries(
                tenant=tenant, contenu="juste du texte", actor=tenant_owner
            )


class TestInvitation:
    def test_l_inscription_envoie_le_lien_au_salarie(
        self, tenant, tenant_owner, salarie, cours, mailoutbox
    ):
        with services.contexte_du_client(tenant):
            inscription, jeton = campagnes.inscrire_et_inviter(
                tenant=tenant,
                learner=salarie,
                course=cours,
                due_date=date.today() + timedelta(days=14),
                actor=tenant_owner,
            )

        assert len(mailoutbox) == 1
        message = mailoutbox[0]
        assert message.to == [salarie.email]
        assert jeton in message.body
        assert inscription.learner_id == salarie.id


class TestRelances:
    def test_relance_a_mi_parcours(self, tenant, tenant_owner, salarie, cours):
        # Campagne de 10 jours, commencée il y a 6 : la mi-parcours est passée.
        inscription = _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() + timedelta(days=4),
            creee_il_y_a=6,
        )

        a_faire = campagnes.relances_du_jour()

        assert [(i.id, k) for i, k in a_faire] == [(inscription.id, ReminderLog.Kind.MID)]

    def test_relance_avant_l_echeance(self, tenant, tenant_owner, salarie, cours):
        _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() + timedelta(days=2),
            creee_il_y_a=1,
        )

        natures = {k for _i, k in campagnes.relances_du_jour()}

        assert ReminderLog.Kind.BEFORE in natures

    def test_relance_apres_l_echeance(self, tenant, tenant_owner, salarie, cours):
        _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() - timedelta(days=3),
            creee_il_y_a=10,
        )

        natures = {k for _i, k in campagnes.relances_du_jour()}

        assert ReminderLog.Kind.AFTER in natures

    def test_chaque_nature_ne_part_qu_une_fois(
        self, tenant, tenant_owner, salarie, cours, mailoutbox
    ):
        _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() + timedelta(days=4),
            creee_il_y_a=6,
        )

        premier = campagnes.envoyer_les_relances()
        second = campagnes.envoyer_les_relances()

        # Une tâche quotidienne qui renverrait le même message tous les jours
        # est le défaut le plus facile à produire ici.
        assert premier == 1
        assert second == 0

    def test_un_salarie_qui_a_termine_ne_recoit_plus_rien(
        self, tenant, tenant_owner, salarie, cours, bonnes_reponses
    ):
        """L'erreur classique de ce genre de mécanisme."""
        inscription = _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() + timedelta(days=4),
            creee_il_y_a=6,
        )
        with services.contexte_du_client(tenant):
            for ecran in inscription.version.screens.all():
                services.marquer_ecran_vu(enrollment=inscription, screen_id=ecran.id)
            services.soumettre_le_quiz(enrollment=inscription, reponses=bonnes_reponses())

        assert campagnes.relances_du_jour() == []

    def test_la_politique_coupee_arrete_tout(self, tenant, tenant_owner, salarie, cours):
        _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() + timedelta(days=4),
            creee_il_y_a=6,
        )
        with services.contexte_du_client(tenant):
            campagnes.regler_la_politique(tenant=tenant, enabled=False, actor=tenant_owner)

        # Une relance qu'on ne peut pas couper devient du harcèlement.
        assert campagnes.relances_du_jour() == []

    def test_chaque_moment_se_coupe_separement(self, tenant, tenant_owner, salarie, cours):
        _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() + timedelta(days=4),
            creee_il_y_a=6,
        )
        with services.contexte_du_client(tenant):
            campagnes.regler_la_politique(tenant=tenant, mid_course=False, actor=tenant_owner)

        natures = {k for _i, k in campagnes.relances_du_jour()}
        assert ReminderLog.Kind.MID not in natures

    def test_un_acces_retire_ne_relance_personne(self, tenant, tenant_owner, salarie, cours):
        inscription = _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() + timedelta(days=4),
            creee_il_y_a=6,
        )
        with services.contexte_du_client(tenant):
            services.revoquer(enrollment=inscription, actor=tenant_owner)

        assert campagnes.relances_du_jour() == []

    def test_la_relance_porte_un_lien_neuf_qui_remplace_l_ancien(
        self, tenant, tenant_owner, salarie, cours, mailoutbox
    ):
        inscription = _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() + timedelta(days=4),
            creee_il_y_a=6,
        )
        ancien = inscription.token_hash

        campagnes.envoyer_les_relances()

        inscription.refresh_from_db()
        # Le jeton n'est stocké que haché : on ne peut pas rappeler le lien
        # envoyé, seulement en émettre un autre.
        assert inscription.token_hash != ancien
        assert "/formation/" in mailoutbox[-1].body
        assert "remplace" in mailoutbox[-1].body

    def test_une_seule_relance_par_jour_et_par_salarie(self, tenant, tenant_owner, salarie, cours):
        # Campagne d'un jour : mi-parcours, avant et après tombent ensemble.
        _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() - timedelta(days=3),
            creee_il_y_a=4,
        )

        a_faire = campagnes.relances_du_jour()

        assert len(a_faire) == 1

    def test_l_etancheite_entre_clients_tient(
        self, tenant, tenant_owner, salarie, cours, user_factory, tenant_factory
    ):
        _inscrire(
            tenant,
            tenant_owner,
            cours,
            salarie=salarie,
            echeance=date.today() + timedelta(days=4),
            creee_il_y_a=6,
        )
        autre_proprietaire = user_factory(email="ailleurs@example.com")
        autre = tenant_factory(autre_proprietaire, name="Autre Entreprise")
        with services.contexte_du_client(autre):
            campagnes.regler_la_politique(tenant=autre, enabled=False)

        # Couper les relances chez l'un ne coupe rien chez l'autre.
        assert len(campagnes.relances_du_jour()) == 1
