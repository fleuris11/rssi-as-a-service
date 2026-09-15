"""Le jeu de démonstration montre un diagnostic terminé et un plan qui avance.

Relevé en production le 15/09/2026 : le client de démonstration avait un
diagnostic ouvert, sans une réponse. Le tableau de bord n'affichait donc que
l'accueil « Bienvenue », et les résultats, le plan d'action, les courbes et le
rapport de comité étaient vides devant un prospect.

Ce qui est tenu ici :

1. le diagnostic et le plan passent par les services, comme depuis l'écran ;
2. le tableau de bord a de quoi se dessiner : score de maturité, avancement du
   plan dans la période par défaut, du fait, de l'en cours, de l'en retard ;
3. rejouer ne refait JAMAIS un diagnostic — le produit ajouterait un second
   jeu d'actions au plan consolidé, et la démonstration le montrerait ;
4. aucune dépendance à l'IA : seuls des documents composés sont produits.
"""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.actions import services as actions_services
from apps.actions.models import ActionItem
from apps.ai_assistant.models import AIUsageLog, GeneratedDocument
from apps.assessments import services as assessments_services
from apps.assessments.models import Assessment
from apps.tenants.models import Membership, Tenant
from apps.threat_intelligence.management.commands.seed_demo_tenant import (
    ACTIONS_TERMINEES_IL_Y_A,
    ANSSI_SLUG,
    DEMO_DOCUMENTS,
    DEMO_TENANT_SLUG,
    DIAGNOSTIC_IL_Y_A_JOURS,
    demo_answer,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _preparer(settings):
    settings.DEBUG = True
    if assessments_services.get_referential(slug=ANSSI_SLUG) is None:
        call_command("load_anssi_referential")


def _demo():
    return Tenant.objects.get(slug=DEMO_TENANT_SLUG)


def _trimestre():
    fin = timezone.now()
    return fin - timedelta(days=90), fin


class TestUnDiagnosticTermine:
    def test_le_diagnostic_est_termine_et_date_dans_le_trimestre(self):
        call_command("seed_demo_tenant")

        termines = Assessment.all_objects.filter(tenant=_demo(), status=Assessment.Status.COMPLETED)
        assert termines.count() == 1
        evaluation = termines.get()
        assert evaluation.score_global is not None
        il_y_a = timezone.now() - evaluation.completed_at
        assert il_y_a.days == DIAGNOSTIC_IL_Y_A_JOURS

    def test_le_plan_reprend_exactement_les_ecarts(self):
        call_command("seed_demo_tenant")

        evaluation = assessments_services.get_latest_completed_assessment(_demo())
        ecarts = [
            mesure
            for mesure in assessments_services.get_assessment_measures(evaluation)
            if demo_answer(mesure.code) in ("no", "partial")
        ]
        assert ecarts, "un plan vide ne montrerait rien"
        assert ActionItem.all_objects.filter(tenant=_demo()).count() == len(ecarts)

    def test_le_diagnostic_ouvert_et_vide_est_repris_plutot_que_double(self):
        """L'état relevé en production : un diagnostic commencé, sans réponse."""
        call_command("seed_demo_tenant")
        tenant = _demo()
        Assessment.all_objects.filter(tenant=tenant).delete()
        administratrice = Membership.all_objects.get(tenant=tenant, role=Membership.Role.ADMIN).user
        ouvert = assessments_services.start_or_resume_assessment(
            tenant=tenant,
            user=administratrice,
            referential=assessments_services.get_referential(slug=ANSSI_SLUG),
        )

        call_command("seed_demo_tenant")

        assert Assessment.all_objects.filter(tenant=tenant).count() == 1
        assert Assessment.all_objects.get(pk=ouvert.pk).status == Assessment.Status.COMPLETED


class TestUnPlanQuiAvance:
    def test_du_fait_de_l_en_cours_et_de_l_en_retard(self):
        call_command("seed_demo_tenant")
        debut, fin = _trimestre()

        indicateurs = actions_services.action_plan_indicators(_demo(), start=debut, end=fin)

        assert indicateurs["done"] == len(ACTIONS_TERMINEES_IL_Y_A)
        assert indicateurs["in_progress"] >= 1
        assert indicateurs["overdue"] >= 1
        assert indicateurs["completed_in_period"] == len(ACTIONS_TERMINEES_IL_Y_A)

    def test_la_courbe_d_avancement_monte_sur_la_periode(self):
        call_command("seed_demo_tenant")
        debut, fin = _trimestre()

        serie = actions_services.action_plan_series(_demo(), start=debut, end=fin)
        taux = [point["completion_rate"] for point in serie if point["completion_rate"] is not None]

        assert taux, "aucun point : la courbe resterait vide"
        assert taux[-1] > taux[0]

    def test_le_score_de_maturite_est_mesure(self):
        call_command("seed_demo_tenant")
        debut, fin = _trimestre()

        maturite = assessments_services.maturity_indicators(_demo(), start=debut, end=fin)

        assert maturite["score"] is not None
        assert len(maturite["history"]) == 1

    def test_des_actions_sont_assignees_aux_membres(self):
        call_command("seed_demo_tenant")

        assert ActionItem.all_objects.filter(tenant=_demo(), assignee__isnull=False).exists()


class TestDocumentsComposes:
    def test_trois_documents_composes_dont_un_valide(self):
        call_command("seed_demo_tenant")

        documents = GeneratedDocument.all_objects.filter(tenant=_demo())
        assert {d.type for d in documents} == {type_document for type_document, _ in DEMO_DOCUMENTS}
        assert all(d.source == GeneratedDocument.Source.COMPOSED for d in documents)
        assert documents.filter(status=GeneratedDocument.Status.VALIDATED).count() == 1

    def test_aucun_appel_a_l_ia(self):
        call_command("seed_demo_tenant")

        assert not AIUsageLog.all_objects.filter(tenant=_demo()).exists()


class TestRejouer:
    def test_rejouer_ne_refait_ni_diagnostic_ni_plan_ni_documents(self):
        call_command("seed_demo_tenant")
        tenant = _demo()
        avant = (
            Assessment.all_objects.filter(tenant=tenant).count(),
            ActionItem.all_objects.filter(tenant=tenant).count(),
            GeneratedDocument.all_objects.filter(tenant=tenant).count(),
        )

        call_command("seed_demo_tenant")

        assert (
            Assessment.all_objects.filter(tenant=tenant).count(),
            ActionItem.all_objects.filter(tenant=tenant).count(),
            GeneratedDocument.all_objects.filter(tenant=tenant).count(),
        ) == avant

    def test_la_remise_a_zero_rend_le_plan_dans_son_etat_initial(self):
        """Une démonstration fait avancer une action : la suivante doit
        repartir du même état."""
        call_command("seed_demo_tenant")
        tenant = _demo()
        a_faire = ActionItem.all_objects.filter(
            tenant=tenant, status=ActionItem.Status.TODO
        ).first()
        actions_services.update_status(a_faire, ActionItem.Status.DONE)

        call_command("seed_demo_tenant", reset=True)

        assert ActionItem.all_objects.filter(
            tenant=tenant, status=ActionItem.Status.DONE
        ).count() == len(ACTIONS_TERMINEES_IL_Y_A)
        assert Assessment.all_objects.filter(tenant=tenant).count() == 1
