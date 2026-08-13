"""Application effective des droits par offre.

Ce qui compte ici n'est pas qu'une garde existe, mais qu'elle soit
**infranchissable par appel direct à l'API** : un client curieux qui appelle
l'endpoint sans passer par l'interface ne doit pas obtenir une fonctionnalité
hors de son offre. Le frontend affiche ces fonctionnalités désactivées, ce qui
en révèle l'existence — d'autant plus de raisons de tenir côté serveur.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.billing import entitlements, features
from apps.billing.models import Plan, Subscription
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd123"


@pytest.fixture
def basic_plan(db):
    return Plan.objects.create(
        code="basique",
        name="Basique",
        monitored_assets=1,
        monthly_scans=2,
        max_users=3,
        status=Plan.Status.PUBLISHED,
        price_monthly=50,
        features=[features.REALTIME_MONITORING],
    )


@pytest.fixture
def full_plan(db):
    return Plan.objects.create(
        code="complet",
        name="Complet",
        monitored_assets=5,
        monthly_scans=100,
        max_users=50,
        status=Plan.Status.PUBLISHED,
        price_monthly=200,
        features=features.all_keys(),
    )


def _set_plan(tenant, plan, *, status_value=Subscription.Status.ACTIVE):
    Subscription.objects.filter(tenant=tenant).update(plan=plan, status=status_value)
    return Subscription.objects.get(tenant=tenant)


def _auth(api_client, user, tenant):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": user.email, "password": PASSWORD}, format="json"
    )
    return {
        "HTTP_AUTHORIZATION": f"Bearer {response.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


class TestFeatureRegistry:
    def test_an_unknown_feature_in_the_database_is_ignored_not_fatal(self, basic_plan):
        """Un plan mal saisi ne doit pas faire tomber l'application pour tous
        les clients qui y sont abonnés."""
        basic_plan.features = ["realtime_monitoring", "fonctionnalite-inventee"]
        basic_plan.save()

        assert basic_plan.enabled_features == ["realtime_monitoring"]
        assert basic_plan.has_feature("realtime_monitoring") is True
        assert basic_plan.has_feature("fonctionnalite-inventee") is False

    def test_writing_an_unknown_feature_is_rejected(self):
        """À la saisie en revanche, on prévient l'exploitant de sa faute de
        frappe — les deux comportements sont voulus et complémentaires."""
        from apps.platform_admin.serializers import PlanWriteSerializer

        serializer = PlanWriteSerializer(
            data={"code": "x", "name": "X", "features": ["nimporte-quoi"]}
        )
        assert not serializer.is_valid()
        assert "features" in serializer.errors


class TestFeatureGating:
    def test_a_feature_outside_the_plan_is_refused(self, tenant, basic_plan):
        _set_plan(tenant, basic_plan)

        with pytest.raises(entitlements.EntitlementError) as exc_info:
            entitlements.ensure_feature(tenant, features.SECRET_REVEAL)

        assert exc_info.value.reason == "feature"

    def test_the_refusal_names_the_plan_that_includes_it(self, tenant, basic_plan, full_plan):
        """Un refus qui ne dit pas comment l'obtenir n'aide ni le client ni la
        vente."""
        _set_plan(tenant, basic_plan)

        with pytest.raises(entitlements.EntitlementError) as exc_info:
            entitlements.ensure_feature(tenant, features.SECRET_REVEAL)

        assert "Complet" in exc_info.value.message
        assert exc_info.value.required_plan == "Complet"

    def test_a_feature_inside_the_plan_passes(self, tenant, full_plan):
        _set_plan(tenant, full_plan)
        entitlements.ensure_feature(tenant, features.SECRET_REVEAL)  # ne doit pas lever

    def test_an_override_can_grant_a_feature_outside_the_plan(self, tenant, basic_plan):
        """Offre « Souverain » : quotas et fonctionnalités négociés sans créer
        un plan fantôme par client."""
        subscription = _set_plan(tenant, basic_plan)
        subscription.override_features = [features.SECRET_REVEAL]
        subscription.save()

        assert entitlements.has_feature(tenant, features.SECRET_REVEAL) is True


class TestQuotas:
    def test_the_scan_quota_is_enforced(self, tenant, basic_plan, website_asset):
        from apps.threat_intelligence.models import BreachIntelligenceUsage

        _set_plan(tenant, basic_plan)  # 2 analyses/mois
        for _ in range(2):
            BreachIntelligenceUsage.all_objects.create(
                tenant=tenant, requests_consumed=1, triggered_by="manual"
            )

        with pytest.raises(entitlements.EntitlementError) as exc_info:
            entitlements.ensure_scan_quota(tenant)
        assert exc_info.value.reason == "quota"
        assert "2" in exc_info.value.message

    def test_a_zero_quota_means_unlimited(self, tenant, basic_plan):
        subscription = _set_plan(tenant, basic_plan)
        subscription.override_monthly_scans = 0
        subscription.save()

        entitlements.ensure_scan_quota(tenant)  # ne doit pas lever

    def test_the_monitored_asset_quota_is_enforced(self, tenant, basic_plan, website_asset):
        from apps.threat_intelligence.models import MonitoredAsset

        _set_plan(tenant, basic_plan)  # 1 actif
        MonitoredAsset.all_objects.create(tenant=tenant, asset=website_asset, provider_ref="ref-1")

        with pytest.raises(entitlements.EntitlementError):
            entitlements.ensure_monitored_asset_quota(tenant)


class TestSuspendedSubscriptionKeepsReadAccess:
    """« On ne prend jamais en otage les données d'un client » : un abonnement
    suspendu bloque ce qui consomme une ressource, jamais la lecture."""

    def test_consuming_actions_are_blocked(self, tenant, full_plan):
        _set_plan(tenant, full_plan, status_value=Subscription.Status.SUSPENDED)

        with pytest.raises(entitlements.EntitlementError) as exc_info:
            entitlements.ensure_operational(tenant)
        assert exc_info.value.reason == "not_operational"
        assert "consultables" in exc_info.value.message

    def test_reading_findings_still_works(
        self, api_client, tenant, tenant_owner, website_asset, full_plan
    ):
        from apps.threat_intelligence import services as ti_services

        ti_services.ingest_raw_findings(
            tenant=tenant,
            asset=website_asset,
            raw_findings=[RawFinding(endpoint="creds", payload={"eml": "a@b.c", "pwd": "x"})],
        )
        _set_plan(tenant, full_plan, status_value=Subscription.Status.SUSPENDED)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-finding-list"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_the_exposure_feed_still_works(
        self, api_client, tenant, tenant_owner, website_asset, full_plan
    ):
        _set_plan(tenant, full_plan, status_value=Subscription.Status.SUSPENDED)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-exposure-feed"), **headers)

        assert response.status_code == status.HTTP_200_OK


class TestApiCannotBeBypassed:
    """Étanchéité : appeler l'API directement ne contourne rien."""

    def test_scan_is_refused_without_an_operational_subscription(
        self, api_client, tenant, tenant_owner, website_asset, basic_plan
    ):
        _set_plan(tenant, basic_plan, status_value=Subscription.Status.SUSPENDED)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(reverse("breach-scan-trigger"), {}, format="json", **headers)

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED

    def test_scan_is_refused_when_the_client_quota_is_exhausted(
        self, api_client, tenant, tenant_owner, website_asset, basic_plan
    ):
        from apps.threat_intelligence.models import BreachIntelligenceUsage

        _set_plan(tenant, basic_plan)
        for _ in range(2):
            BreachIntelligenceUsage.all_objects.create(
                tenant=tenant, requests_consumed=1, triggered_by="manual"
            )
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(reverse("breach-scan-trigger"), {}, format="json", **headers)

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED

    def test_reveal_is_refused_outside_the_plan(
        self, api_client, tenant, tenant_owner, website_asset, basic_plan
    ):
        from apps.threat_intelligence import services as ti_services

        finding = ti_services.ingest_raw_findings(
            tenant=tenant,
            asset=website_asset,
            raw_findings=[RawFinding(endpoint="creds", payload={"eml": "a@b.c", "pwd": "secret"})],
        )[0]
        _set_plan(tenant, basic_plan)  # sans secret_reveal
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": PASSWORD},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
        assert "offre" in response.data["detail"].lower()

    def test_the_refused_reveal_is_audited(
        self, api_client, tenant, tenant_owner, website_asset, basic_plan
    ):
        from apps.threat_intelligence import services as ti_services
        from apps.threat_intelligence.models import SecretRevealAudit

        finding = ti_services.ingest_raw_findings(
            tenant=tenant,
            asset=website_asset,
            raw_findings=[RawFinding(endpoint="creds", payload={"eml": "a@b.c", "pwd": "s"})],
        )[0]
        _set_plan(tenant, basic_plan)
        headers = _auth(api_client, tenant_owner, tenant)

        api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": PASSWORD},
            format="json",
            **headers,
        )

        assert SecretRevealAudit.all_objects.filter(tenant=tenant, success=False).exists()

    def test_realtime_monitoring_is_refused_outside_the_plan(
        self, api_client, tenant, tenant_owner, website_asset, settings
    ):
        settings.BREACHSENSE_WEBHOOK_CALLBACK_URL = "https://example.test/webhook"
        plan = Plan.objects.create(
            code="sans-temps-reel",
            name="Sans temps réel",
            monitored_assets=1,
            status=Plan.Status.PUBLISHED,
            features=[],
        )
        _set_plan(tenant, plan)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("monitored-asset-list"),
            {"asset_id": website_asset.id},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED


