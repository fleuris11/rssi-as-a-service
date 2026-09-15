"""Lot C — les courbes du tableau de bord d'un RSSI.

Quatre questions, une courbe chacune, et rien d'autre :

- **le score d'exposition baisse-t-il ?**
- **est-ce qu'on traite les fuites, ou est-ce qu'on les écarte ?**
- **la maturité progresse-t-elle ?** (l'historique existait déjà)
- **le plan d'action avance-t-il ?**

Mêmes exigences que les indicateurs de la V2-3 : exactitude sur des jeux
connus, étanchéité entre clients, cohérence avec les chiffres affichés à côté —
une courbe dont le dernier point contredit la carte voisine détruit la
confiance dans les deux. Et un coût qui ne dépend pas du volume.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.actions import services as actions_services
from apps.actions.models import ActionItem
from apps.reporting import exports, periods, services
from apps.threat_intelligence import services as ti_services
from apps.threat_intelligence.models import BreachFinding

from .test_indicateurs import _fuite

pytestmark = pytest.mark.django_db


@pytest.fixture
def periode():
    return periods.resolve(periods.PRESET_30D)


@pytest.fixture
def voisin(user_factory, tenant_factory):
    from apps.monitoring import services as monitoring_services
    from apps.monitoring.models import Asset

    proprietaire = user_factory(email="voisin-courbes@example.com")
    tenant = tenant_factory(name="Voisin courbes", owner=proprietaire)
    asset = monitoring_services.create_asset(
        tenant=tenant,
        user=proprietaire,
        type=Asset.Type.WEBSITE,
        value="https://voisin-courbes.example",
        ownership_confirmed=True,
    )
    return tenant, asset, proprietaire


class TestOuvertesContreTraitees:
    def test_le_cumul_ne_compte_que_les_fuites_traitees(self, tenant, website_asset, periode):
        """Ignorer fait baisser le stock, mais ce n'est pas traiter."""
        _fuite(tenant, website_asset, severity="high", detected_il_y_a=20, cle="a")
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=20,
            status=BreachFinding.Status.TREATED,
            traitee_il_y_a=10,
            cle="b",
        )
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=20,
            status=BreachFinding.Status.IGNORED,
            traitee_il_y_a=5,
            cle="c",
        )

        serie = ti_services.open_findings_series(tenant, start=periode.start, end=periode.end)

        assert serie[-1]["open"] == 1
        assert serie[-1]["treated"] == 1
        # Avant le traitement, rien de traité sur la période.
        jour_avant = timezone.localdate() - timedelta(days=15)
        assert next(p for p in serie if p["date"] == jour_avant)["treated"] == 0

    def test_une_fuite_traitee_avant_la_periode_n_entre_pas_dans_le_cumul(
        self, tenant, website_asset, periode
    ):
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=90,
            status=BreachFinding.Status.TREATED,
            traitee_il_y_a=60,
            cle="ancienne",
        )

        serie = ti_services.open_findings_series(tenant, start=periode.start, end=periode.end)

        assert {p["treated"] for p in serie} == {0}

    def test_le_cumul_du_dernier_jour_egale_les_traitees_de_la_periode(
        self, tenant, website_asset, periode
    ):
        """Cohérence avec la ligne « Traitées » affichée à côté de la courbe."""
        for i in range(3):
            _fuite(
                tenant,
                website_asset,
                severity="attention",
                detected_il_y_a=25,
                status=BreachFinding.Status.TREATED,
                traitee_il_y_a=2 + i,
                cle=f"t{i}",
            )

        indicateurs = ti_services.breach_indicators(tenant, start=periode.start, end=periode.end)

        assert indicateurs["series"][-1]["treated"] == indicateurs["treated_in_period"] == 3


