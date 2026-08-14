"""Back-office plateforme.

Deux exigences structurantes vérifiées ici :
- l'administration gère des **abonnements et des quotas**, elle ne consulte
  jamais les fuites d'un client (ADR-014 : un administrateur plateforme
  n'accède aux données d'un tenant que s'il en est membre) ;
- **les administrateurs plateforme ne sont pas au-dessus de l'audit** : toute
  action sensible laisse une trace nominative.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.billing.models import Plan, Subscription
from apps.platform_admin.models import AdminAuditLog

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd123"


@pytest.fixture
def staff_headers(api_client, user_factory):
    staff = user_factory(email="staff@example.com", is_staff=True)
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": staff.email, "password": PASSWORD}, format="json"
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}


@pytest.fixture
def client_headers(api_client, tenant_owner, tenant):
    response = api_client.post(
        reverse("token-obtain-pair"),
        {"email": tenant_owner.email, "password": PASSWORD},
        format="json",
    )
    return {
        "HTTP_AUTHORIZATION": f"Bearer {response.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


ADMIN_ENDPOINTS = [
    ("platform-capacity", {}),
    ("platform-tenant-list", {}),
    ("platform-plan-list", {}),
    ("platform-health", {}),
    ("platform-configuration", {}),
    ("platform-audit", {}),
]


class TestAccessControl:
    @pytest.mark.parametrize("route,kwargs", ADMIN_ENDPOINTS)
    def test_anonymous_is_refused(self, api_client, route, kwargs):
        response = api_client.get(reverse(route, kwargs=kwargs))
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @pytest.mark.parametrize("route,kwargs", ADMIN_ENDPOINTS)
    def test_a_tenant_admin_is_refused(self, api_client, client_headers, route, kwargs):
        """Être administrateur de SON entreprise ne donne aucun droit sur la
        plateforme : ce sont deux espaces distincts, pas deux niveaux."""
        response = api_client.get(reverse(route, kwargs=kwargs), **client_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("route,kwargs", ADMIN_ENDPOINTS)
    def test_platform_staff_is_allowed(self, api_client, staff_headers, route, kwargs):
        response = api_client.get(reverse(route, kwargs=kwargs), **staff_headers)
        assert response.status_code == status.HTTP_200_OK


class TestCapacityView:
    def test_it_reports_both_scarce_resources(self, api_client, staff_headers):
        response = api_client.get(reverse("platform-capacity"), **staff_headers)

        resources = {r["resource"] for r in response.data["resources"]}
        assert resources == {"monitored_slots", "monthly_scans"}

    def test_it_projects_the_effect_of_each_plan(self, api_client, staff_headers, settings):
        """« Si vous activez ce client, il restera X » — sans cette
        projection, l'exploitant fait le calcul de tête avant chaque vente."""
        settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE = 4

        response = api_client.get(reverse("platform-capacity"), **staff_headers)

        projections = {p["plan_code"]: p for p in response.data["projections"]}
        assert "pilotage" in projections
        for projection in projections.values():
            assert "would_fit" in projection
            assert "remaining_after" in projection

    def test_it_shows_which_tenant_consumes_the_resource(self, api_client, staff_headers, tenant):
        response = api_client.get(reverse("platform-capacity"), **staff_headers)

        names = [row["tenant_name"] for row in response.data["by_tenant"]]
        assert tenant.name in names


class TestTenantManagement:
    def test_the_tenant_list_shows_the_subscription(self, api_client, staff_headers, tenant):
        response = api_client.get(reverse("platform-tenant-list"), **staff_headers)

        row = next(r for r in response.data if r["name"] == tenant.name)
        assert row["subscription_status"] == "trial"
        assert row["plan_name"]

    def test_the_tenant_detail_never_exposes_breach_content(
        self, api_client, staff_headers, tenant, tenant_owner
    ):
        """L'administration voit des COMPTEURS, jamais un identifiant fuité ni
        un secret : ADR-014 réserve cet accès aux membres du tenant."""
        from apps.monitoring import services as monitoring_services
        from apps.monitoring.models import Asset
        from apps.threat_intelligence import services as ti_services
        from apps.threat_intelligence.providers.base import RawFinding

        asset = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.WEBSITE,
            value="https://exemple.test",
            ownership_confirmed=True,
        )
        ti_services.ingest_raw_findings(
            tenant=tenant,
            asset=asset,
            raw_findings=[
                RawFinding(
                    endpoint="creds",
                    payload={"eml": "victime@exemple.test", "pwd": "SecretTresPrive"},
                )
            ],
        )

        response = api_client.get(
            reverse("platform-tenant-detail", args=[tenant.id]), **staff_headers
        )

        payload = str(response.data)
        assert response.data["usage"]["findings_total"] == 1
        assert "SecretTresPrive" not in payload
        assert "victime@exemple.test" not in payload

    def test_internal_notes_can_be_recorded(self, api_client, staff_headers, tenant):
        response = api_client.patch(
            reverse("platform-tenant-detail", args=[tenant.id]),
            {"internal_notes": "Rappeler en septembre."},
            format="json",
            **staff_headers,
        )

        assert response.data["subscription"]["internal_notes"] == "Rappeler en septembre."


