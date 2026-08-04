"""Public interface of the assessments app — other apps must go through
here instead of importing apps.assessments.models directly.

``Assessment``/``Answer`` are tenant-scoped, but every function here is
given an already-resolved ``tenant``/``assessment`` (never derives one from
ambient request context), so — unlike apps.tenants.services, which reads
through the request-scoped manager — these functions consistently use
``all_objects`` with an explicit ``tenant=`` filter. That makes the whole
module correct and unit-testable independently of whether it's called from
a request that went through TenantScopingMiddleware.
"""

from django.utils import timezone

from .models import Answer, Assessment, Domain, Measure, Referential


class AssessmentsError(Exception):
    """Base class for business-rule violations raised by this module."""


class NoActiveReferentialError(AssessmentsError):
    pass


class MeasureNotInReferentialError(AssessmentsError):
    pass


class AssessmentAlreadyCompletedError(AssessmentsError):
    pass


class IncompleteAssessmentError(AssessmentsError):
    def __init__(self, answered, total):
        self.answered = answered
        self.total = total
        super().__init__(
            f"{answered}/{total} mesures répondues : toutes les mesures doivent avoir une "
            "réponse (y compris « non applicable ») avant de terminer l'évaluation."
        )


# Weighting used by the scoring formula (see score_from_values): standard
# measures count fully, "renforcé" ones count for half — they're desirable
# but not baseline-blocking for a maturity score aimed at TPE/PME.
LEVEL_WEIGHTS = {
    Measure.Level.STANDARD: 1.0,
    Measure.Level.RENFORCE: 0.5,
}

VALUE_SCORES = {
    Answer.Value.YES: 1.0,
    Answer.Value.PARTIAL: 0.5,
    Answer.Value.NO: 0.0,
}

# Re-exported so apps.actions can build a projected score (a "done" action
# item's measure counts as full credit) without importing Answer directly.
FULL_CREDIT_VALUE = Answer.Value.YES

# Re-exported so apps.actions can identify which answers are "gaps" worth an
# action item, without importing Answer directly.
GAP_VALUES = {Answer.Value.NO, Answer.Value.PARTIAL}


def get_active_referential() -> Referential:
    referential = Referential.objects.filter(is_active=True).order_by("-id").first()
    if referential is None:
        raise NoActiveReferentialError(
            "Aucun référentiel actif : lancez `manage.py load_anssi_referential`."
        )
    return referential


def get_referential_structure(referential: Referential):
    """Domains (ordered) with their measures prefetched, for rendering the
    questionnaire or the radar's category list."""
    return (
        Domain.objects.filter(referential=referential)
        .order_by("order")
        .prefetch_related("measures")
    )


def get_current_assessment(tenant):
    return (
        Assessment.all_objects.filter(tenant=tenant, status=Assessment.Status.IN_PROGRESS)
        .order_by("-started_at")
        .first()
    )


def start_or_resume_assessment(*, tenant, user):
    current = get_current_assessment(tenant)
    if current is not None:
        return current
    referential = get_active_referential()
    return Assessment.all_objects.create(tenant=tenant, referential=referential, started_by=user)


def list_assessments(tenant):
    """History of a tenant's assessments, most recent first (US-2.3)."""
    return Assessment.all_objects.filter(tenant=tenant).order_by("-started_at")


def get_latest_completed_assessment(tenant):
    return (
        Assessment.all_objects.filter(tenant=tenant, status=Assessment.Status.COMPLETED)
        .order_by("-completed_at")
        .first()
    )


def get_assessment(*, tenant, assessment_id):
    return Assessment.all_objects.filter(tenant=tenant, id=assessment_id).first()


def submit_answer(
    *, assessment: Assessment, measure: Measure, value: str, note: str = ""
) -> Answer:
    if assessment.status == Assessment.Status.COMPLETED:
        raise AssessmentAlreadyCompletedError("Cette évaluation est déjà terminée.")
    if measure.domain.referential_id != assessment.referential_id:
        raise MeasureNotInReferentialError(
            "Cette mesure n'appartient pas au référentiel de cette évaluation."
        )
    answer, _created = Answer.all_objects.update_or_create(
        assessment=assessment,
        measure=measure,
        defaults={"tenant": assessment.tenant, "value": value, "note": note},
    )
    return answer