class TestScoreDExpositionDansLeTemps:
    def test_chaque_point_egale_le_score_calcule_a_cet_instant(
        self, tenant, website_asset, periode
    ):
        """La reconstruction en mémoire ne doit RIEN changer au chiffre : une
        optimisation qui modifie le score n'est pas une optimisation."""
        _fuite(tenant, website_asset, severity="critical", detected_il_y_a=28, cle="1")
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=25,
            status=BreachFinding.Status.TREATED,
            traitee_il_y_a=12,
            cle="2",
        )
        _fuite(tenant, website_asset, severity="attention", detected_il_y_a=6, cle="3")
        _fuite(
            tenant,
            website_asset,
            severity="high",
            detected_il_y_a=20,
            status=BreachFinding.Status.IGNORED,
            traitee_il_y_a=3,
            cle="4",
        )

        serie = ti_services.exposure_score_series(tenant, start=periode.start, end=periode.end)

        pas = (periode.end - periode.start) / (ti_services.EXPOSURE_SCORE_POINTS - 1)
        instants = [periode.start + pas * r for r in range(ti_services.EXPOSURE_SCORE_POINTS - 1)]
        instants.append(periode.end)
        attendus = [ti_services.exposure_score_at(tenant, m) for m in instants]
        assert [p["score"] for p in serie] == attendus
        # Le jeu fait réellement bouger le score : sinon ce test passerait
        # aussi sur une courbe plate constante.
        assert len(set(attendus)) > 1

    def test_les_extremites_egalent_les_chiffres_de_la_carte(self, tenant, website_asset, periode):
        _fuite(tenant, website_asset, severity="critical", detected_il_y_a=40, cle="x")
        _fuite(tenant, website_asset, severity="high", detected_il_y_a=3, cle="y")

        tableau = services.build_dashboard(tenant, periode)
        serie = tableau["exposure"]["score_series"]

        assert serie[0]["score"] == tableau["exposure"]["exposure_score_at_period_start"]
        assert serie[-1]["score"] == tableau["exposure"]["exposure_score"]

    def test_le_score_du_voisin_ne_pese_pas(self, tenant, website_asset, voisin, periode):
        tenant_voisin, asset_voisin, _proprietaire = voisin
        _fuite(tenant_voisin, asset_voisin, severity="critical", detected_il_y_a=10, cle="v")

        serie = ti_services.exposure_score_series(tenant, start=periode.start, end=periode.end)

        assert {p["score"] for p in serie} == {0}


