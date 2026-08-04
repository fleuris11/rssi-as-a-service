"""Public interface of the actions app — other apps must go through here
instead of importing apps.actions.models directly. Like apps.assessments,
every function here is given an already-resolved tenant/assessment/item,
so it consistently uses ``all_objects`` with an explicit ``tenant=`` filter
rather than the request-scoped manager.
"""

from apps.assessments import services as assessments_services
from apps.tenants import services as tenants_services

from .models import ActionItem


class ActionsError(Exception):
    """Base class for business-rule violations raised by this module."""


class InvalidAssigneeError(ActionsError):
    pass


# Priority = impact / effort ("ratio", cadrage M3): a high-impact, low-effort
# gap (a quick win) ranks highest; a low-impact, high-effort one ranks lowest.
IMPACT_RANK = {"low": 1, "medium": 2, "high": 3}
EFFORT_RANK = {"low": 1, "medium": 2, "high": 3}


def priority_ratio(item: ActionItem) -> float:
    return IMPACT_RANK[item.measure.impact] / EFFORT_RANK[item.measure.effort]


def generate_action_plan(assessment) -> int:
    """Creates a TODO action item for every gap (non/partial answer) of a
    completed assessment. Idempotent: measures that already have an item
    for this assessment are left untouched, so re-running (or a retried
    request) never duplicates or resets progress already made.

    Returns the number of items actually created.
    """
    measures = assessments_services.get_referential_measures(assessment.referential)
    values = assessments_services.get_answer_values(assessment)

    created_count = 0
    for measure in measures:
        if values.get(measure.id) not in assessments_services.GAP_VALUES:
            continue
        _item, created = ActionItem.all_objects.get_or_create(
            assessment=assessment,
            measure=measure,
            defaults={"tenant": assessment.tenant, "status": ActionItem.Status.TODO},
        )
        if created:
            created_count += 1
    return created_count


def list_action_items(tenant, *, assessment=None, status=None):
    """The tenant's action items, quick wins (high impact / low effort) first."""
    queryset = ActionItem.all_objects.filter(tenant=tenant).select_related(
        "measure", "measure__domain", "assignee"
    )
    if assessment is not None:
        queryset = queryset.filter(assessment=assessment)
    if status is not None:
        queryset = queryset.filter(status=status)
    return sorted(queryset, key=priority_ratio, reverse=True)


def get_action_item(*, tenant, item_id):
    return (
        ActionItem.all_objects.filter(tenant=tenant, id=item_id)
        .select_related("measure", "measure__domain", "assignee")
        .first()
    )


def update_status(item: ActionItem, status: str) -> ActionItem:
    item.status = status
    item.save(update_fields=["status", "updated_at"])
    return item


def assign_action_item(item: ActionItem, user) -> ActionItem:
    """Assigns ``item`` to ``user``, or unassigns it if ``user`` is None.
    The assignee must be a member of the item's tenant."""
    if user is not None:
        membership = tenants_services.get_membership(user=user, tenant_id=item.tenant_id)
        if membership is None:
            raise InvalidAssigneeError("Cette personne n'est pas membre de cette entreprise.")
    item.assignee = user
    item.save(update_fields=["assignee", "updated_at"])
    return item


def set_note(item: ActionItem, note: str) -> ActionItem:
    item.note = note
    item.save(update_fields=["note", "updated_at"])
    return item


def compute_projected_score(assessment) -> dict:
    """Same shape as assessments.services.compute_scores, but every "done"
    action item's measure counts as full credit — this is the "score
    projeté" the plan advances toward as items get completed."""
    values = dict(assessments_services.get_answer_values(assessment))
    done_measure_ids = ActionItem.all_objects.filter(
        tenant=assessment.tenant, assessment=assessment, status=ActionItem.Status.DONE
    ).values_list("measure_id", flat=True)
    for measure_id in done_measure_ids:
        values[measure_id] = assessments_services.FULL_CREDIT_VALUE
    return assessments_services.compute_scores(assessment, measure_values=values)
