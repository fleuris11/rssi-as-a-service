"""Unit tests for the scoring engine (apps.assessments.services).

Fixture measures (see apps/conftest.py::referential):
  M1 (domaine-a, standard, weight 1.0)
  M2 (domaine-a, renforcé, weight 0.5)
  M3 (domaine-b, standard, weight 1.0)
  M4 (domaine-b, renforcé, weight 0.5)
"""

import pytest

from apps.assessments import services
from apps.assessments.models import Answer, Measure

pytestmark = pytest.mark.django_db


@pytest.fixture
def measures(referential):
    return list(Measure.objects.filter(domain__referential=referential).order_by("number"))


class TestScoreFromValuesEdgeCases:
    def test_empty_assessment_returns_none(self, measures):
        """Cas limite : évaluation vide (aucune réponse) — pas de score
        trompeur à 0, mais une absence de score."""
        assert services.score_from_values({}, measures) is None

    def test_all_not_applicable_returns_none(self, measures):
        """Cas limite : toutes les mesures marquées "non applicable" — les
        N/A sont exclus du dénominateur, donc rien à scorer."""
        values = {m.id: Answer.Value.NOT_APPLICABLE for m in measures}
        assert services.score_from_values(values, measures) is None

    def test_all_yes_scores_100(self, measures):
        values = {m.id: Answer.Value.YES for m in measures}
        assert services.score_from_values(values, measures) == 100.0

    def test_all_no_scores_0(self, measures):
        values = {m.id: Answer.Value.NO for m in measures}
        assert services.score_from_values(values, measures) == 0.0

    def test_no_measures_returns_none(self):
        """Cas limite : référentiel/domaine sans aucune mesure."""
        assert services.score_from_values({"anything": Answer.Value.YES}, []) is None


class TestWeightedScoring:
    def test_renforce_measures_count_half_of_standard(self, measures):
        """M1 (standard) = oui, M2 (renforcé) = non : si le poids était
        identique le score serait 50 ; le poids réduit du "renforcé" doit
        le faire remonter au-dessus de 50."""
        m1, m2 = measures[0], measures[1]
        values = {m1.id: Answer.Value.YES, m2.id: Answer.Value.NO}

        score = services.score_from_values(values, [m1, m2])

        # weighted_sum = 1.0*1.0 + 0*0.5 = 1.0 ; weight_total = 1.0+0.5 = 1.5
        assert score == pytest.approx(round(100 * 1.0 / 1.5, 1))
        assert score > 50.0

    def test_na_excluded_from_denominator(self, measures):
        """Cas limite : le N/A ne doit ni compter comme un échec (0) ni
        être moyenné comme une valeur — il doit disparaître du calcul."""
        m1, m2 = measures[0], measures[1]
        score_with_na = services.score_from_values(
            {m1.id: Answer.Value.YES, m2.id: Answer.Value.NOT_APPLICABLE}, [m1, m2]
        )
        score_without_m2 = services.score_from_values({m1.id: Answer.Value.YES}, [m1])

        assert score_with_na == score_without_m2 == 100.0

    def test_partial_counts_as_half_credit(self, measures):
        m1 = measures[0]
        assert services.score_from_values({m1.id: Answer.Value.PARTIAL}, [m1]) == 50.0

    def test_unanswered_measure_excluded_like_na(self, measures):
        m1, m2 = measures[0], measures[1]
        score_partial = services.score_from_values({m1.id: Answer.Value.YES}, [m1, m2])
        score_explicit_na = services.score_from_values(
            {m1.id: Answer.Value.YES, m2.id: Answer.Value.NOT_APPLICABLE}, [m1, m2]
        )
        assert score_partial == score_explicit_na


class TestComputeScoresPerDomain:
    def test_global_and_per_domain_scores(self, assessment, measures):
        m1, m2, m3, m4 = measures  # M1/M2 in domaine-a, M3/M4 in domaine-b
        services.submit_answer(assessment=assessment, measure=m1, value=Answer.Value.YES)
        services.submit_answer(assessment=assessment, measure=m2, value=Answer.Value.PARTIAL)
        services.submit_answer(assessment=assessment, measure=m3, value=Answer.Value.NO)
        services.submit_answer(assessment=assessment, measure=m4, value=Answer.Value.NOT_APPLICABLE)

        result = services.compute_scores(assessment)

        # global: weighted_sum = 1.0*1.0(M1) + 0.5*0.5(M2) + 0*1.0(M3) = 1.25
        #         weight_total = 1.0(M1) + 0.5(M2) + 1.0(M3) = 2.5 (M4 excluded, N/A)
        assert result["global"] == pytest.approx(round(100 * 1.25 / 2.5, 1))

        by_domain = {d["domain_code"]: d["score"] for d in result["by_domain"]}
        # domaine-a: weighted_sum = 1.0 + 0.25 = 1.25, weight_total = 1.5
        assert by_domain["domaine-a"] == pytest.approx(round(100 * 1.25 / 1.5, 1))
        # domaine-b: only M3 counts (M4 is N/A) -> 0/1.0 -> 0.0
        assert by_domain["domaine-b"] == 0.0

    def test_measure_values_override_for_projected_scoring(self, assessment, measures):
        """compute_scores accepts a measure_values override — this is the
        hook apps.actions uses for the plan's projected score."""
        m1 = measures[0]
        services.submit_answer(assessment=assessment, measure=m1, value=Answer.Value.NO)

        actual = services.compute_scores(assessment)
        projected = services.compute_scores(assessment, measure_values={m1.id: Answer.Value.YES})

        assert actual["global"] < projected["global"]
        assert projected["global"] == 100.0
