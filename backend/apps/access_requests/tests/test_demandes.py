"""Le mécanisme de demande — générique, et vérifié comme tel.

Les tests portent sur DEUX sujets (un référentiel, une fonctionnalité d'offre)
précisément parce que le mécanisme doit servir au-delà de V2-4 : un test qui ne
connaîtrait que les référentiels laisserait passer un couplage.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.access_requests import services, subjects
from apps.access_requests.models import AccessRequest
from apps.assessments import services as assessments_services
from apps.platform_admin.models import AdminAuditLog, PlatformAdminProfile

pytestmark = pytest.mark.django_db


def _login(api_client, email, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


def _auth(api_client, user, tenant=None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {_login(api_client, user.email)}"}
    if tenant is not None:
        headers["HTTP_X_TENANT_ID"] = str(tenant.id)
    return headers


@pytest.fixture
def admin_plateforme(user_factory):
    user = user_factory(email="console@example.com", is_staff=True)
    PlatformAdminProfile.objects.create(user=user, level=PlatformAdminProfile.Level.FULL)
    return user


@pytest.fixture
def non_attribue(tenant, second_referential):
    """Un référentiel que ce client n'a pas — le point de départ d'une
    demande."""
    assessments_services.revoke_referential(tenant=tenant, referential=second_referential)
    return second_referential


class TestDeposerUneDemande:
    def test_enregistre_qui_demande_quoi_et_pourquoi(self, tenant, tenant_owner, non_attribue):
        demande = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
            reason="Notre donneur d'ordre l'exige.",
        )

        assert demande.status == AccessRequest.Status.PENDING
        assert demande.requested_by == tenant_owner
        assert demande.reason == "Notre donneur d'ordre l'exige."
        assert demande.created_at is not None

    def test_fige_le_libelle_du_sujet(self, tenant, tenant_owner, non_attribue):
        """Le référentiel peut être renommé ensuite : la demande resterait
        lisible."""
        demande = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
        )
        non_attribue.name = "Nom tout autre"
        non_attribue.save(update_fields=["name"])

        demande.refresh_from_db()
        assert demande.subject_label == "Autre référentiel"

    def test_refuse_un_sujet_inconnu(self, tenant, tenant_owner):
        with pytest.raises(services.UnknownSubjectError):
            services.create_request(
                tenant=tenant,
                user=tenant_owner,
                subject_type="quelque-chose",
                subject_key="x",
            )

    def test_refuse_un_element_introuvable(self, tenant, tenant_owner):
        with pytest.raises(services.UnknownSubjectError):
            services.create_request(
                tenant=tenant,
                user=tenant_owner,
                subject_type=subjects.REFERENTIAL,
                subject_key="referentiel-qui-n-existe-pas",
            )

    def test_refuse_de_demander_ce_qu_on_a_deja(self, tenant, tenant_owner, referential):
        with pytest.raises(services.AlreadyHeldError):
            services.create_request(
                tenant=tenant,
                user=tenant_owner,
                subject_type=subjects.REFERENTIAL,
                subject_key=referential.slug,
            )

    def test_refuse_une_seconde_demande_en_attente(self, tenant, tenant_owner, non_attribue):
        services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
        )
        with pytest.raises(services.DuplicateRequestError):
            services.create_request(
                tenant=tenant,
                user=tenant_owner,
                subject_type=subjects.REFERENTIAL,
                subject_key=non_attribue.slug,
            )

    def test_redemander_apres_un_refus_est_possible(self, tenant, tenant_owner, non_attribue):
        """Un refus n'est pas définitif : la situation du client change."""
        demande = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
        )
        services.handle_request(demande, granted=False, response="Pas dans votre offre.")

        seconde = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
        )
        assert seconde.is_pending


class TestTraiterUneDemande:
    def test_accorder_attribue_le_referentiel(
        self, tenant, tenant_owner, admin_plateforme, non_attribue
    ):
        demande = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
        )

        demande, attribue = services.handle_request(
            demande, granted=True, response="C'est fait.", actor=admin_plateforme
        )

        assert attribue is True
        assert demande.status == AccessRequest.Status.GRANTED
        assert assessments_services.is_granted(tenant, non_attribue) is True

    def test_refuser_n_attribue_rien_mais_repond(
        self, tenant, tenant_owner, admin_plateforme, non_attribue
    ):
        demande = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
        )

        demande, attribue = services.handle_request(
            demande, granted=False, response="Contactez votre conseiller.", actor=admin_plateforme
        )

        assert attribue is False
        assert demande.response == "Contactez votre conseiller."
        assert assessments_services.is_granted(tenant, non_attribue) is False

    def test_un_sujet_sans_attribution_automatique_le_dit(
        self, tenant, tenant_owner, admin_plateforme
    ):
        """Accorder une FONCTIONNALITÉ ne change pas l'offre toute seule : la
        console doit dire qu'il reste un geste à faire."""
        from apps.billing import entitlements

        # L'offre d'essai du client comprend l'assistant : on l'en retire pour
        # qu'il y ait quelque chose à demander.
        abonnement = entitlements.get_subscription(tenant)
        abonnement.override_features = [
            cle for cle in abonnement.effective_features if cle != "assistant"
        ]
        abonnement.save(update_fields=["override_features"])

        demande = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.FEATURE,
            subject_key="assistant",
        )

        _, attribue = services.handle_request(demande, granted=True, actor=admin_plateforme)
        assert attribue is False

    def test_une_demande_deja_traitee_ne_se_retraite_pas(
        self, tenant, tenant_owner, admin_plateforme, non_attribue
    ):
        demande = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
        )
        services.handle_request(demande, granted=False, actor=admin_plateforme)

        with pytest.raises(services.AlreadyHandledError):
            services.handle_request(demande, granted=True, actor=admin_plateforme)

    def test_le_client_peut_retirer_sa_demande(self, tenant, tenant_owner, non_attribue):
        demande = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
        )
        services.cancel_request(demande, user=tenant_owner)
        assert demande.status == AccessRequest.Status.CANCELLED