class TestSubscriptionActions:
    def test_a_subscription_can_be_suspended(self, api_client, staff_headers, tenant):
        response = api_client.post(
            reverse("platform-subscription-action", args=[tenant.id]),
            {"action": "suspend", "reason": "Impayé"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert Subscription.objects.get(tenant=tenant).status == "suspended"

    def test_the_plan_can_be_changed(self, api_client, staff_headers, tenant):
        response = api_client.post(
            reverse("platform-subscription-action", args=[tenant.id]),
            {"action": "change_plan", "plan_code": "veille"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert Subscription.objects.get(tenant=tenant).plan.code == "veille"

    def test_an_activation_exceeding_the_platform_cap_returns_409(
        self, api_client, staff_headers, tenant, settings, user_factory, tenant_factory
    ):
        """409 et non 400 : la demande est légitime, c'est l'état de la
        plateforme qui la rend impossible."""
        settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE = 3
        big = Plan.objects.create(
            code="enorme", name="Énorme", monitored_assets=10, status=Plan.Status.PUBLISHED
        )

        response = api_client.post(
            reverse("platform-subscription-action", args=[tenant.id]),
            {"action": "change_plan", "plan_code": big.code},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "plafond" in response.data["detail"].lower()
        assert Subscription.objects.get(tenant=tenant).plan.code != "enorme"

    def test_change_plan_requires_a_plan_code(self, api_client, staff_headers, tenant):
        response = api_client.post(
            reverse("platform-subscription-action", args=[tenant.id]),
            {"action": "change_plan"},
            format="json",
            **staff_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestPlanAdministration:
    def test_a_plan_can_be_created_without_redeployment(self, api_client, staff_headers):
        response = api_client.post(
            reverse("platform-plan-list"),
            {
                "code": "nouveau",
                "name": "Nouveau",
                "price_monthly": "199.00",
                "monitored_assets": 2,
                "monthly_scans": 40,
                "max_users": 8,
                "features": ["assistant"],
                "status": "published",
            },
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Plan.objects.filter(code="nouveau").exists()

    def test_an_unknown_feature_is_rejected_at_write_time(self, api_client, staff_headers):
        response = api_client.post(
            reverse("platform-plan-list"),
            {"code": "bancal", "name": "Bancal", "features": ["fonction-inexistante"]},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "features" in response.data

    def test_a_plan_can_be_retired(self, api_client, staff_headers):
        response = api_client.patch(
            reverse("platform-plan-detail", args=["veille"]),
            {"status": "retired"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert Plan.objects.get(code="veille").status == "retired"

    def test_a_retired_plan_leaves_the_public_catalogue(self, api_client, staff_headers):
        api_client.patch(
            reverse("platform-plan-detail", args=["veille"]),
            {"status": "retired"},
            format="json",
            **staff_headers,
        )

        public = api_client.get(reverse("public-plan-list"))
        assert "veille" not in [p["code"] for p in public.data["plans"]]


class TestAdminActionsAreAudited:
    def test_a_suspension_is_traced_with_its_actor(self, api_client, staff_headers, tenant):
        api_client.post(
            reverse("platform-subscription-action", args=[tenant.id]),
            {"action": "suspend", "reason": "Impayé"},
            format="json",
            **staff_headers,
        )

        entry = AdminAuditLog.objects.latest("created_at")
        assert entry.action == AdminAuditLog.Action.SUBSCRIPTION_SUSPENDED
        assert entry.actor.email == "staff@example.com"
        assert entry.tenant == tenant
        assert "Impayé" in entry.detail

    def test_a_plan_change_is_traced(self, api_client, staff_headers, tenant):
        api_client.post(
            reverse("platform-subscription-action", args=[tenant.id]),
            {"action": "change_plan", "plan_code": "veille"},
            format="json",
            **staff_headers,
        )

        assert AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.PLAN_CHANGED, tenant=tenant
        ).exists()

    def test_catalogue_changes_are_traced(self, api_client, staff_headers):
        api_client.patch(
            reverse("platform-plan-detail", args=["veille"]),
            {"status": "retired"},
            format="json",
            **staff_headers,
        )

        assert AdminAuditLog.objects.filter(action=AdminAuditLog.Action.PLAN_RETIRED).exists()

    def test_a_refused_action_leaves_no_audit_entry(
        self, api_client, staff_headers, tenant, settings
    ):
        """Une action refusée n'a pas eu lieu : la tracer comme faite
        induirait en erreur lors d'une reconstitution."""
        settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE = 1
        Plan.objects.create(
            code="enorme", name="Énorme", monitored_assets=10, status=Plan.Status.PUBLISHED
        )
        before = AdminAuditLog.objects.count()

        api_client.post(
            reverse("platform-subscription-action", args=[tenant.id]),
            {"action": "change_plan", "plan_code": "enorme"},
            format="json",
            **staff_headers,
        )

        assert AdminAuditLog.objects.count() == before


class TestConsolidatedAudit:
    def test_it_merges_admin_actions_and_secret_reveals(
        self, api_client, staff_headers, tenant, tenant_owner
    ):
        from apps.threat_intelligence import services as ti_services

        ti_services.record_reveal_attempt(
            tenant=tenant, finding=None, user=tenant_owner, success=True
        )
        api_client.post(
            reverse("platform-subscription-action", args=[tenant.id]),
            {"action": "suspend"},
            format="json",
            **staff_headers,
        )

        response = api_client.get(reverse("platform-audit"), **staff_headers)

        kinds = {entry["kind"] for entry in response.data["entries"]}
        assert kinds == {"admin", "reveal"}

    def test_entries_are_sorted_most_recent_first(self, api_client, staff_headers, tenant):
        api_client.post(
            reverse("platform-subscription-action", args=[tenant.id]),
            {"action": "suspend"},
            format="json",
            **staff_headers,
        )
        api_client.post(
            reverse("platform-subscription-action", args=[tenant.id]),
            {"action": "activate"},
            format="json",
            **staff_headers,
        )

        response = api_client.get(reverse("platform-audit"), **staff_headers)

        timestamps = [entry["at"] for entry in response.data["entries"]]
        assert timestamps == sorted(timestamps, reverse=True)


class TestHealthAndConfiguration:
    def test_health_reports_every_service(self, api_client, staff_headers):
        response = api_client.get(reverse("platform-health"), **staff_headers)

        names = {check["name"] for check in response.data["checks"]}
        assert {"database", "redis", "celery_worker", "celery_beat", "cti_provider"} <= names

    def test_health_survives_a_failing_probe(self, api_client, staff_headers, monkeypatch):
        """C'est précisément quand quelque chose casse qu'on ouvre cette
        page : une sonde en échec ne doit pas empêcher d'afficher les autres."""
        from apps.platform_admin import services as admin_services

        def _boom():
            raise RuntimeError("indisponible")

        monkeypatch.setattr(admin_services, "platform_volumes", _boom)
        response = api_client.get(reverse("platform-health"), **staff_headers)

        assert response.status_code == status.HTTP_200_OK
        # La section en échec est signalée comme telle, les autres restent
        # lisibles.
        checks = {check["name"]: check for check in response.data["checks"]}
        assert checks["volumes"]["healthy"] is False
        assert checks["database"]["healthy"] is True

    def test_configuration_never_exposes_a_key_value(self, api_client, staff_headers, settings):
        response = api_client.get(reverse("platform-configuration"), **staff_headers)

        payload = str(response.data)
        assert settings.BREACH_SECRET_ENCRYPTION_KEY not in payload
        assert settings.TOTP_ENCRYPTION_KEY not in payload
        for key in response.data["keys"]:
            assert set(key) <= {"name", "label", "present", "valid"}

    def test_configuration_reports_caps_and_retention(self, api_client, staff_headers):
        response = api_client.get(reverse("platform-configuration"), **staff_headers)

        assert response.data["caps"]["monitored_slots"] > 0
        assert response.data["retention"]["secret_days"] > 0
        assert response.data["cti_mode"]


class TestDemoRequestHandling:
    """Une demande reçue sur le site public doit pouvoir être suivie puis
    convertie en client — sans jamais contourner la garde de capacité."""

    @pytest.fixture
    def demo_request(self):
        from apps.marketing.models import DemoRequest

        return DemoRequest.objects.create(
            full_name="Camille Roux",
            company="Atelier Roux",
            role="Gérante",
            email="camille@atelier-roux.example",
            company_size="10-49",
            message="Nous voulons comprendre notre exposition.",
        )

    def test_listing_is_refused_to_a_client(self, api_client, client_headers, demo_request):
        response = api_client.get(reverse("platform-demo-request-list"), **client_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_listing_never_exposes_the_anti_abuse_metadata(
        self, api_client, staff_headers, demo_request
    ):
        """L'IP et l'agent utilisateur sont collectés pour la seule finalité
        anti-abus : une liste consultée pour rappeler un prospect n'en a pas
        besoin."""
        demo_request.ip_address = "203.0.113.9"
        demo_request.user_agent = "Mozilla/5.0"
        demo_request.save(update_fields=["ip_address", "user_agent"])

        response = api_client.get(reverse("platform-demo-request-list"), **staff_headers)

        payload = str(response.data)
        assert "203.0.113.9" not in payload
        assert "Mozilla/5.0" not in payload
        assert "Atelier Roux" in payload

    def test_status_change_is_recorded_and_audited(
        self, api_client, staff_headers, demo_request
    ):
        response = api_client.patch(
            reverse("platform-demo-request-detail", kwargs={"demo_request_id": demo_request.id}),
            {"status": "contacted"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        demo_request.refresh_from_db()
        assert demo_request.status == "contacted"
        assert AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.DEMO_REQUEST_UPDATED, target="Atelier Roux"
        ).exists()

    def test_unknown_status_is_refused(self, api_client, staff_headers, demo_request):
        response = api_client.patch(
            reverse("platform-demo-request-detail", kwargs={"demo_request_id": demo_request.id}),
            {"status": "gagnee"},
            format="json",
            **staff_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        demo_request.refresh_from_db()
        assert demo_request.status == "new"

    def test_conversion_creates_the_tenant_its_owner_and_a_trial(
        self, api_client, staff_headers, demo_request
    ):
        from apps.tenants.models import Tenant

        response = api_client.post(
            reverse("platform-demo-request-convert", kwargs={"demo_request_id": demo_request.id}),
            **staff_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        tenant = Tenant.objects.get(name="Atelier Roux")
        assert Subscription.objects.get(tenant=tenant).status == Subscription.Status.TRIAL
        demo_request.refresh_from_db()
        assert demo_request.status == "closed"
        assert AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.TENANT_CREATED, tenant=tenant
        ).exists()

    def test_conversion_is_refused_when_the_platform_is_full(
        self, api_client, staff_headers, demo_request, settings
    ):
        """Le refus arrive AVANT toute écriture : ni entreprise, ni essai."""
        from apps.tenants.models import Tenant

        settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE = 0

        response = api_client.post(
            reverse("platform-demo-request-convert", kwargs={"demo_request_id": demo_request.id}),
            **staff_headers,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "emplacement" in response.data["detail"]
        assert not Tenant.objects.filter(name="Atelier Roux").exists()
        demo_request.refresh_from_db()
        assert demo_request.status == "new"

    def test_conversion_flags_a_company_that_is_already_a_client(
        self, api_client, staff_headers, demo_request, tenant
    ):
        from apps.marketing.models import DemoRequest

        duplicate = DemoRequest.objects.create(
            full_name="Autre personne", company=tenant.name, email="autre@example.com"
        )

        listing = api_client.get(reverse("platform-demo-request-list"), **staff_headers)
        rows = {row["id"]: row for row in listing.data["requests"]}
        assert rows[duplicate.id]["already_client"] is True
        assert rows[demo_request.id]["already_client"] is False

        response = api_client.post(
            reverse("platform-demo-request-convert", kwargs={"demo_request_id": duplicate.id}),
            **staff_headers,
        )
        assert response.status_code == status.HTTP_409_CONFLICT
