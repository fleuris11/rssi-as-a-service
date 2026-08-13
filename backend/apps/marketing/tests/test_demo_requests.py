"""Site vitrine — demande de démonstration.

L'endpoint est **public** : c'est, avec l'authentification et le webhook, l'un
des trois seuls points d'entrée non authentifiés de la plateforme. Les tests
portent donc autant sur ce qu'il accepte que sur ce qu'il refuse, et sur le
fait qu'un incident d'envoi d'email ne fasse jamais perdre une demande déjà
enregistrée.
"""

from unittest.mock import patch

import pytest
from django.core import mail
from django.urls import reverse
from rest_framework import status

from apps.marketing.models import DemoRequest

pytestmark = pytest.mark.django_db

VALID = {
    "full_name": "Marie Durand",
    "company": "Cabinet Durand",
    "role": "Gérante",
    "email": "marie.durand@cabinet-durand.example",
    "company_size": "10-49",
    "preferred_slot": "morning",
    "message": "Nous aimerions voir la détection de fuites.",
}


@pytest.fixture(autouse=True)
def _operator_email(settings):
    settings.DEMO_REQUEST_NOTIFICATION_EMAIL = "commercial@example.test"


class TestSubmission:
    def test_a_valid_request_is_stored(self, api_client):
        response = api_client.post(reverse("demo-request-create"), VALID, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        demo_request = DemoRequest.objects.get()
        assert demo_request.company == "Cabinet Durand"
        assert demo_request.status == DemoRequest.Status.NEW

    def test_the_response_announces_a_delay(self, api_client):
        """Le message de succès doit rassurer : sans délai annoncé, le
        prospect ne sait pas s'il doit relancer."""
        response = api_client.post(reverse("demo-request-create"), VALID, format="json")
        assert "jour ouvré" in response.data["detail"]

    def test_no_authentication_required(self, api_client):
        response = api_client.post(reverse("demo-request-create"), VALID, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_optional_fields_can_be_omitted(self, api_client):
        minimal = {
            "full_name": "Jean Martin",
            "company": "Martin SARL",
            "email": "jean@martin.example",
        }
        response = api_client.post(reverse("demo-request-create"), minimal, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_submission_context_is_recorded(self, api_client):
        api_client.post(
            reverse("demo-request-create"),
            VALID,
            format="json",
            HTTP_USER_AGENT="Mozilla/5.0",
            HTTP_X_FORWARDED_FOR="203.0.113.5",
        )
        demo_request = DemoRequest.objects.get()
        assert demo_request.ip_address == "203.0.113.5"
        assert demo_request.user_agent == "Mozilla/5.0"


class TestValidation:
    @pytest.mark.parametrize("field", ["full_name", "company", "email"])
    def test_required_fields_are_enforced(self, api_client, field):
        payload = {k: v for k, v in VALID.items() if k != field}
        response = api_client.post(reverse("demo-request-create"), payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert field in response.data

    def test_malformed_email_is_rejected(self, api_client):
        response = api_client.post(
            reverse("demo-request-create"), {**VALID, "email": "pas-un-email"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_disposable_email_is_rejected(self, api_client):
        response = api_client.post(
            reverse("demo-request-create"), {**VALID, "email": "x@yopmail.com"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert DemoRequest.objects.count() == 0

    def test_a_common_provider_address_is_accepted(self, api_client):
        """Un artisan à son compte n'a souvent qu'une adresse grand public :
        la refuser écarterait de vrais prospects."""
        response = api_client.post(
            reverse("demo-request-create"),
            {**VALID, "email": "jean.martin@gmail.com"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_email_is_normalised_to_lowercase(self, api_client):
        api_client.post(
            reverse("demo-request-create"),
            {**VALID, "email": "Marie@Durand.Example"},
            format="json",
        )
        assert DemoRequest.objects.get().email == "marie@durand.example"

    def test_a_one_character_name_is_rejected(self, api_client):
        response = api_client.post(
            reverse("demo-request-create"), {**VALID, "full_name": "M"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestHoneypot:
    def test_a_filled_honeypot_is_rejected(self, api_client):
        response = api_client.post(
            reverse("demo-request-create"),
            {**VALID, "website": "http://spam.example"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert DemoRequest.objects.count() == 0

    def test_the_rejection_does_not_reveal_the_trap(self, api_client):
        """Un robot qui apprendrait quel champ le trahit contournerait le
        filtre au passage suivant."""
        response = api_client.post(
            reverse("demo-request-create"),
            {**VALID, "website": "http://spam.example"},
            format="json",
        )
        assert "honeypot" not in str(response.data).lower()
        assert "website" not in str(response.data).lower()

    def test_an_empty_honeypot_passes(self, api_client):
        response = api_client.post(
            reverse("demo-request-create"), {**VALID, "website": ""}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED


class TestRateLimiting:
    def test_repeated_submissions_are_throttled(self, api_client):
        codes = []
        for i in range(5):
            response = api_client.post(
                reverse("demo-request-create"),
                {**VALID, "email": f"contact{i}@societe.example"},
                format="json",
            )
            codes.append(response.status_code)

        assert status.HTTP_429_TOO_MANY_REQUESTS in codes


class TestEmails:
    def test_the_prospect_receives_an_acknowledgement(self, api_client):
        api_client.post(reverse("demo-request-create"), VALID, format="json")

        acknowledgements = [m for m in mail.outbox if VALID["email"] in m.to]
        assert len(acknowledgements) == 1
        assert "démonstration" in acknowledgements[0].subject

    def test_the_operator_is_notified_with_the_context(self, api_client):
        api_client.post(reverse("demo-request-create"), VALID, format="json")

        notifications = [m for m in mail.outbox if "commercial@example.test" in m.to]
        assert len(notifications) == 1
        assert "Cabinet Durand" in notifications[0].subject
        assert VALID["email"] in notifications[0].body

    def test_no_operator_configured_still_acknowledges_the_prospect(self, api_client, settings):
        settings.DEMO_REQUEST_NOTIFICATION_EMAIL = ""

        api_client.post(reverse("demo-request-create"), VALID, format="json")

        assert len(mail.outbox) == 1
        assert VALID["email"] in mail.outbox[0].to

    def test_an_smtp_failure_does_not_lose_the_request(self, api_client):
        """La demande est acquise dès l'écriture en base : renvoyer une erreur
        parce que l'email n'est pas parti pousserait le prospect à
        resoumettre, alors que sa demande est bien arrivée."""
        with patch("apps.marketing.services.send_mail", side_effect=OSError("SMTP indisponible")):
            response = api_client.post(reverse("demo-request-create"), VALID, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert DemoRequest.objects.count() == 1


class TestBackOffice:
    def _staff_auth(self, api_client, user_factory):
        staff = user_factory(email="staff@example.com", is_staff=True)
        response = api_client.post(
            reverse("token-obtain-pair"),
            {"email": staff.email, "password": "Str0ng!Passw0rd123"},
            format="json",
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}

    def test_platform_admin_can_list_requests(self, api_client, user_factory):
        api_client.post(reverse("demo-request-create"), VALID, format="json")
        headers = self._staff_auth(api_client, user_factory)

        response = api_client.get(reverse("demo-request-admin-list"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["company"] == "Cabinet Durand"

    def test_a_non_staff_user_cannot_list_requests(self, api_client, tenant_owner):
        response = api_client.post(
            reverse("token-obtain-pair"),
            {"email": tenant_owner.email, "password": "Str0ng!Passw0rd123"},
            format="json",
        )
        headers = {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}

        listing = api_client.get(reverse("demo-request-admin-list"), **headers)

        assert listing.status_code == status.HTTP_403_FORBIDDEN

    def test_anonymous_cannot_list_requests(self, api_client):
        response = api_client.get(reverse("demo-request-admin-list"))
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_status_can_be_updated(self, api_client, user_factory):
        api_client.post(reverse("demo-request-create"), VALID, format="json")
        demo_request = DemoRequest.objects.get()
        headers = self._staff_auth(api_client, user_factory)

        response = api_client.patch(
            reverse("demo-request-admin-detail", args=[demo_request.id]),
            {"status": "contacted"},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        demo_request.refresh_from_db()
        assert demo_request.status == DemoRequest.Status.CONTACTED