class TestApiClient:
    def test_depose_une_demande_depuis_son_espace(
        self, api_client, tenant, tenant_owner, non_attribue
    ):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("access-request-list"),
            {
                "subject_type": "referential",
                "subject_key": non_attribue.slug,
                "reason": "Exigé par un client grand compte.",
            },
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["subject_label"] == non_attribue.name
        assert response.data["status"] == "pending"

    def test_demander_ce_qu_on_a_deja_repond_409(
        self, api_client, tenant, tenant_owner, referential
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.post(
            reverse("access-request-list"),
            {"subject_type": "referential", "subject_key": referential.slug},
            format="json",
            **headers,
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_un_client_ne_voit_que_ses_demandes(
        self, api_client, tenant, tenant_owner, tenant_factory, user_factory, non_attribue
    ):
        voisin_owner = user_factory(email="voisin@example.com")
        voisin = tenant_factory(voisin_owner, name="Voisin")
        assessments_services.revoke_referential(tenant=voisin, referential=non_attribue)
        services.create_request(
            tenant=voisin,
            user=voisin_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
            reason="Chez le voisin.",
        )

        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("access-request-list"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == []


class TestApiConsole:
    def test_la_file_montre_le_client_qui_demande(
        self, api_client, tenant, tenant_owner, admin_plateforme, non_attribue
    ):
        services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
            reason="Notre assureur le demande.",
        )
        headers = _auth(api_client, admin_plateforme)

        response = api_client.get(reverse("console-access-request-list"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pending_count"] == 1
        ligne = response.data["results"][0]
        assert ligne["tenant_name"] == tenant.name
        assert ligne["requested_by_email"] == tenant_owner.email
        assert ligne["reason"] == "Notre assureur le demande."

    def test_accorder_depuis_la_console_attribue_et_journalise(
        self, api_client, tenant, tenant_owner, admin_plateforme, non_attribue
    ):
        demande = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
        )
        headers = _auth(api_client, admin_plateforme)

        response = api_client.post(
            reverse("console-access-request-detail", args=[demande.id]),
            {"granted": True, "response": "Attribué, bonne évaluation."},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["granted_automatically"] is True
        assert assessments_services.is_granted(tenant, non_attribue) is True
        assert AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.ACCESS_REQUEST_HANDLED, tenant=tenant
        ).exists()

    def test_un_client_n_atteint_pas_la_console(
        self, api_client, tenant, tenant_owner, non_attribue
    ):
        headers = _auth(api_client, tenant_owner, tenant)
        response = api_client.get(reverse("console-access-request-list"), **headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_un_administrateur_commercial_lit_mais_ne_repond_pas(
        self, api_client, tenant, tenant_owner, user_factory, non_attribue
    ):
        commercial = user_factory(email="commercial@example.com", is_staff=True)
        PlatformAdminProfile.objects.create(
            user=commercial, level=PlatformAdminProfile.Level.COMMERCIAL
        )
        demande = services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
        )
        headers = _auth(api_client, commercial)

        lecture = api_client.get(reverse("console-access-request-list"), **headers)
        reponse = api_client.post(
            reverse("console-access-request-detail", args=[demande.id]),
            {"granted": True},
            format="json",
            **headers,
        )

        assert lecture.status_code == status.HTTP_200_OK
        assert reponse.status_code == status.HTTP_403_FORBIDDEN


class TestConsoleAttributionDirecte:
    def test_attribuer_puis_retirer_un_referentiel_depuis_la_console(
        self, api_client, tenant, admin_plateforme, second_referential
    ):
        assessments_services.revoke_referential(tenant=tenant, referential=second_referential)
        headers = _auth(api_client, admin_plateforme)
        url = reverse("platform-client-referentials", args=[tenant.id])

        attribution = api_client.post(
            url, {"referential": second_referential.slug}, format="json", **headers
        )
        assert attribution.status_code == status.HTTP_200_OK
        assert assessments_services.is_granted(tenant, second_referential) is True

        retrait = api_client.delete(
            url, {"referential": second_referential.slug}, format="json", **headers
        )
        assert retrait.status_code == status.HTTP_200_OK
        assert retrait.data["kept_readable"] is True
        assert assessments_services.is_granted(tenant, second_referential) is False

    def test_le_catalogue_de_la_console_dit_les_droits(
        self, api_client, admin_plateforme, referential, second_referential
    ):
        headers = _auth(api_client, admin_plateforme)
        response = api_client.get(reverse("platform-referential-list"), **headers)

        par_slug = {ligne["slug"]: ligne for ligne in response.data}
        assert par_slug[second_referential.slug]["kind"] == "licensed"
        assert par_slug[second_referential.slug]["licence_notice"]
