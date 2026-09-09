"""Public interface of the actions app — other apps must go through here
instead of importing apps.actions.models directly. Like apps.assessments,
every function here is given an already-resolved tenant/assessment/item,
so it consistently uses ``all_objects`` with an explicit ``tenant=`` filter
rather than the request-scoped manager.
"""

from django.db.models import Count, Q
from django.utils import timezone

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
    # Le périmètre de l'évaluation, et non le référentiel entier (V2-4) :
    # quand le diagnostic a porté sur un sous-ensemble de 10 mesures, le plan
    # d'action ne doit pas en lister 42 dont 32 n'ont jamais été posées.
    measures = assessments_services.get_assessment_measures(assessment)
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


def list_action_items(tenant, *, assessment=None, status=None, referential=None):
    """The tenant's action items, quick wins (high impact / low effort) first.

    ``referential`` filtre le plan sur un seul référentiel ; sans lui, le plan
    est CONSOLIDÉ — toutes les évaluations du client, tous référentiels
    confondus. Consolider des actions, contrairement à consolider des scores,
    ne demande aucune règle d'arbitrage : une action est une chose à faire, et
    deux référentiels qui demandent la même chose donnent deux lignes qu'on
    voit côte à côte. Ce que nous ne faisons PAS, faute de table de
    correspondance : les fusionner (ADR-030).
    """
    queryset = ActionItem.all_objects.filter(tenant=tenant).select_related(
        "measure", "measure__domain", "measure__referential", "assignee"
    )
    if assessment is not None:
        queryset = queryset.filter(assessment=assessment)
    if status is not None:
        queryset = queryset.filter(status=status)
    if referential is not None:
        queryset = queryset.filter(measure__referential=referential)
    items = sorted(queryset, key=priority_ratio, reverse=True)
    # Le plan affiche le MÊME énoncé que le questionnaire : si le client a
    # reformulé une mesure, la voir revenir dans sa formulation d'origine sur
    # l'écran d'à côté lui ferait douter qu'il s'agit de la même.
    assessments_services.apply_overrides([item.measure for item in items], tenant)
    return items


def plan_by_referential(tenant) -> list[dict]:
    """Le plan d'action, référentiel par référentiel : ce qui reste à faire
    de chaque côté quand un client en suit plusieurs."""
    lignes = (
        ActionItem.all_objects.filter(tenant=tenant)
        .values("measure__referential_id", "measure__referential__name")
        .annotate(
            total=Count("id"),
            done=Count("id", filter=Q(status=ActionItem.Status.DONE)),
            open=Count("id", filter=~Q(status=ActionItem.Status.DONE)),
        )
        .order_by("measure__referential__name")
    )
    return [
        {
            "referential_id": ligne["measure__referential_id"],
            "referential_name": ligne["measure__referential__name"],
            "total": ligne["total"],
            "done": ligne["done"],
            "open": ligne["open"],
            "completion_rate": (
                round(100 * ligne["done"] / ligne["total"], 1) if ligne["total"] else None
            ),
        }
        for ligne in lignes
    ]


def get_action_item(*, tenant, item_id):
    return (
        ActionItem.all_objects.filter(tenant=tenant, id=item_id)
        .select_related("measure", "measure__domain", "assignee")
        .first()
    )


def set_due_date(item: ActionItem, due_date) -> ActionItem:
    """Échéance d'une action. ``None`` la retire."""
    item.due_date = due_date
    item.save(update_fields=["due_date", "updated_at"])
    return item


def update_status(item: ActionItem, status: str) -> ActionItem:
    item.status = status
    # V2-3 : la date de fin est posée au passage à « fait », et RETIRÉE si
    # l'action rouvre. Sans le second cas, une action rouverte resterait
    # comptée comme terminée dans le trimestre où elle l'avait été — un
    # tableau de bord qui ne sait pas revenir en arrière ment une fois sur
    # deux.
    item.completed_at = timezone.now() if status == ActionItem.Status.DONE else None
    item.save(update_fields=["status", "completed_at", "updated_at"])
    return item


# --- Indicateurs pour le comité (V2-3, ADR-028) -----------------------------


def action_plan_indicators(tenant, *, start, end, today=None) -> dict:
    """Plan d'action : ce qui reste, ce qui a avancé, ce qui traîne.

    Tout en base : cinq agrégats, aucune instance matérialisée. Le plan d'un
    tenant compte quelques dizaines d'actions et non des milliers, mais la
    règle vaut quand même — un tableau de bord qui charge des objets « parce
    qu'il n'y en a pas beaucoup » finit par en charger beaucoup.
    """
    today = today or timezone.localdate()
    du_tenant = ActionItem.all_objects.filter(tenant=tenant)

    comptes = du_tenant.aggregate(
        total=Count("id"),
        done=Count("id", filter=Q(status=ActionItem.Status.DONE)),
        in_progress=Count("id", filter=Q(status=ActionItem.Status.IN_PROGRESS)),
        todo=Count("id", filter=Q(status=ActionItem.Status.TODO)),
        # « En retard » ne concerne QUE ce qui a une échéance dépassée et
        # n'est pas fait. Une action sans échéance n'est pas en retard : elle
        # est sans échéance, ce qui se dit à côté.
        overdue=Count(
            "id",
            filter=Q(due_date__lt=today) & ~Q(status=ActionItem.Status.DONE),
        ),
        without_due_date=Count(
            "id", filter=Q(due_date__isnull=True) & ~Q(status=ActionItem.Status.DONE)
        ),
    )

    mouvements = du_tenant.aggregate(
        completed_in_period=Count("id", filter=Q(completed_at__gte=start, completed_at__lte=end)),
        created_in_period=Count("id", filter=Q(created_at__gte=start, created_at__lte=end)),
    )

    ouvertes = comptes["todo"] + comptes["in_progress"]
    return {
        "total": comptes["total"],
        "open": ouvertes,
        "todo": comptes["todo"],
        "in_progress": comptes["in_progress"],
        "done": comptes["done"],
        "overdue": comptes["overdue"],
        "without_due_date": comptes["without_due_date"],
        "completed_in_period": mouvements["completed_in_period"],
        "created_in_period": mouvements["created_in_period"],
        # Ce que le comité regarde : la part du plan effectivement close.
        "completion_rate": (
            round(100 * comptes["done"] / comptes["total"], 1) if comptes["total"] else None
        ),
        # V2-4 : le détail par référentiel accompagne le total, comme pour le
        # score (ADR-030). Un « 40 % » qui recouvre 80 % sur l'ANSSI et 10 %
        # sur ISO ne dit pas la même chose que 40 % partout.
        "by_referential": plan_by_referential(tenant),
    }


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
