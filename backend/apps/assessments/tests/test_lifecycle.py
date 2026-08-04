import pytest

from apps.assessments import services
from apps.assessments.models import Answer, Assessment, Measure, Referential

pytestmark = pytest.mark.django_db


class TestStartOrResume:
    def test_creates_new_assessment_against_active_referential(
        self, referential, tenant, tenant_owner
    ):
        assessment = services.start_or_resume_assessment(tenant=tenant, user=tenant_owner)

        assert assessment.tenant_id == tenant.id
        assert assessment.referential_id == referential.id
        assert assessment.status == Assessment.Status.IN_PROGRESS

    def test_resumes_existing_in_progress_assessment(self, referential, tenant, tenant_owner):
        first = services.start_or_resume_assessment(tenant=tenant, user=tenant_owner)
        second = services.start_or_resume_assessment(tenant=tenant, user=tenant_owner)

        assert first.id == second.id
        assert Assessment.all_objects.filter(tenant=tenant).count() == 1

    def test_raises_without_an_active_referential(self, tenant, tenant_owner):
        with pytest.raises(services.NoActiveReferentialError):
            services.start_or_resume_assessment(tenant=tenant, user=tenant_owner)


class TestSubmitAnswer:
    def test_creates_then_updates_the_same_row(self, assessment, referential):
        measure = Measure.objects.filter(domain__referential=referential).first()

        services.submit_answer(assessment=assessment, measure=measure, value=Answer.Value.NO)
        services.submit_answer(
            assessment=assessment, measure=measure, value=Answer.Value.YES, note="corrigé"
        )

        answers = Answer.all_objects.filter(assessment=assessment, measure=measure)
        assert answers.count() == 1
        assert answers.first().value == Answer.Value.YES
        assert answers.first().note == "corrigé"

    def test_rejects_answer_on_completed_assessment(self, assessment, referential):
        measures = list(Measure.objects.filter(domain__referential=referential))
        for measure in measures:
            services.submit_answer(assessment=assessment, measure=measure, value=Answer.Value.YES)
        services.complete_assessment(assessment)

        with pytest.raises(services.AssessmentAlreadyCompletedError):
            services.submit_answer(
                assessment=assessment, measure=measures[0], value=Answer.Value.NO
            )

    def test_rejects_measure_from_another_referential(self, assessment):
        other_referential = Referential.objects.create(
            slug="other", name="Autre référentiel", version="1.0"
        )
        from apps.assessments.models import Domain

        other_domain = Domain.objects.create(referential=other_referential, code="d", name="D")
        foreign_measure = Measure.objects.create(
            domain=other_domain,
            code="FOREIGN",
            official_title="Mesure étrangère",
            plain_language="?",
            level=Measure.Level.STANDARD,
            effort=Measure.Effort.LOW,
            impact=Measure.Impact.LOW,
        )

        with pytest.raises(services.MeasureNotInReferentialError):
            services.submit_answer(
                assessment=assessment, measure=foreign_measure, value=Answer.Value.YES
            )


class TestProgress:
    def test_counts_answered_measures_by_domain(self, assessment, referential):
        measures = list(Measure.objects.filter(domain__referential=referential).order_by("code"))
        services.submit_answer(assessment=assessment, measure=measures[0], value=Answer.Value.YES)
        services.submit_answer(assessment=assessment, measure=measures[2], value=Answer.Value.NO)

        progress = services.get_progress(assessment)

        assert progress["answered"] == 2
        assert progress["total"] == 4
        by_domain = {d["domain_code"]: d for d in progress["by_domain"]}
        assert by_domain["domaine-a"]["answered"] == 1
        assert by_domain["domaine-a"]["total"] == 2
        assert by_domain["domaine-b"]["answered"] == 1
        assert by_domain["domaine-b"]["total"] == 2


class TestCompleteAssessment:
    def test_requires_every_measure_answered(self, assessment, referential):
        measures = list(Measure.objects.filter(domain__referential=referential))
        services.submit_answer(assessment=assessment, measure=measures[0], value=Answer.Value.YES)

        with pytest.raises(services.IncompleteAssessmentError) as excinfo:
            services.complete_assessment(assessment)
        assert excinfo.value.answered == 1
        assert excinfo.value.total == 4

    def test_na_counts_as_answered_for_completion(self, assessment, referential):
        """ "Non applicable" is a valid, complete answer — it just doesn't
        contribute to the score's denominator (see test_scoring.py)."""
        measures = list(Measure.objects.filter(domain__referential=referential))
        for measure in measures:
            services.submit_answer(
                assessment=assessment, measure=measure, value=Answer.Value.NOT_APPLICABLE
            )

        completed = services.complete_assessment(assessment)

        assert completed.status == Assessment.Status.COMPLETED
        assert completed.score_global is None

    def test_success_snapshots_status_and_score(self, assessment, referential):
        measures = list(Measure.objects.filter(domain__referential=referential))
        for measure in measures:
            services.submit_answer(assessment=assessment, measure=measure, value=Answer.Value.YES)

        completed = services.complete_assessment(assessment)

        assert completed.status == Assessment.Status.COMPLETED
        assert completed.completed_at is not None
        assert completed.score_global == 100.0

    def test_cannot_complete_twice(self, assessment, referential):
        for measure in Measure.objects.filter(domain__referential=referential):
            services.submit_answer(assessment=assessment, measure=measure, value=Answer.Value.YES)
        services.complete_assessment(assessment)

        with pytest.raises(services.AssessmentAlreadyCompletedError):
            services.complete_assessment(assessment)


class TestHistory:
    def test_list_assessments_orders_most_recent_first(self, referential, tenant, tenant_owner):
        first = Assessment.all_objects.create(tenant=tenant, referential=referential)
        second = Assessment.all_objects.create(tenant=tenant, referential=referential)

        history = list(services.list_assessments(tenant))

        assert [a.id for a in history] == [second.id, first.id]

    def test_get_latest_completed_assessment_ignores_in_progress(
        self, referential, tenant, tenant_owner
    ):
        Assessment.all_objects.create(tenant=tenant, referential=referential)  # in progress

        assert services.get_latest_completed_assessment(tenant) is None