class TestEntitlementsEndpoint:
    def test_it_lists_included_and_excluded_features(
        self, api_client, tenant, tenant_owner, basic_plan, full_plan
    ):
        """Le frontend a besoin de la liste COMPLÈTE pour afficher les
        fonctionnalités hors offre en désactivé plutôt que masquées."""
        _set_plan(tenant, basic_plan)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("tenant-entitlements"), **headers)

        assert response.status_code == status.HTTP_200_OK
        by_key = {f["key"]: f for f in response.data["features"]}
        assert len(by_key) == len(features.all_keys())
        assert by_key[features.REALTIME_MONITORING]["included"] is True
        assert by_key[features.SECRET_REVEAL]["included"] is False
        assert by_key[features.SECRET_REVEAL]["required_plan"] == "Complet"
        assert by_key[features.SECRET_REVEAL]["teaser"]

    def test_it_reports_quota_consumption(self, api_client, tenant, tenant_owner, basic_plan):
        _set_plan(tenant, basic_plan)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("tenant-entitlements"), **headers)

        assert response.data["quotas"]["monthly_scans"]["quota"] == 2
        assert response.data["subscription"]["plan_name"] == "Basique"

    def test_another_tenants_entitlements_are_not_reachable(
        self, api_client, user_factory, tenant_factory, basic_plan, full_plan
    ):
        owner_a = user_factory(email="a@example.com")
        tenant_a = tenant_factory(owner_a, name="A")
        owner_b = user_factory(email="b@example.com")
        tenant_b = tenant_factory(owner_b, name="B")
        _set_plan(tenant_a, basic_plan)
        _set_plan(tenant_b, full_plan)

        # A demande explicitement le contexte de B : le middleware refuse,
        # l'adhésion n'existant pas.
        response_a = api_client.post(
            reverse("token-obtain-pair"),
            {"email": owner_a.email, "password": PASSWORD},
            format="json",
        )
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {response_a.data['access']}",
            "HTTP_X_TENANT_ID": str(tenant_b.id),
        }

        response = api_client.get(reverse("tenant-entitlements"), **headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestPublicPlanCatalogue:
    def test_only_published_plans_are_public(self, basic_plan, api_client):
        Plan.objects.create(code="brouillon", name="Brouillon", status=Plan.Status.DRAFT)

        response = api_client.get(reverse("public-plan-list"))

        codes = [plan["code"] for plan in response.data["plans"]]
        assert "basique" in codes
        assert "brouillon" not in codes

    def test_the_catalogue_needs_no_authentication(self, api_client, basic_plan):
        response = api_client.get(reverse("public-plan-list"))
        assert response.status_code == status.HTTP_200_OK
