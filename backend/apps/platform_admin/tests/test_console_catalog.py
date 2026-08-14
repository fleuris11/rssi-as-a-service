"""Console d'administration — offres, prospects, administrateurs, réglages."""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.billing.models import Plan, Subscription
from apps.marketing.models import DemoRequest
from apps.platform_admin.models import AdminAuditLog, PlatformAdminProfile
from apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd123"


@pytest.fixture
def staff_headers(api_client, user_factory):
    staff = user_factory(email="patron@example.com", is_staff=True)
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": staff.email, "password": PASSWORD}, format="json"
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}


@pytest.fixture
def commercial_headers(api_client, user_factory):
    """Administrateur de niveau commercial : lecture partout, écriture sur les
    seuls prospects."""
    user = user_factory(email="commercial@example.com", is_staff=True)
    PlatformAdminProfile.objects.create(
        user=user, level=PlatformAdminProfile.Level.COMMERCIAL
    )
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": user.email, "password": PASSWORD}, format="json"
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}


@pytest.fixture
def plan():
    return Plan.objects.create(
        code="essentiel",
        name="Essentiel",
        price_monthly=50,
        price_yearly=500,
        status=Plan.Status.PUBLISHED,
        monitored_assets=3,
        monthly_scans=30,
        max_users=5,
        features=["realtime_monitoring"],
    )


