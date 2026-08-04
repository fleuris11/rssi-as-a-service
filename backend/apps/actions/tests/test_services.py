import pytest

from apps.actions import services
from apps.actions.models import ActionItem
from apps.assessments import services as assessments_services
from apps.assessments.models import Answer, Measure
from apps.tenants.models import Membership

pytestmark = pytest.mark.django_db


@pytest.fixture
def measures(referential):
    return list(Measure.objects.filter(domain__referential=referential).order_by("code"))


class TestGenerateActionPlan:
    def test_creates_items_only_for_gaps(self, assessment, measures):
        m1, m2, m3, m4 = measures
        assessments_services.submit_answer(
            assessment=assessment, measure=m1, value=Answer.Value.YES
        )
        assessments_services.submit_answer(assessment=assessment, measure=m2, value=Answer.Value.NO)
        assessments_services.submit_answer(
            assessment=assessment, measure=m3, value=Answer.Value.PARTIAL
        )
        assessments_services.submit_answer(
            assessment=assessment, measure=m4, value=Answer.Value.NOT_APPLICABLE
        )

        created = services.generate_action_plan(assessment)

        assert created == 2
        items = ActionItem.all_objects.filter(assessment=assessment)
        assert {item.measure_id for item in items} == {m2.id, m3.id}
        assert all(item.status == ActionItem.Status.TODO for item in items)

    def test_is_idempotent(self, assessment, measures):
        assessments_services.submit_answer(
            assessment=assessment, measure=measures[0], value=Answer.Value.NO
        )

        first_run = services.generate_action_plan(assessment)
        second_run = services.generate_action_plan(assessment)

        assert first_run == 1
        assert second_run == 0
        assert ActionItem.all_objects.filter(assessment=assessment).count() == 1

    def test_no_gaps_creates_nothing(self, assessment, measures):
        for measure in measures:
            assessments_services.submit_answer(
                assessment=assessment, measure=measure, value=Answer.Value.YES
            )

        created = services.generate_action_plan(assessment)

        assert created == 0
        assert ActionItem.all_objects.filter(assessment=assessment).count() == 0


class TestPriorityRatio:
    def test_quick_wins_rank_above_costly_low_impact_items(self, assessment, measures, tenant):
        m1, _m2, _m3, m4 = measures  # M1: impact high/effort low ; M4: impact high/effort high
        quick_win = ActionItem.all_objects.create(tenant=tenant, assessment=assessment, measure=m1)
        costly = ActionItem.all_objects.create(tenant=tenant, assessment=assessment, measure=m4)

        assert services.priority_ratio(quick_win) > services.priority_ratio(costly)

    def test_list_action_items_orders_quick_wins_first(self, assessment, measures, tenant):
        m1, _m2, _m3, m4 = measures
        ActionItem.all_objects.create(tenant=tenant, assessment=assessment, measure=m4)
        ActionItem.all_objects.create(tenant=tenant, assessment=assessment, measure=m1)

        ordered = services.list_action_items(tenant)

        assert [item.measure_id for item in ordered] == [m1.id, m4.id]


class TestUpdateAndAssign:
    def test_update_status(self, assessment, measures, tenant):
        item = ActionItem.all_objects.create(
            tenant=tenant, assessment=assessment, measure=measures[0]
        )

        services.update_status(item, ActionItem.Status.IN_PROGRESS)

        item.refresh_from_db()
        assert item.status == ActionItem.Status.IN_PROGRESS

    def test_assign_to_a_tenant_member_succeeds(
        self, assessment, measures, tenant, tenant_owner, user_factory
    ):
        item = ActionItem.all_objects.create(
            tenant=tenant, assessment=assessment, measure=measures[0]
        )
        contributor = user_factory(email="contributor@example.com")
        Membership.all_objects.create(
            tenant=tenant, user=contributor, role=Membership.Role.CONTRIBUTOR
        )

        services.assign_action_item(item, contributor)

        item.refresh_from_db()
        assert item.assignee_id == contributor.id

    def test_assign_to_a_non_member_is_rejected(self, assessment, measures, tenant, user_factory):
        item = ActionItem.all_objects.create(
            tenant=tenant, assessment=assessment, measure=measures[0]
        )
        outsider = user_factory(email="outsider@example.com")

        with pytest.raises(services.InvalidAssigneeError):
            services.assign_action_item(item, outsider)

        item.refresh_from_db()
        assert item.assignee_id is None

    def test_unassign_with_none(self, assessment, measures, tenant, tenant_owner):
        item = ActionItem.all_objects.create(
            tenant=tenant, assessment=assessment, measure=measures[0], assignee=tenant_owner
        )

        services.assign_action_item(item, None)

        item.refresh_from_db()
        assert item.assignee_id is None


class TestProjectedScore:
    def test_done_items_count_as_full_credit(self, assessment, measures):
        m1, m2, _m3, _m4 = measures
        assessments_services.submit_answer(assessment=assessment, measure=m1, value=Answer.Value.NO)
        assessments_services.submit_answer(assessment=assessment, measure=m2, value=Answer.Value.NO)
        services.generate_action_plan(assessment)
        item = ActionItem.all_objects.get(assessment=assessment, measure=m1)
        services.update_status(item, ActionItem.Status.DONE)

        actual = assessments_services.compute_scores(assessment)
        projected = services.compute_projected_score(assessment)

        assert actual["global"] == 0.0
        # M1 (weight 1.0) now counts as "yes", M2 (weight 0.5) still "non" ->
        # weighted_sum = 1.0, weight_total = 1.5
        assert projected["global"] == pytest.approx(round(100 * 1.0 / 1.5, 1))
        assert projected["global"] > actual["global"]

    def test_projected_score_without_any_done_item_matches_actual(self, assessment, measures):
        assessments_services.submit_answer(
            assessment=assessment, measure=measures[0], value=Answer.Value.PARTIAL
        )

        actual = assessments_services.compute_scores(assessment)
        projected = services.compute_projected_score(assessment)

        assert actual == projected
