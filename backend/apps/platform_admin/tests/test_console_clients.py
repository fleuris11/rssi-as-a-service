"""Console d'administration — cycle de vie client (phase 11).

Ce fichier existe d'abord pour une raison : **le bug de la phase 10 était le
troisième du même type sur ce dépôt** — un ``except`` trop large avalant une
erreur de capacité, et un dépassement constaté après coup. Chaque chemin de
création vérifie donc explicitement que le refus remonte ET que rien n'a été
écrit.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import AccessInvitation
from apps.billing.models import Plan, Subscription
from apps.platform_admin.models import AdminAuditLog
from apps.tenants.models import Membership, Tenant

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd123"


@pytest.fixture
def staff_headers(api_client, user_factory):
    staff = user_factory(email="console@example.com", is_staff=True)
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": staff.email, "password": PASSWORD}, format="json"
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}


@pytest.fixture
def small_pool(settings):
    """Pool volontairement étroit : les tests de refus doivent porter sur une
    limite atteignable, pas sur 15 emplacements qu'il faudrait remplir."""
    settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE = 4
    Plan.objects.update(status=Plan.Status.RETIRED)
    plan = Plan.objects.create(
        code="test-veille",
        name="Test Veille",
        price_monthly=10,
        price_yearly=100,
        status=Plan.Status.PUBLISHED,
        monitored_assets=2,
        monthly_scans=10,
        max_users=2,
        features=["realtime_monitoring"],
    )
    settings.BILLING_DEFAULT_TRIAL_PLAN_CODE = plan.code
    return plan