class TestAvancementDuPlan:
    @pytest.fixture
    def plan(self, tenant, tenant_owner, referential):
        from apps.assessments import services as assessments_services

        evaluation = assessments_services.start_or_resume_assessment(
            tenant=tenant, user=tenant_owner, referential=referential
        )
        for mesure in assessments_services.get_assessment_measures(evaluation):
            assessments_services.submit_answer(assessment=evaluation, measure=mesure, value="no")
        assessments_services.complete_assessment(evaluation)
        actions_services.generate_action_plan(evaluation)
        return list(ActionItem.all_objects.filter(tenant=tenant).order_by("id"))

    def _dater(self, action, *, creee_il_y_a, terminee_il_y_a=None):
        maintenant = timezone.now()
        ActionItem.all_objects.filter(pk=action.pk).update(
            created_at=maintenant - timedelta(days=creee_il_y_a),
            status=ActionItem.Status.DONE
            if terminee_il_y_a is not None
            else ActionItem.Status.TODO,
            completed_at=(
                maintenant - timedelta(days=terminee_il_y_a)
                if terminee_il_y_a is not None
                else None
            ),
        )

    def test_le_dernier_point_egale_les_chiffres_du_plan(self, tenant, plan, periode):
        for action in plan:
            self._dater(action, creee_il_y_a=40)
        self._dater(plan[0], creee_il_y_a=40, terminee_il_y_a=20)
        self._dater(plan[1], creee_il_y_a=40, terminee_il_y_a=2)

        indicateurs = actions_services.action_plan_indicators(
            tenant, start=periode.start, end=periode.end
        )
        serie = actions_services.action_plan_series(tenant, start=periode.start, end=periode.end)

        assert serie[-1]["done"] == indicateurs["done"] == 2
        assert serie[-1]["total"] == indicateurs["total"]
        assert serie[-1]["completion_rate"] == indicateurs["completion_rate"]

    def test_une_action_terminee_avant_la_periode_compte_des_le_premier_jour(
        self, tenant, plan, periode
    ):
        """Le trou qu'une neutralisation a montré : aucun test ne terminait
        d'action AVANT la période. Oublier l'état initial laissait alors tous
        les tests verts, et la courbe démarrait à zéro chez un client dont la
        moitié du plan était faite depuis des mois."""
        for action in plan:
            self._dater(action, creee_il_y_a=60)
        self._dater(plan[0], creee_il_y_a=60, terminee_il_y_a=45)

        serie = actions_services.action_plan_series(tenant, start=periode.start, end=periode.end)

        assert serie[0]["done"] == 1
        assert serie[0]["completion_rate"] == round(100 / len(plan), 1)

    def test_la_courbe_monte_le_jour_ou_une_action_est_terminee(self, tenant, plan, periode):
        for action in plan:
            self._dater(action, creee_il_y_a=40)
        self._dater(plan[0], creee_il_y_a=40, terminee_il_y_a=10)

        serie = actions_services.action_plan_series(tenant, start=periode.start, end=periode.end)
        par_jour = {p["date"]: p["done"] for p in serie}
        aujourd_hui = timezone.localdate()

        assert par_jour[aujourd_hui - timedelta(days=11)] == 0
        assert par_jour[aujourd_hui - timedelta(days=10)] == 1

    def test_une_action_ajoutee_en_cours_de_periode_compte_a_partir_de_son_ajout(
        self, tenant, plan, periode
    ):
        for action in plan:
            self._dater(action, creee_il_y_a=40)
        self._dater(plan[0], creee_il_y_a=5)

        serie = actions_services.action_plan_series(tenant, start=periode.start, end=periode.end)
        aujourd_hui = timezone.localdate()
        par_jour = {p["date"]: p["total"] for p in serie}

        assert par_jour[aujourd_hui - timedelta(days=6)] == len(plan) - 1
        assert par_jour[aujourd_hui] == len(plan)

    def test_sans_plan_la_courbe_dit_non_mesure_et_pas_zero_pour_cent(self, tenant, periode):
        serie = actions_services.action_plan_series(tenant, start=periode.start, end=periode.end)

        assert len(serie) == periode.days
        assert {p["completion_rate"] for p in serie} == {None}

    def test_le_plan_du_voisin_ne_compte_pas(self, tenant, plan, voisin, periode, referential):
        from apps.assessments import services as assessments_services

        tenant_voisin, _asset, proprietaire = voisin
        evaluation = assessments_services.start_or_resume_assessment(
            tenant=tenant_voisin, user=proprietaire, referential=referential
        )
        for mesure in assessments_services.get_assessment_measures(evaluation):
            assessments_services.submit_answer(assessment=evaluation, measure=mesure, value="no")
        assessments_services.complete_assessment(evaluation)
        actions_services.generate_action_plan(evaluation)

        serie = actions_services.action_plan_series(tenant, start=periode.start, end=periode.end)

        assert serie[-1]["total"] == len(plan)


class TestCout:
    def test_les_courbes_coutent_un_nombre_fixe_de_requetes(self, tenant, website_asset, periode):
        """Budget par courbe, indépendant du nombre de jours et du volume."""
        for i in range(30):
            _fuite(tenant, website_asset, severity="high", detected_il_y_a=i % 28, cle=f"c{i}")

        with CaptureQueriesContext(connection) as score:
            ti_services.exposure_score_series(tenant, start=periode.start, end=periode.end)
        with CaptureQueriesContext(connection) as plan:
            actions_services.action_plan_series(tenant, start=periode.start, end=periode.end)
        with CaptureQueriesContext(connection) as ouvertes:
            ti_services.open_findings_series(tenant, start=periode.start, end=periode.end)

        # Une requête par point de la courbe, et non par jour ni par fuite :
        # un nombre FIXE. Choisi sur mesure (test_performance_courbes.py) :
        # treize requêtes coûtent moins cher qu'une seule reconstruite en
        # mémoire sur 28 450 fuites.
        assert len(score) == ti_services.EXPOSURE_SCORE_POINTS
        assert len(plan) <= 4
        assert len(ouvertes) <= 4


class TestExportTableur:
    def test_le_tableur_reprend_les_quatre_courbes(self, tenant, website_asset, periode):
        _fuite(tenant, website_asset, severity="critical", detected_il_y_a=10, cle="e")

        lignes = exports.csv_rows(services.build_report(tenant, periode))
        titres = [ligne[0] for ligne in lignes if ligne]

        assert "— Compromissions ouvertes et traitées, jour par jour —" in titres
        assert "— Score d'exposition dans le temps —" in titres
        assert "— Avancement du plan d'action, jour par jour —" in titres