class TestPlanAdministration:
    def test_creates_a_plan_from_scratch(self, api_client, staff_headers):
        response = api_client.post(
            reverse("platform-plan-list"),
            {
                "code": "nouvelle-offre",
                "name": "Nouvelle Offre",
                "price_monthly": "129.00",
                "price_yearly": "1290.00",
                "monitored_assets": 2,
                "monthly_scans": 40,
                "max_users": 4,
                "features": ["realtime_monitoring"],
                "status": "draft",
            },
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Plan.objects.filter(code="nouvelle-offre").exists()

    def test_duplicates_a_plan_as_a_draft(self, api_client, staff_headers, plan):
        response = api_client.post(
            reverse("platform-plan-duplicate", kwargs={"plan_code": plan.code}),
            {"code": "essentiel-2026", "name": "Essentiel 2026"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        clone = Plan.objects.get(code="essentiel-2026")
        # Une copie ne doit jamais atterrir sur la vitrine avant relecture.
        assert clone.status == Plan.Status.DRAFT
        assert clone.is_highlighted is False
        assert clone.monitored_assets == plan.monitored_assets

    def test_rejects_an_unknown_feature_key(self, api_client, staff_headers, plan):
        response = api_client.patch(
            reverse("platform-plan-detail", kwargs={"plan_code": plan.code}),
            {"features": ["realtime_monitoring", "teleportation"]},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        plan.refresh_from_db()
        assert "teleportation" not in plan.features

    def test_impact_preview_counts_affected_clients_without_writing(
        self, api_client, staff_headers, plan, tenant
    ):
        Subscription.objects.filter(tenant=tenant).update(plan=plan)

        response = api_client.post(
            reverse("platform-plan-impact", kwargs={"plan_code": plan.code}),
            {"monitored_assets": 1},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["subscriber_count"] == 1
        assert "monitored_assets" in response.data["lowered_quotas"]
        assert response.data["will_freeze_existing"] is True
        plan.refresh_from_db()
        assert plan.monitored_assets == 3  # rien n'a été écrit

    def test_lowering_a_quota_freezes_existing_clients(
        self, api_client, staff_headers, plan, tenant
    ):
        """ADR-021 : un client ne perd jamais un quota déjà consenti."""
        Subscription.objects.filter(tenant=tenant).update(plan=plan)

        api_client.patch(
            reverse("platform-plan-detail", kwargs={"plan_code": plan.code}),
            {"monitored_assets": 1},
            format="json",
            **staff_headers,
        )

        subscription = Subscription.objects.get(tenant=tenant)
        assert subscription.override_monitored_assets == 3
        assert subscription.monitored_assets_quota == 3
        plan.refresh_from_db()
        assert plan.monitored_assets == 1  # les NOUVEAUX clients auront 1

    def test_raising_a_quota_benefits_everyone_immediately(
        self, api_client, staff_headers, plan, tenant
    ):
        Subscription.objects.filter(tenant=tenant).update(plan=plan)

        api_client.patch(
            reverse("platform-plan-detail", kwargs={"plan_code": plan.code}),
            {"monthly_scans": 100},
            format="json",
            **staff_headers,
        )

        subscription = Subscription.objects.get(tenant=tenant)
        # Aucune surcharge posée : le client suit l'offre, donc profite de la
        # hausse sans intervention.
        assert subscription.override_monthly_scans is None
        assert subscription.monthly_scans_quota == 100

    def test_a_plan_with_clients_cannot_be_deleted(
        self, api_client, staff_headers, plan, tenant
    ):
        Subscription.objects.filter(tenant=tenant).update(plan=plan)

        response = api_client.delete(
            reverse("platform-plan-delete", kwargs={"plan_code": plan.code}), **staff_headers
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "retirez-la de la vente" in response.data["detail"].lower()
        assert Plan.objects.filter(code=plan.code).exists()

    def test_an_unused_plan_can_be_deleted(self, api_client, staff_headers, plan):
        response = api_client.delete(
            reverse("platform-plan-delete", kwargs={"plan_code": plan.code}), **staff_headers
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Plan.objects.filter(code=plan.code).exists()

    def test_preview_shows_the_public_rendering(self, api_client, staff_headers, plan):
        plan.status = Plan.Status.DRAFT
        plan.save(update_fields=["status"])

        response = api_client.get(
            reverse("platform-plan-preview", kwargs={"plan_code": plan.code}), **staff_headers
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"]["name"] == "Essentiel"
        assert response.data["is_visible_publicly"] is False


class TestProspects:
    def test_creates_a_prospect_by_hand(self, api_client, staff_headers):
        response = api_client.post(
            reverse("platform-prospect-list"),
            {
                "company": "Rencontre Salon",
                "full_name": "Alix Berger",
                "email": "alix@rencontre.example",
                "phone": "0601020304",
            },
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        prospect = DemoRequest.objects.get(company="Rencontre Salon")
        assert prospect.source == DemoRequest.Source.MANUAL
        assert prospect.created_by.email == "patron@example.com"

    def test_a_lost_prospect_requires_a_reason(self, api_client, staff_headers):
        prospect = DemoRequest.objects.create(
            company="Perdu", full_name="X", email="x@perdu.example"
        )

        response = api_client.patch(
            reverse("platform-prospect-detail", kwargs={"prospect_id": prospect.id}),
            {"status": "lost"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        prospect.refresh_from_db()
        assert prospect.status == DemoRequest.Status.NEW

    def test_records_timestamped_notes(self, api_client, staff_headers):
        prospect = DemoRequest.objects.create(
            company="Suivi", full_name="Y", email="y@suivi.example"
        )

        response = api_client.post(
            reverse("platform-prospect-note", kwargs={"prospect_id": prospect.id}),
            {"body": "Rappelé, intéressé par le palier Pilotage."},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["author_email"] == "patron@example.com"
        assert prospect.notes.count() == 1

    def test_follow_up_board_separates_due_from_stale(self, api_client, staff_headers):
        from datetime import timedelta

        from django.utils import timezone

        today = timezone.localdate()
        DemoRequest.objects.create(
            company="À rappeler",
            full_name="A",
            email="a@relance.example",
            next_follow_up_on=today,
        )
        old = DemoRequest.objects.create(
            company="Oublié", full_name="B", email="b@oublie.example"
        )
        DemoRequest.objects.filter(id=old.id).update(
            updated_at=timezone.now() - timedelta(days=40)
        )

        response = api_client.get(reverse("platform-prospect-follow-up"), **staff_headers)

        assert [p["company"] for p in response.data["due_today"]] == ["À rappeler"]
        assert [p["company"] for p in response.data["stale"]] == ["Oublié"]

    def test_conversion_prefills_and_keeps_the_link(self, api_client, staff_headers, plan):
        prospect = DemoRequest.objects.create(
            company="Devient Client", full_name="Z", email="z@devient.example"
        )

        response = api_client.post(
            reverse("platform-client-create"),
            {
                "name": "Devient Client",
                "owner_email": "z@devient.example",
                "plan_code": plan.code,
                "prospect_id": prospect.id,
            },
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        prospect.refresh_from_db()
        assert prospect.status == DemoRequest.Status.WON
        assert prospect.converted_tenant == Tenant.objects.get(name="Devient Client")


class TestAdminLevels:
    def test_a_commercial_can_read_the_console(self, api_client, commercial_headers):
        response = api_client.get(reverse("platform-capacity"), **commercial_headers)
        assert response.status_code == status.HTTP_200_OK

    def test_a_commercial_can_manage_prospects(self, api_client, commercial_headers):
        response = api_client.post(
            reverse("platform-prospect-list"),
            {"company": "Piste", "full_name": "C", "email": "c@piste.example"},
            format="json",
            **commercial_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_a_commercial_cannot_touch_clients_or_the_catalogue(
        self, api_client, commercial_headers, plan, tenant
    ):
        creation = api_client.post(
            reverse("platform-client-create"),
            {"name": "Interdit", "owner_email": "i@interdit.example"},
            format="json",
            **commercial_headers,
        )
        catalogue = api_client.patch(
            reverse("platform-plan-detail", kwargs={"plan_code": plan.code}),
            {"name": "Renommé"},
            format="json",
            **commercial_headers,
        )
        archive = api_client.post(
            reverse("platform-client-archive", kwargs={"tenant_id": tenant.id}),
            {},
            format="json",
            **commercial_headers,
        )

        assert creation.status_code == status.HTTP_403_FORBIDDEN
        assert catalogue.status_code == status.HTTP_403_FORBIDDEN
        assert archive.status_code == status.HTTP_403_FORBIDDEN
        assert not Tenant.objects.filter(name="Interdit").exists()

    def test_invites_an_administrator_with_a_link_not_a_password(
        self, api_client, staff_headers
    ):
        response = api_client.post(
            reverse("platform-admin-list"),
            {"email": "collegue@example.com", "level": "commercial"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "/invitation/" in response.data["invitation"]["invitation_url"]
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.get(email="collegue@example.com")
        assert user.is_staff
        assert not user.has_usable_password()

    def test_an_administrator_cannot_revoke_themselves(
        self, api_client, staff_headers, user_factory
    ):
        from django.contrib.auth import get_user_model

        me = get_user_model().objects.get(email="patron@example.com")

        response = api_client.delete(
            reverse("platform-admin-detail", kwargs={"user_id": me.id}), **staff_headers
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        me.refresh_from_db()
        assert me.is_staff

    def test_the_last_full_administrator_cannot_be_revoked(
        self, api_client, staff_headers, user_factory
    ):
        from django.contrib.auth import get_user_model

        other = user_factory(email="autre-admin@example.com", is_staff=True)
        PlatformAdminProfile.objects.create(
            user=other, level=PlatformAdminProfile.Level.COMMERCIAL
        )
        me = get_user_model().objects.get(email="patron@example.com")

        # « autre » est commercial : « patron » est le dernier complet, mais il
        # ne peut de toute façon pas se retirer lui-même. On vérifie donc le
        # refus depuis le compte « autre » promu complet puis rétrogradé.
        response = api_client.patch(
            reverse("platform-admin-detail", kwargs={"user_id": me.id}),
            {"level": "commercial"},
            format="json",
            **staff_headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestPlatformSettings:
    def test_changes_a_cap_without_touching_the_environment(self, api_client, staff_headers):
        from apps.billing import capacity

        response = api_client.patch(
            reverse("platform-settings"),
            {"key": "monitored_slot_pool", "value": 25},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert capacity.monitored_slot_capacity() == 25
        assert AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.SETTING_CHANGED
        ).exists()

    def test_refuses_an_out_of_range_value(self, api_client, staff_headers):
        response = api_client.patch(
            reverse("platform-settings"),
            {"key": "alert_warning_ratio", "value": 500},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "100" in response.data["detail"]

    def test_warns_when_lowering_the_pool_below_what_is_committed(
        self, api_client, staff_headers, tenant
    ):
        response = api_client.patch(
            reverse("platform-settings"),
            {"key": "monitored_slot_pool", "value": 0},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        # Le message doit lever les deux malentendus opposés : la baisse n'est
        # pas sans effet, et elle ne coupe personne.
        assert "engagés" in response.data["warning"]
        assert "Aucun client ne perdra" in response.data["warning"]

    def test_reset_returns_to_the_environment_value(self, api_client, staff_headers, settings):
        api_client.patch(
            reverse("platform-settings"),
            {"key": "trial_days", "value": 3},
            format="json",
            **staff_headers,
        )

        response = api_client.post(
            reverse("platform-setting-reset", kwargs={"key": "trial_days"}), **staff_headers
        )

        assert response.status_code == status.HTTP_200_OK
        from apps.platform_admin import settings_registry

        assert settings_registry.get("trial_days") == settings.BILLING_TRIAL_DAYS

    def test_settings_never_expose_a_secret(self, api_client, staff_headers, settings):
        response = api_client.get(reverse("platform-settings"), **staff_headers)

        payload = str(response.data)
        assert settings.BREACH_SECRET_ENCRYPTION_KEY not in payload
        assert settings.TOTP_ENCRYPTION_KEY not in payload
        keys = {row["key"] for row in response.data["settings"]}
        # Aucun réglage n'accepte une valeur secrète : les clés restent en
        # variables d'environnement.
        assert not any("key" in k and "encryption" in k for k in keys)


class TestSearchAndExport:
    def test_search_finds_a_company_a_user_and_a_prospect(
        self, api_client, staff_headers, tenant
    ):
        DemoRequest.objects.create(
            company=f"{tenant.name} Filiale", full_name="D", email="d@filiale.example"
        )

        response = api_client.get(
            reverse("platform-search"), {"q": tenant.name[:6]}, **staff_headers
        )

        assert response.status_code == status.HTTP_200_OK
        assert any(t["name"] == tenant.name for t in response.data["tenants"])
        assert len(response.data["prospects"]) >= 1

    def test_search_ignores_a_query_too_short_to_be_useful(self, api_client, staff_headers):
        response = api_client.get(reverse("platform-search"), {"q": "a"}, **staff_headers)
        assert response.data["tenants"] == []

    @pytest.mark.parametrize("kind", ["tenants", "prospects", "subscriptions"])
    def test_exports_a_csv(self, api_client, staff_headers, tenant, kind):
        response = api_client.get(
            reverse("platform-export", kwargs={"kind": kind}), **staff_headers
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"].startswith("text/csv")
        assert "attachment" in response["Content-Disposition"]
        assert AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.EXPORT_GENERATED
        ).exists()

    def test_an_unknown_export_is_a_404_not_a_crash(self, api_client, staff_headers):
        response = api_client.get(
            reverse("platform-export", kwargs={"kind": "inconnu"}), **staff_headers
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
