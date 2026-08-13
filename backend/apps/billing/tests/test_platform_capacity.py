"""Plafonds PLATEFORME — le test le plus important de la Phase 10.

La licence borne toute la plateforme (15 emplacements de surveillance, 1000
analyses/mois), pas chaque client. Vendre au-delà produirait un engagement
contractuel intenable, découvert quand le client active sa surveillance.

Ce que ces tests verrouillent : le refus intervient **avant** l'écriture. Un
abonnement refusé ne doit laisser aucune trace — ni ligne en base, ni
emplacement engagé. Un test qui vérifierait seulement « une exception est
levée » laisserait passer un enregistrement suivi d'un rollback oublié.
"""

import pytest
from django.core import mail

from apps.billing import capacity
from apps.billing import services as billing_services
from apps.billing.models import Plan, Subscription

pytestmark = pytest.mark.django_db


@pytest.fixture
def small_pool(settings, db):
    """Pool réduit à 5 : exercer la vraie limite de 15 demanderait de créer
    quinze abonnements par test, sans rien prouver de plus.

    Fixe aussi l'offre d'essai par défaut à 1 emplacement. Depuis la Phase 10,
    créer une entreprise ouvre un essai automatiquement : sans cela, chaque
    ``tenant_factory`` consommerait les 3 emplacements de l'offre Pilotage et
    la comptabilité de ces tests dépendrait du catalogue de production.
    """
    settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE = 5
    Plan.objects.create(
        code="defaut-test",
        name="Défaut test",
        monitored_assets=1,
        monthly_scans=10,
        status=Plan.Status.PUBLISHED,
    )
    settings.BILLING_DEFAULT_TRIAL_PLAN_CODE = "defaut-test"
    return 5


@pytest.fixture
def plan_factory(db):
    def make(code, *, monitored_assets=1, monthly_scans=20, status=Plan.Status.PUBLISHED):
        return Plan.objects.create(
            code=code,
            name=code.title(),
            monitored_assets=monitored_assets,
            monthly_scans=monthly_scans,
            status=status,
        )

    return make


class TestSlotAccounting:
    def test_commitment_counts_quotas_not_activated_assets(
        self, small_pool, plan_factory, user_factory, tenant_factory
    ):
        """On compte ce qui est ENGAGÉ, pas ce qui est déjà activé : un client
        qui n'a pas encore branché sa surveillance y a malgré tout droit."""
        plan = plan_factory("trois", monitored_assets=3)
        owner = user_factory(email="a@example.com")
        tenant = tenant_factory(owner, name="A")
        Subscription.objects.filter(tenant=tenant).update(plan=plan)

        assert capacity.monitored_slots_committed() == 3

    def test_suspended_subscriptions_free_their_slots(
        self, small_pool, plan_factory, user_factory, tenant_factory
    ):
        plan = plan_factory("trois", monitored_assets=3)
        owner = user_factory(email="a@example.com")
        tenant = tenant_factory(owner, name="A")
        subscription = Subscription.objects.get(tenant=tenant)
        subscription.plan = plan
        subscription.save()
        assert capacity.monitored_slots_committed() == 3

        billing_services.suspend(subscription=subscription)

        assert capacity.monitored_slots_committed() == 0


