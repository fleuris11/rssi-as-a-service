import pytest
from django.urls import reverse
from rest_framework import status

from apps.assessments.models import Assessment, Measure
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


def _answer_all(api_client, headers, assessment_id, measures, value="yes"):
    for measure in measures:
        response = api_client.put(
            reverse("assessment-answer", args=[assessment_id, measure.id]),
            {"value": value},
            format="json",
            **headers,
        )
        assert response.status_code == status.HTTP_200_OK


class TestReferentialEndpoint:
    def test_returns_domains_with_nested_measures(
        self, api_client, referential, tenant, tenant_owner
    ):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("assessment-referential"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["slug"] == referential.slug
        domain_codes = [d["code"] for d in response.data["domains"]]
        assert domain_codes == ["domaine-a", "domaine-b"]
        assert len(response.data["domains"][0]["measures"]) == 2


class TestStartAssessment:
    def test_creates_in_progress_assessment(self, api_client, referential, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(reverse("assessment-start"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "in_progress"
        assert Assessment.all_objects.filter(tenant=tenant).count() == 1

    def test_resumes_instead_of_duplicating(self, api_client, referential, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)

        first = api_client.post(reverse("assessment-start"), **headers)
        second = api_client.post(reverse("assessment-start"), **headers)

        assert first.data["id"] == second.data["id"]
        assert Assessment.all_objects.filter(tenant=tenant).count() == 1

    def test_reader_cannot_start_an_assessment(self, api_client, referential, tenant, user_factory):
        reader = user_factory(email="reader@example.com")
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        headers = _auth(api_client, reader, tenant)

        response = api_client.post(reverse("assessment-start"), **headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestAnswerAndComplete:
    def test_submit_answer_is_reflected_in_progress(
        self, api_client, referential, tenant, tenant_owner
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        start = api_client.post(reverse("assessment-start"), **headers)
        assessment_id = start.data["id"]
        measure = Measure.objects.filter(domain__referential=referential).first()

        answer_response = api_client.put(
            reverse("assessment-answer", args=[assessment_id, measure.id]),
            {"value": "yes", "note": "en place depuis 2024"},
            format="json",
            **headers,
        )
        detail_response = api_client.get(
            reverse("assessment-detail", args=[assessment_id]), **headers
        )

        assert answer_response.status_code == status.HTTP_200_OK
        assert detail_response.data["progress"]["answered"] == 1

    def test_complete_with_missing_answers_returns_400(
        self, api_client, referential, tenant, tenant_owner
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        start = api_client.post(reverse("assessment-start"), **headers)

        response = api_client.post(
            reverse("assessment-complete", args=[start.data["id"]]), **headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_success_returns_score_and_generates_action_plan(
        self, api_client, referential, tenant, tenant_owner
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        start = api_client.post(reverse("assessment-start"), **headers)
        assessment_id = start.data["id"]
        measures = list(Measure.objects.filter(domain__referential=referential))
        # Two gaps (no), two compliant (yes) — expect exactly 2 action items.
        for measure, value in zip(measures, ["yes", "no", "yes", "no"], strict=True):
            api_client.put(
                reverse("assessment-answer", args=[assessment_id, measure.id]),
                {"value": value},
                format="json",
                **headers,
            )

        complete_response = api_client.post(
            reverse("assessment-complete", args=[assessment_id]), **headers
        )
        plan_response = api_client.get(reverse("action-item-list"), **headers)

        assert complete_response.status_code == status.HTTP_200_OK
        assert complete_response.data["status"] == "completed"
        assert complete_response.data["score_global"] is not None
        assert plan_response.data["count"] == 2

    def test_scores_endpoint(self, api_client, referential, tenant, tenant_owner):
        headers = _auth(api_client, tenant_owner, tenant)
        start = api_client.post(reverse("assessment-start"), **headers)
        assessment_id = start.data["id"]
        _answer_all(
            api_client,
            headers,
            assessment_id,
            Measure.objects.filter(domain__referential=referential),
        )
        api_client.post(reverse("assessment-complete", args=[assessment_id]), **headers)

        response = api_client.get(reverse("assessment-scores", args=[assessment_id]), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["global_score"] == 100.0
        assert len(response.data["by_domain"]) == 2

    def test_reader_can_read_but_not_answer(
        self, api_client, referential, tenant, tenant_owner, user_factory
    ):
        owner_headers = _auth(api_client, tenant_owner, tenant)
        start = api_client.post(reverse("assessment-start"), **owner_headers)
        measure = Measure.objects.filter(domain__referential=referential).first()

        reader = user_factory(email="reader@example.com")
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        reader_headers = _auth(api_client, reader, tenant)

        read_response = api_client.get(
            reverse("assessment-detail", args=[start.data["id"]]), **reader_headers
        )
        write_response = api_client.put(
            reverse("assessment-answer", args=[start.data["id"], measure.id]),
            {"value": "yes"},
            format="json",
            **reader_headers,
        )

        assert read_response.status_code == status.HTTP_200_OK
        assert write_response.status_code == status.HTTP_403_FORBIDDEN


class TestTenantIsolation:
    def test_cannot_read_another_tenants_assessment(
        self, api_client, referential, user_factory, tenant_factory
    ):
        owner_a = user_factory(email="owner-a@example.com")
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com")
        tenant_b = tenant_factory(owner_b, name="Entreprise B")

        headers_b = _auth(api_client, owner_b, tenant_b)
        start_b = api_client.post(reverse("assessment-start"), **headers_b)

        headers_a = _auth(api_client, owner_a, tenant_a)
        response = api_client.get(
            reverse("assessment-detail", args=[start_b.data["id"]]), **headers_a
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_history_is_scoped_per_tenant(
        self, api_client, referential, user_factory, tenant_factory
    ):
        owner_a = user_factory(email="owner-a@example.com")
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com")
        tenant_b = tenant_factory(owner_b, name="Entreprise B")

        api_client.post(reverse("assessment-start"), **_auth(api_client, owner_b, tenant_b))

        response = api_client.get(
            reverse("assessment-list"), **_auth(api_client, owner_a, tenant_a)
        )

        assert response.data["count"] == 0