def list_answers(assessment: Assessment):
    """Every answer recorded on ``assessment`` — used to pre-fill the
    questionnaire when a tenant resumes an in-progress assessment."""
    return Answer.all_objects.filter(
        tenant=assessment.tenant, assessment=assessment
    ).select_related("measure")


def get_progress(assessment: Assessment) -> dict:
    measures = list(Measure.objects.filter(domain__referential=assessment.referential))
    answered_ids = set(
        Answer.all_objects.filter(tenant=assessment.tenant, assessment=assessment).values_list(
            "measure_id", flat=True
        )
    )
    by_domain = []
    for domain in Domain.objects.filter(referential=assessment.referential).order_by("order"):
        domain_measures = [m for m in measures if m.domain_id == domain.id]
        by_domain.append(
            {
                "domain_code": domain.code,
                "domain_name": domain.name,
                "answered": sum(1 for m in domain_measures if m.id in answered_ids),
                "total": len(domain_measures),
            }
        )
    return {
        "answered": len(answered_ids),
        "total": len(measures),
        "by_domain": by_domain,
    }


def score_from_values(measure_values: dict, measures) -> float | None:
    """Weighted score (0-100) for ``measures`` given a ``{measure_id: value}``
    mapping. Measures with no value, or an explicit "non applicable" value,
    are excluded from the denominator. Returns None when nothing scorable
    remains (e.g. every measure is N/A, or none have been answered yet) —
    never a misleading 0.

    Public and reused as-is by apps.actions.services for the projected
    score (same formula, substituting "done" action items' measures with a
    hypothetical "yes").
    """
    weighted_sum = 0.0
    weight_total = 0.0
    for measure in measures:
        value = measure_values.get(measure.id)
        if value is None or value == Answer.Value.NOT_APPLICABLE:
            continue
        weight = LEVEL_WEIGHTS[measure.level]
        weighted_sum += VALUE_SCORES[value] * weight
        weight_total += weight
    if weight_total == 0:
        return None
    return round(100 * weighted_sum / weight_total, 1)


def get_answer_values(assessment: Assessment) -> dict:
    """``{measure_id: value}`` for every answer recorded on ``assessment``.

    Exposed publicly so apps.actions can build a *projected* score (actual
    answers with "done" action items' measures overridden to full credit)
    via compute_scores(assessment, measure_values=...) without importing
    this app's models directly.
    """
    return dict(
        Answer.all_objects.filter(tenant=assessment.tenant, assessment=assessment).values_list(
            "measure_id", "value"
        )
    )


def get_referential_measures(referential: Referential):
    return list(Measure.objects.filter(domain__referential=referential).select_related("domain"))


def compute_scores(assessment: Assessment, *, measure_values: dict | None = None) -> dict:
    """Global + per-domain weighted scores.

    Reads the assessment's actual answers by default; pass
    ``measure_values`` to score a hypothetical set of answers instead (used
    by apps.actions for the plan's projected score).
    """
    measures = get_referential_measures(assessment.referential)
    if measure_values is None:
        measure_values = get_answer_values(assessment)

    by_domain = []
    for domain in Domain.objects.filter(referential=assessment.referential).order_by("order"):
        domain_measures = [m for m in measures if m.domain_id == domain.id]
        by_domain.append(
            {
                "domain_code": domain.code,
                "domain_name": domain.name,
                "score": score_from_values(measure_values, domain_measures),
            }
        )

    return {
        "global": score_from_values(measure_values, measures),
        "by_domain": by_domain,
    }


def complete_assessment(assessment: Assessment) -> Assessment:
    if assessment.status == Assessment.Status.COMPLETED:
        raise AssessmentAlreadyCompletedError("Cette évaluation est déjà terminée.")

    total = Measure.objects.filter(domain__referential=assessment.referential).count()
    answered = Answer.all_objects.filter(tenant=assessment.tenant, assessment=assessment).count()
    if answered < total:
        raise IncompleteAssessmentError(answered, total)

    scores = compute_scores(assessment)
    assessment.status = Assessment.Status.COMPLETED
    assessment.completed_at = timezone.now()
    assessment.score_global = scores["global"]
    assessment.save(update_fields=["status", "completed_at", "score_global"])
    return assessment