class TestTrialRefusedWhenPoolFull:
    def test_a_trial_that_would_overflow_is_refused(
        self, small_pool, plan_factory, user_factory, tenant_factory, settings
    ):
        settings.BILLING_DEFAULT_TRIAL_PLAN_CODE = "gros"
        plan_factory("gros", monitored_assets=4)

        # Premier client : 4 sur 5, ça passe.
        tenant_factory(user_factory(email="a@example.com"), name="A")
        assert capacity.monitored_slots_committed() == 4

        # Second client : 4 + 4 = 8 > 5. L'essai doit être refusé.
        with pytest.raises(capacity.PlatformCapacityError):
            billing_services.start_trial(
                tenant=tenant_factory(user_factory(email="b@example.com"), name="B")
            )

    def test_nothing_is_written_when_the_trial_is_refused(
        self, small_pool, plan_factory, user_factory, tenant_factory
    ):
        """Le point central : refuser APRÈS avoir enregistré reviendrait à
        vendre puis à se dédire."""
        plan = plan_factory("gros", monitored_assets=4)
        owner_a = user_factory(email="a@example.com")
        tenant_a = tenant_factory(owner_a, name="A")
        Subscription.objects.filter(tenant=tenant_a).update(plan=plan)

        owner_b = user_factory(email="b@example.com")
        from apps.tenants.models import Tenant

        tenant_b = Tenant.objects.create(name="B", slug="b")

        before = Subscription.objects.count()
        with pytest.raises(capacity.PlatformCapacityError):
            billing_services.start_trial(tenant=tenant_b, plan=plan, actor=owner_b)

        assert Subscription.objects.count() == before
        assert not Subscription.objects.filter(tenant=tenant_b).exists()
        assert capacity.monitored_slots_committed() == 4

    def test_the_refusal_says_what_remains(
        self, small_pool, plan_factory, user_factory, tenant_factory
    ):
        """Un refus sans indication de sortie oblige l'exploitant à lire le
        code pour comprendre quoi faire."""
        plan = plan_factory("gros", monitored_assets=4)
        tenant_a = tenant_factory(user_factory(email="a@example.com"), name="A")
        Subscription.objects.filter(tenant=tenant_a).update(plan=plan)

        from apps.tenants.models import Tenant

        with pytest.raises(capacity.PlatformCapacityError) as exc_info:
            billing_services.start_trial(
                tenant=Tenant.objects.create(name="B", slug="b"), plan=plan
            )

        message = str(exc_info.value)
        assert "5" in message  # le plafond
        assert "reste" in message.lower()
        assert "licence" in message.lower()  # la sortie proposée


class TestPlanChangeRefusedWhenPoolFull:
    def test_upgrading_beyond_the_pool_is_refused(
        self, small_pool, plan_factory, user_factory, tenant_factory
    ):
        small = plan_factory("petit", monitored_assets=1)
        big = plan_factory("gros", monitored_assets=5)
        tenant_a = tenant_factory(user_factory(email="a@example.com"), name="A")
        tenant_b = tenant_factory(user_factory(email="b@example.com"), name="B")
        for tenant in (tenant_a, tenant_b):
            Subscription.objects.filter(tenant=tenant).update(plan=small)

        subscription_a = Subscription.objects.get(tenant=tenant_a)
        with pytest.raises(capacity.PlatformCapacityError):
            billing_services.change_plan(subscription=subscription_a, plan=big)

        subscription_a.refresh_from_db()
        assert subscription_a.plan == small  # inchangé

    def test_the_subscription_being_changed_is_not_counted_twice(
        self, small_pool, plan_factory, user_factory, tenant_factory
    ):
        """Sans exclusion, passer de 1 à 4 emplacements compterait 1 + 4 = 5
        au lieu de 4, et refuserait une opération pourtant possible."""
        small = plan_factory("petit", monitored_assets=1)
        medium = plan_factory("moyen", monitored_assets=4)
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        Subscription.objects.filter(tenant=tenant).update(plan=small)
        subscription = Subscription.objects.get(tenant=tenant)

        billing_services.change_plan(subscription=subscription, plan=medium)

        subscription.refresh_from_db()
        assert subscription.plan == medium

    def test_downgrading_is_always_allowed(
        self, small_pool, plan_factory, user_factory, tenant_factory
    ):
        big = plan_factory("gros", monitored_assets=5)
        small = plan_factory("petit", monitored_assets=1)
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        Subscription.objects.filter(tenant=tenant).update(plan=big)
        subscription = Subscription.objects.get(tenant=tenant)

        billing_services.change_plan(subscription=subscription, plan=small)

        subscription.refresh_from_db()
        assert subscription.plan == small


class TestReactivationRefusedWhenPoolFull:
    def test_reactivating_into_a_full_pool_is_refused(
        self, small_pool, plan_factory, user_factory, tenant_factory
    ):
        """Un abonnement suspendu a libéré ses emplacements : le réactiver les
        ré-engage réellement, et doit repasser la garde."""
        plan = plan_factory("gros", monitored_assets=4)
        tenant_a = tenant_factory(user_factory(email="a@example.com"), name="A")
        tenant_b = tenant_factory(user_factory(email="b@example.com"), name="B")
        Subscription.objects.filter(tenant__in=[tenant_a, tenant_b]).update(plan=plan)

        subscription_a = Subscription.objects.get(tenant=tenant_a)
        subscription_b = Subscription.objects.get(tenant=tenant_b)
        billing_services.suspend(subscription=subscription_a)
        billing_services.suspend(subscription=subscription_b)
        billing_services.activate(subscription=subscription_b)  # 4/5, passe

        with pytest.raises(capacity.PlatformCapacityError):
            billing_services.activate(subscription=subscription_a)

        subscription_a.refresh_from_db()
        assert subscription_a.status == Subscription.Status.SUSPENDED


