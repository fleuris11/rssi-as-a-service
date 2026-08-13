"""Cycle de vie des abonnements.

Exigence de la phase : **aucune transition implicite**. Chaque changement
d'état laisse une trace (``SubscriptionEvent``) qui dit d'où l'on vient, où
l'on va, pourquoi et sur décision de qui.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.billing import services as billing_services
from apps.billing.models import Payment, Plan, Subscription, SubscriptionEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def plan(db):
    return Plan.objects.create(
        code="test",
        name="Test",
        monitored_assets=1,
        monthly_scans=10,
        max_users=5,
        price_monthly=Decimal("100"),
        price_yearly=Decimal("1000"),
        status=Plan.Status.PUBLISHED,
    )


class TestAutomaticTrial:
    def test_creating_a_tenant_opens_a_trial(self, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")

        subscription = Subscription.objects.get(tenant=tenant)
        assert subscription.status == Subscription.Status.TRIAL
        assert subscription.trial_ends_at is not None

    def test_the_trial_lasts_the_configured_duration(self, settings, user_factory, tenant_factory):
        settings.BILLING_TRIAL_DAYS = 21
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")

        subscription = Subscription.objects.get(tenant=tenant)
        expected = timezone.now() + timedelta(days=21)
        assert abs((subscription.trial_ends_at - expected).total_seconds()) < 60

    def test_the_trial_uses_the_configured_default_plan(
        self, settings, plan, user_factory, tenant_factory
    ):
        settings.BILLING_DEFAULT_TRIAL_PLAN_CODE = "test"
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")

        assert Subscription.objects.get(tenant=tenant).plan.code == "test"

    def test_a_tenant_is_still_created_if_the_trial_cannot_open(
        self, settings, user_factory, tenant_factory
    ):
        """La création d'entreprise prime : sans catalogue, on obtient une
        entreprise sans abonnement — état que les gardes traitent
        explicitement — plutôt qu'un échec d'inscription."""
        Plan.objects.all().delete()

        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")

        assert tenant.pk is not None
        assert not Subscription.objects.filter(tenant=tenant).exists()

    def test_a_second_subscription_is_refused(self, plan, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")

        with pytest.raises(billing_services.BillingError):
            billing_services.start_trial(tenant=tenant, plan=plan)


class TestTransitions:
    def test_activation_sets_a_renewal_date(self, plan, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)

        billing_services.activate(subscription=subscription, period="yearly")

        subscription.refresh_from_db()
        assert subscription.status == Subscription.Status.ACTIVE
        assert subscription.period == "yearly"
        assert subscription.renews_at > timezone.now() + timedelta(days=360)

    def test_suspension_keeps_the_subscription(self, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)

        billing_services.suspend(subscription=subscription, reason="Impayé")

        subscription.refresh_from_db()
        assert subscription.status == Subscription.Status.SUSPENDED
        assert subscription.is_operational is False

    def test_cancellation_records_an_end_date(self, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)

        billing_services.cancel(subscription=subscription)

        subscription.refresh_from_db()
        assert subscription.status == Subscription.Status.CANCELLED
        assert subscription.ends_at is not None

    def test_activating_an_already_active_subscription_is_a_no_op(
        self, user_factory, tenant_factory
    ):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)
        billing_services.activate(subscription=subscription)
        events_before = SubscriptionEvent.objects.filter(subscription=subscription).count()

        billing_services.activate(subscription=subscription)

        assert SubscriptionEvent.objects.filter(subscription=subscription).count() == events_before


class TestEveryTransitionIsTraced:
    def test_the_trial_opening_is_traced(self, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)

        event = SubscriptionEvent.objects.get(subscription=subscription)
        assert event.to_status == Subscription.Status.TRIAL
        assert event.reason

    def test_each_transition_records_where_it_came_from(self, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)

        billing_services.activate(subscription=subscription)
        billing_services.suspend(subscription=subscription, reason="Impayé")

        events = list(SubscriptionEvent.objects.filter(subscription=subscription).order_by("id"))
        assert [e.to_status for e in events] == ["trial", "active", "suspended"]
        assert events[2].from_status == "active"
        assert events[2].reason == "Impayé"

    def test_the_actor_is_recorded(self, user_factory, tenant_factory):
        actor = user_factory(email="admin@example.com", is_staff=True)
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)

        billing_services.suspend(subscription=subscription, actor=actor)

        event = SubscriptionEvent.objects.filter(subscription=subscription).latest("id")
        assert event.actor == actor

    def test_a_plan_change_records_both_plans(self, plan, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)
        previous_name = subscription.plan.name

        billing_services.change_plan(subscription=subscription, plan=plan)

        event = SubscriptionEvent.objects.filter(subscription=subscription).latest("id")
        assert event.from_plan == previous_name
        assert event.to_plan == "Test"


class TestPlanChangeResetsOverrides:
    def test_negotiated_overrides_do_not_follow_to_a_standard_plan(
        self, plan, user_factory, tenant_factory
    ):
        """Conserver les surcharges ferait silencieusement suivre des quotas
        sur mesure sur une offre standard."""
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)
        subscription.override_monthly_scans = 999
        subscription.save()

        billing_services.change_plan(subscription=subscription, plan=plan)

        subscription.refresh_from_db()
        assert subscription.override_monthly_scans is None
        assert subscription.monthly_scans_quota == plan.monthly_scans


class TestTrialExpiry:
    def test_due_trials_expire(self, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)
        subscription.trial_ends_at = timezone.now() - timedelta(days=1)
        subscription.save()

        assert billing_services.expire_due_trials() == 1

        subscription.refresh_from_db()
        assert subscription.status == Subscription.Status.EXPIRED

    def test_expiry_is_idempotent(self, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)
        subscription.trial_ends_at = timezone.now() - timedelta(days=1)
        subscription.save()
        billing_services.expire_due_trials()

        assert billing_services.expire_due_trials() == 0

    def test_a_running_trial_is_untouched(self, user_factory, tenant_factory):
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")

        assert billing_services.expire_due_trials() == 0
        assert Subscription.objects.get(tenant=tenant).status == Subscription.Status.TRIAL


class TestPayments:
    def test_a_payment_can_be_recorded(self, user_factory, tenant_factory):
        actor = user_factory(email="admin@example.com", is_staff=True)
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        subscription = Subscription.objects.get(tenant=tenant)

        payment = billing_services.record_payment(
            subscription=subscription,
            amount=Decimal("249"),
            received_at=timezone.now().date(),
            reference="VIR-2026-001",
            actor=actor,
        )

        assert Payment.objects.count() == 1
        assert payment.recorded_by == actor
        assert payment.currency == subscription.plan.currency


class TestPlanPricing:
    def test_the_yearly_price_is_ten_months(self, plan):
        assert plan.price_yearly == plan.price_monthly * 10

    def test_the_equivalent_months_are_exposed(self, plan):
        assert float(plan.yearly_equivalent_months) == 10.0

    def test_a_quote_only_plan_has_no_equivalent_months(self):
        quote_plan = Plan.objects.create(code="devis", name="Devis", is_quote_only=True)
        assert quote_plan.yearly_equivalent_months is None


class TestInitialCatalogue:
    """La migration de données doit produire un catalogue cohérent : c'est ce
    que la vitrine affiche au premier démarrage."""

    def test_the_three_plans_exist_and_are_published(self):
        codes = set(
            Plan.objects.filter(status=Plan.Status.PUBLISHED).values_list("code", flat=True)
        )
        assert {"veille", "pilotage", "souverain"} <= codes

    def test_only_one_plan_is_highlighted(self):
        assert Plan.objects.filter(is_highlighted=True).count() == 1

    def test_the_quote_only_plan_carries_no_price(self):
        souverain = Plan.objects.get(code="souverain")
        assert souverain.is_quote_only is True
        assert souverain.price_monthly == 0

    def test_the_committed_slots_of_all_plans_fit_a_single_licence(self, settings):
        """Garde-fou de cohérence commerciale : si la somme des emplacements
        d'un seul client de chaque offre dépassait déjà le pool, le catalogue
        serait invendable en l'état."""
        total = sum(
            plan.monitored_assets for plan in Plan.objects.filter(status=Plan.Status.PUBLISHED)
        )
        assert total <= settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE
