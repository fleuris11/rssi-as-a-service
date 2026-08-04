import pytest
from django.urls import reverse
from rest_framework import status

from apps.actions.models import ActionItem
from apps.assessments import services as assessments_services
from apps.assessments.models import Measure
from apps.tenants.models import Membership

pytestmark = pytest.mark.django_db


def _login(api_client, email, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


def _auth(api_client, user, tenant):
    access = _login(api_client, user.email)
    return {"HTTP_AUTHORIZATION": f"Bearer {access}", "HTTP_X_TENANT_ID": str(tenant.id)}


@pytest.fixture
def completed_assessment_with_gaps(assessment, referential):
    measures = list(Measure.objects.filter(domain__referential=referential).order_by("number"))
    for measure, value in zip(measures, ["yes", "no", "no", "yes"], strict=True):
        assessments_services.submit_answer(assessment=assessment, measure=measure, value=value)
    assessments_services.complete_assessment(assessment)
    from apps.actions import services as actions_services

    actions_services.generate_action_plan(assessment)
    return assessment


class TestActionItemListAPI:
    def test_lists_the_generated_plan(
        self, api_client, completed_assessment_with_gaps, tenant, tenant_owner
    ):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("action-item-list"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        # Quick wins (higher impact/effort ratio) come first.
        priorities = [item["priority"] for item in response.data["results"]]
        assert priorities == sorted(priorities, reverse=True)

    def test_filter_by_status(
        self, api_client, completed_assessment_with_gaps, tenant, tenant_owner
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        item = ActionItem.all_objects.filter(assessment=completed_assessment_with_gaps).first()
        api_client.patch(
            reverse("action-item-detail", args=[item.id]),
            {"status": "done"},
            format="json",
            **headers,
        )

        response = api_client.get(reverse("action-item-list"), {"status": "done"}, **headers)

        assert response.data["count"] == 1


class TestActionItemDetailAPI:
    def test_contributor_can_change_status(
        self, api_client, completed_assessment_with_gaps, tenant, tenant_owner
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        item = ActionItem.all_objects.filter(assessment=completed_assessment_with_gaps).first()

        response = api_client.patch(
            reverse("action-item-detail", args=[item.id]),
            {"status": "in_progress"},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "in_progress"

    def test_reader_cannot_change_status(
        self, api_client, completed_assessment_with_gaps, tenant, user_factory
    ):
        reader = user_factory(email="reader@example.com")
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        headers = _auth(api_client, reader, tenant)
        item = ActionItem.all_objects.filter(assessment=completed_assessment_with_gaps).first()

        response = api_client.patch(
            reverse("action-item-detail", args=[item.id]),
            {"status": "done"},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_assign_to_tenant_member_succeeds(
        self, api_client, completed_assessment_with_gaps, tenant, tenant_owner, user_factory
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        item = ActionItem.all_objects.filter(assessment=completed_assessment_with_gaps).first()
        contributor = user_factory(email="contributor@example.com")
        Membership.all_objects.create(
            tenant=tenant, user=contributor, role=Membership.Role.CONTRIBUTOR
        )

        response = api_client.patch(
            reverse("action-item-detail", args=[item.id]),
            {"assignee": str(contributor.id)},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["assignee_email"] == "contributor@example.com"

    def test_assign_to_outsider_returns_400(
        self, api_client, completed_assessment_with_gaps, tenant, tenant_owner, user_factory
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        item = ActionItem.all_objects.filter(assessment=completed_assessment_with_gaps).first()
        outsider = user_factory(email="outsider@example.com")

        response = api_client.patch(
            reverse("action-item-detail", args=[item.id]),
            {"assignee": str(outsider.id)},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestProjectedScoreAPI:
    def test_returns_higher_score_once_items_are_done(
        self, api_client, completed_assessment_with_gaps, tenant, tenant_owner
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        actual = api_client.get(
            reverse("assessment-scores", args=[completed_assessment_with_gaps.id]), **headers
        )
        item = ActionItem.all_objects.filter(assessment=completed_assessment_with_gaps).first()
        api_client.patch(
            reverse("action-item-detail", args=[item.id]),
            {"status": "done"},
            format="json",
            **headers,
        )

        projected = api_client.get(reverse("action-projected-score"), **headers)

        assert projected.status_code == status.HTTP_200_OK
        assert projected.data["global_score"] > actual.data["global_score"]


class TestActionsTenantIsolation:
    def test_list_only_returns_the_selected_tenants_items(
        self, api_client, referential, user_factory, tenant_factory
    ):
        owner_a = user_factory(email="owner-a@example.com")
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com")
        tenant_b = tenant_factory(owner_b, name="Entreprise B")

        headers_b = _auth(api_client, owner_b, tenant_b)
        start_b = api_client.post(reverse("assessment-start"), **headers_b)
        for measure in Measure.objects.filter(domain__referential=referential):
            api_client.put(
                reverse("assessment-answer", args=[start_b.data["id"], measure.id]),
                {"value": "no"},
                format="json",
                **headers_b,
            )
        api_client.post(reverse("assessment-complete", args=[start_b.data["id"]]), **headers_b)

        headers_a = _auth(api_client, owner_a, tenant_a)
        response = api_client.get(reverse("action-item-list"), **headers_a)

        assert response.data["count"] == 0

    def test_cannot_patch_another_tenants_item(
        self, api_client, completed_assessment_with_gaps, tenant, user_factory, tenant_factory
    ):
        item = ActionItem.all_objects.filter(assessment=completed_assessment_with_gaps).first()
        outsider = user_factory(email="outsider-owner@example.com")
        outsider_tenant = tenant_factory(outsider, name="Entreprise étrangère")
        headers = _auth(api_client, outsider, outsider_tenant)

        response = api_client.patch(
            reverse("action-item-detail", args=[item.id]),
            {"status": "done"},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