class TestScanBudget:
    def test_scan_budget_is_refused_when_the_monthly_cap_is_reached(
        self, settings, user_factory, tenant_factory
    ):
        settings.PLATFORM_MONTHLY_SCAN_CAP = 3
        from apps.threat_intelligence.models import BreachIntelligenceUsage

        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        BreachIntelligenceUsage.all_objects.create(
            tenant=tenant, requests_consumed=3, triggered_by="manual"
        )

        with pytest.raises(capacity.PlatformCapacityError) as exc_info:
            capacity.ensure_scan_budget_available(additional=1)
        assert "3" in str(exc_info.value)

    def test_scan_budget_passes_below_the_cap(self, settings, user_factory, tenant_factory):
        settings.PLATFORM_MONTHLY_SCAN_CAP = 10
        capacity.ensure_scan_budget_available(additional=1)  # ne doit pas lever


class TestOperationalAlerts:
    def test_an_alert_is_sent_at_eighty_percent(
        self, settings, small_pool, plan_factory, user_factory, tenant_factory
    ):
        settings.PLATFORM_ALERT_EMAIL = "exploitant@example.test"
        plan = plan_factory("quatre", monitored_assets=4)
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        Subscription.objects.filter(tenant=tenant).update(plan=plan)  # 4/5 = 80 %

        mail.outbox.clear()
        sent = capacity.check_alert_thresholds()

        assert any(s.startswith("monitored_slots@80") for s in sent)
        assert len(mail.outbox) == 1
        assert "80" in mail.outbox[0].subject

    def test_the_same_alert_is_not_sent_twice(
        self, settings, small_pool, plan_factory, user_factory, tenant_factory
    ):
        """Une alerte répétée à chaque opération cesse d'être lue — le pire
        résultat possible pour une alerte."""
        settings.PLATFORM_ALERT_EMAIL = "exploitant@example.test"
        plan = plan_factory("quatre", monitored_assets=4)
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        Subscription.objects.filter(tenant=tenant).update(plan=plan)

        capacity.check_alert_thresholds()
        mail.outbox.clear()
        capacity.check_alert_thresholds()

        assert mail.outbox == []

    def test_no_alert_without_a_configured_recipient(
        self, settings, small_pool, plan_factory, user_factory, tenant_factory
    ):
        settings.PLATFORM_ALERT_EMAIL = ""
        plan = plan_factory("quatre", monitored_assets=4)
        tenant = tenant_factory(user_factory(email="a@example.com"), name="A")
        Subscription.objects.filter(tenant=tenant).update(plan=plan)

        assert capacity.check_alert_thresholds() == []


class TestGuardActuallyBites:
    """Vérification exigée par la phase : neutraliser temporairement la garde
    doit faire ROUGIR les tests de refus. Sans cela, un test de refus pourrait
    passer pour une raison sans rapport (une exception levée plus tôt, un
    paramétrage qui rend le scénario impossible) et donner une fausse
    assurance."""

    def test_disabling_the_guard_lets_the_overflow_through(
        self, small_pool, plan_factory, user_factory, tenant_factory, monkeypatch
    ):
        plan = plan_factory("gros", monitored_assets=4)
        tenant_a = tenant_factory(user_factory(email="a@example.com"), name="A")
        Subscription.objects.filter(tenant=tenant_a).update(plan=plan)

        from apps.tenants.models import Tenant

        tenant_b = Tenant.objects.create(name="B", slug="b")

        # Garde neutralisée : l'enregistrement passe et la plateforme dépasse
        # son plafond (8 engagés pour 5). C'est exactement ce que la garde
        # empêche en temps normal.
        monkeypatch.setattr(capacity, "ensure_monitored_slots_available", lambda **kwargs: None)
        monkeypatch.setattr(
            billing_services.capacity, "ensure_monitored_slots_available", lambda **kwargs: None
        )

        billing_services.start_trial(tenant=tenant_b, plan=plan)

        assert Subscription.objects.filter(tenant=tenant_b).exists()
        assert capacity.monitored_slots_committed() == 8 > small_pool