class TestClientCreation:
    def test_creates_company_owner_subscription_and_invitation_in_one_go(
        self, api_client, staff_headers, small_pool
    ):
        response = api_client.post(
            reverse("platform-client-create"),
            {
                "name": "Atelier Nouveau",
                "owner_email": "gerant@atelier-nouveau.example",
                "plan_code": small_pool.code,
                "sector": "Artisanat",
                "contact_phone": "0102030405",
            },
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        tenant = Tenant.objects.get(name="Atelier Nouveau")
        assert tenant.sector == "Artisanat"
        assert Subscription.objects.get(tenant=tenant).plan == small_pool
        membership = Membership.all_objects.get(tenant=tenant)
        assert membership.role == Membership.Role.ADMIN
        assert membership.user.email == "gerant@atelier-nouveau.example"
        # Un lien d'invitation, pas un mot de passe.
        assert AccessInvitation.objects.filter(user=membership.user).exists()
        assert "/invitation/" in response.data["invitation"]["invitation_url"]

    def test_never_sets_or_returns_a_password(self, api_client, staff_headers, small_pool):
        response = api_client.post(
            reverse("platform-client-create"),
            {"name": "Sans Mot De Passe", "owner_email": "contact@smdp.example"},
            format="json",
            **staff_headers,
        )

        user = Membership.all_objects.get(tenant__name="Sans Mot De Passe").user
        assert not user.has_usable_password()
        # Le compte n'est utilisable qu'une fois le lien consommé.
        assert user.is_active is False
        assert "password" not in str(response.data).lower()

    def test_engagement_active_skips_the_trial(self, api_client, staff_headers, small_pool):
        api_client.post(
            reverse("platform-client-create"),
            {
                "name": "Direct Actif",
                "owner_email": "contact@direct-actif.example",
                "engagement": "active",
            },
            format="json",
            **staff_headers,
        )

        subscription = Subscription.objects.get(tenant__name="Direct Actif")
        assert subscription.status == Subscription.Status.ACTIVE

    def test_refuses_and_writes_nothing_when_the_platform_is_full(
        self, api_client, staff_headers, small_pool
    ):
        """LE test de cette phase. Un refus de capacité doit annuler la
        transaction ENTIÈRE : ni entreprise, ni utilisateur, ni abonnement."""
        api_client.post(
            reverse("platform-client-create"),
            {"name": "Premier", "owner_email": "a@premier.example"},
            format="json",
            **staff_headers,
        )  # 2 emplacements sur 4
        api_client.post(
            reverse("platform-client-create"),
            {"name": "Second", "owner_email": "b@second.example"},
            format="json",
            **staff_headers,
        )  # 4 sur 4

        response = api_client.post(
            reverse("platform-client-create"),
            {"name": "De Trop", "owner_email": "c@detrop.example"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "emplacement" in response.data["detail"]
        assert "reste" in response.data["detail"]
        assert not Tenant.objects.filter(name="De Trop").exists()
        assert not Membership.all_objects.filter(user__email="c@detrop.example").exists()
        from django.contrib.auth import get_user_model

        assert not get_user_model().objects.filter(email="c@detrop.example").exists()

    def test_refuses_a_duplicate_company_name(self, api_client, staff_headers, small_pool):
        api_client.post(
            reverse("platform-client-create"),
            {"name": "Doublon", "owner_email": "a@doublon.example"},
            format="json",
            **staff_headers,
        )
        response = api_client.post(
            reverse("platform-client-create"),
            {"name": "doublon", "owner_email": "b@doublon.example"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert Tenant.objects.filter(name__iexact="doublon").count() == 1

    def test_creation_is_audited(self, api_client, staff_headers, small_pool):
        api_client.post(
            reverse("platform-client-create"),
            {"name": "Tracée", "owner_email": "contact@tracee.example"},
            format="json",
            **staff_headers,
        )

        entry = AdminAuditLog.objects.get(action=AdminAuditLog.Action.TENANT_CREATED)
        assert entry.target == "Tracée"
        assert entry.actor.email == "console@example.com"

    def test_a_client_cannot_create_a_client(self, api_client, tenant_owner, tenant, small_pool):
        response = api_client.post(
            reverse("token-obtain-pair"),
            {"email": tenant_owner.email, "password": PASSWORD},
            format="json",
        )
        headers = {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}

        response = api_client.post(
            reverse("platform-client-create"),
            {"name": "Pirate", "owner_email": "pirate@example.com"},
            format="json",
            **headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not Tenant.objects.filter(name="Pirate").exists()


class TestClientUpdate:
    def test_updates_the_commercial_record_and_audits_the_diff(
        self, api_client, staff_headers, tenant
    ):
        response = api_client.patch(
            reverse("platform-client-detail", kwargs={"tenant_id": tenant.id}),
            {"sector": "Santé", "account_manager": "Camille"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        tenant.refresh_from_db()
        assert tenant.sector == "Santé"
        entry = AdminAuditLog.objects.get(action=AdminAuditLog.Action.TENANT_UPDATED)
        # Le journal dit CE QUI a changé, pas seulement « modifié ».
        assert entry.changes["sector"][1] == "Santé"
        assert entry.changes["account_manager"] == ["", "Camille"]

    def test_an_update_that_changes_nothing_leaves_no_audit_trail(
        self, api_client, staff_headers, tenant
    ):
        api_client.patch(
            reverse("platform-client-detail", kwargs={"tenant_id": tenant.id}),
            {"name": tenant.name},
            format="json",
            **staff_headers,
        )

        assert not AdminAuditLog.objects.filter(action=AdminAuditLog.Action.TENANT_UPDATED).exists()


class TestArchiveAndTrash:
    def test_archiving_releases_the_platform_slots(self, api_client, staff_headers, small_pool):
        api_client.post(
            reverse("platform-client-create"),
            {"name": "À Archiver", "owner_email": "a@archiver.example"},
            format="json",
            **staff_headers,
        )
        from apps.billing import capacity

        before = capacity.projected_monitored_slots(additional=0)
        tenant = Tenant.objects.get(name="À Archiver")

        api_client.post(
            reverse("platform-client-archive", kwargs={"tenant_id": tenant.id}),
            {"reason": "Fin de collaboration"},
            format="json",
            **staff_headers,
        )

        tenant.refresh_from_db()
        assert tenant.is_archived
        # Sans résiliation, une entreprise archivée continuerait d'occuper le
        # pool partagé — c'est le piège que ce test verrouille.
        assert capacity.projected_monitored_slots(additional=0) == before - 2
        assert Subscription.objects.get(tenant=tenant).status == Subscription.Status.CANCELLED

    def test_archiving_is_reversible(self, api_client, staff_headers, tenant):
        url = reverse("platform-client-archive", kwargs={"tenant_id": tenant.id})
        api_client.post(url, {}, format="json", **staff_headers)
        api_client.post(url, {"restore": True}, format="json", **staff_headers)

        tenant.refresh_from_db()
        assert not tenant.is_archived
        assert tenant.is_active

    def test_trash_lists_archived_companies(self, api_client, staff_headers, tenant):
        api_client.post(
            reverse("platform-client-archive", kwargs={"tenant_id": tenant.id}),
            {"reason": "Test"},
            format="json",
            **staff_headers,
        )

        response = api_client.get(reverse("platform-trash"), **staff_headers)

        assert response.status_code == status.HTTP_200_OK
        names = [row["name"] for row in response.data["tenants"]]
        assert tenant.name in names

    def test_permanent_deletion_requires_archiving_first(self, api_client, staff_headers, tenant):
        response = api_client.delete(
            reverse("platform-client-detail", kwargs={"tenant_id": tenant.id}),
            {"confirm_name": tenant.name},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert Tenant.objects.filter(id=tenant.id).exists()

    def test_permanent_deletion_requires_typing_the_exact_name(
        self, api_client, staff_headers, tenant
    ):
        api_client.post(
            reverse("platform-client-archive", kwargs={"tenant_id": tenant.id}),
            {},
            format="json",
            **staff_headers,
        )

        response = api_client.delete(
            reverse("platform-client-detail", kwargs={"tenant_id": tenant.id}),
            {"confirm_name": "à peu près le bon nom"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert Tenant.objects.filter(id=tenant.id).exists()

    def test_permanent_deletion_works_once_archived_and_confirmed(
        self, api_client, staff_headers, tenant
    ):
        name = tenant.name
        api_client.post(
            reverse("platform-client-archive", kwargs={"tenant_id": tenant.id}),
            {},
            format="json",
            **staff_headers,
        )

        response = api_client.delete(
            reverse("platform-client-detail", kwargs={"tenant_id": tenant.id}),
            {"confirm_name": name},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Tenant.objects.filter(id=tenant.id).exists()
        assert AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.TENANT_DELETED, target=name
        ).exists()


class TestClientMembers:
    def test_invites_a_member_and_returns_a_link_not_a_password(
        self, api_client, staff_headers, tenant
    ):
        response = api_client.post(
            reverse("platform-client-members", kwargs={"tenant_id": tenant.id}),
            {"email": "nouveau@client.example", "role": "contributor"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "/invitation/" in response.data["invitation"]["invitation_url"]
        membership = Membership.all_objects.get(user__email="nouveau@client.example")
        assert membership.role == "contributor"
        assert not membership.user.has_usable_password()

    def test_refuses_beyond_the_plan_user_quota(self, api_client, staff_headers, tenant):
        subscription = Subscription.objects.get(tenant=tenant)
        subscription.override_max_users = 1
        subscription.save(update_fields=["override_max_users"])

        response = api_client.post(
            reverse("platform-client-members", kwargs={"tenant_id": tenant.id}),
            {"email": "detrop@client.example", "role": "reader"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
        assert not Membership.all_objects.filter(user__email="detrop@client.example").exists()

    def test_cuts_access_of_a_departing_employee(self, api_client, staff_headers, tenant):
        invite = api_client.post(
            reverse("platform-client-members", kwargs={"tenant_id": tenant.id}),
            {"email": "partant@client.example", "role": "reader"},
            format="json",
            **staff_headers,
        )
        membership_id = invite.data["id"]

        # La personne a accepté son invitation : c'est l'état d'un salarié en
        # poste, celui qu'on coupe le jour de son départ. Un compte invité mais
        # jamais activé est déjà inactif — le désactiver ne changerait rien.
        member = Membership.all_objects.get(id=membership_id)
        member.user.is_active = True
        member.user.save(update_fields=["is_active"])

        response = api_client.patch(
            reverse(
                "platform-client-member-detail",
                kwargs={"tenant_id": tenant.id, "membership_id": membership_id},
            ),
            {"is_active": False},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        membership = Membership.all_objects.get(id=membership_id)
        assert membership.user.is_active is False
        assert AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.USER_DEACTIVATED, target="partant@client.example"
        ).exists()

    def test_never_removes_the_last_administrator(self, api_client, staff_headers, tenant):
        membership = Membership.all_objects.get(tenant=tenant, role=Membership.Role.ADMIN)

        response = api_client.delete(
            reverse(
                "platform-client-member-detail",
                kwargs={"tenant_id": tenant.id, "membership_id": membership.id},
            ),
            **staff_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "dernier administrateur" in response.data["detail"]
        assert Membership.all_objects.filter(id=membership.id).exists()

    def test_never_demotes_the_last_administrator(self, api_client, staff_headers, tenant):
        membership = Membership.all_objects.get(tenant=tenant, role=Membership.Role.ADMIN)

        response = api_client.patch(
            reverse(
                "platform-client-member-detail",
                kwargs={"tenant_id": tenant.id, "membership_id": membership.id},
            ),
            {"role": "reader"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        membership.refresh_from_db()
        assert membership.role == Membership.Role.ADMIN

    def test_password_reset_emits_a_link_and_never_reveals_a_password(
        self, api_client, staff_headers, tenant
    ):
        membership = Membership.all_objects.get(tenant=tenant, role=Membership.Role.ADMIN)
        previous_hash = membership.user.password

        response = api_client.post(
            reverse(
                "platform-client-member-reset",
                kwargs={"tenant_id": tenant.id, "membership_id": membership.id},
            ),
            **staff_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert "/invitation/" in response.data["invitation_url"]
        membership.user.refresh_from_db()
        # Émettre un lien ne change PAS le mot de passe : tant que la personne
        # n'a pas cliqué, son accès actuel reste valable.
        assert membership.user.password == previous_hash
        assert AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.PASSWORD_RESET_SENT
        ).exists()
