"""Le volet formation du rapport de comité (F3, point 12).

Un seul sujet ici, et il est juridique : ce document circule, s'imprime et
s'archive. Il porte des chiffres collectifs, **jamais** le résultat d'un
salarié nommé.
"""

from datetime import date, timedelta

import pytest

from apps.reporting import periods, report
from apps.reporting import services as reporting
from apps.training import services

pytestmark = pytest.mark.django_db


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


def _rapport(tenant):
    return reporting.build_report(tenant, periods.resolve(periods.PRESET_QUARTER))


class TestVoletFormation:
    def test_le_rapport_porte_les_chiffres_de_formation(self, tenant, campagne):
        donnees = _rapport(tenant)

        assert donnees["training"]["learners_total"] == 1
        assert donnees["training"]["completed"] == 1
        assert donnees["training"]["participation_rate"] == 100

    def test_le_document_montre_la_sensibilisation(self, tenant, campagne):
        html = report.build_html(_rapport(tenant))

        assert "La sensibilisation des équipes" in html
        assert "Taux de participation" in html

    def test_le_document_ne_nomme_aucun_salarie(self, tenant, campagne):
        """La règle du lot, vérifiée sur le document lui-même."""
        html = report.build_html(_rapport(tenant))

        assert "Camille Martin" not in html
        assert "camille@exemple.fr" not in html
        assert "Le détail par salarié" in html

    def test_sans_formation_le_volet_disparait_au_lieu_d_afficher_des_zeros(self, tenant):
        html = report.build_html(_rapport(tenant))

        # Un comité n'a pas besoin de lire « 0 salarié formé, 0 % de
        # participation » : l'absence de dispositif se dit ailleurs.
        assert "La sensibilisation des équipes" not in html
