"""Phase 8A : le tenant de démonstration doit être rejouable sans effet de
bord (une démo client se prépare en relançant la commande), impossible à
confondre avec des données réelles, et refusé par défaut hors DEBUG.
"""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.monitoring.models import Asset
from apps.tenants.models import Membership, Tenant
from apps.threat_intelligence.management.commands.seed_demo_tenant import (
    DEMO_PASSWORD,
    DEMO_TENANT_NAME,
    DEMO_TENANT_NAME_PREFIX,
    DEMO_TENANT_SLUG,
    DEMO_USERS,
    demo_findings_payloads,
)
from apps.threat_intelligence.models import BreachFinding

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _debug_on(settings):
    # La suite tourne avec DEBUG=False ; le garde-fou de la commande ferait
    # donc échouer tous les cas nominaux. On l'active explicitement ici, et
    # le garde-fou lui-même est testé à part (test_refuses_to_run_outside_debug).
    settings.DEBUG = True


def _demo_tenant() -> Tenant:
    return Tenant.objects.get(slug=DEMO_TENANT_SLUG)


class TestSeedDemoTenant:
    def test_creates_tenant_users_assets_and_findings(self):
        call_command("seed_demo_tenant")

        tenant = _demo_tenant()
        assert tenant.name == DEMO_TENANT_NAME
        assert Membership.all_objects.filter(tenant=tenant).count() == len(DEMO_USERS)
        assert Asset.all_objects.filter(tenant=tenant).count() == 4
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == len(
            demo_findings_payloads()
        )

    def test_covers_every_source_endpoint(self):
        """La démo doit montrer toute l'étendue du produit — un endpoint
        manquant, c'est une catégorie de fuite qu'on ne sait pas illustrer."""
        call_command("seed_demo_tenant")

        seeded = set(
            BreachFinding.all_objects.filter(tenant=_demo_tenant()).values_list(
                "source_endpoint", flat=True
            )
        )
        expected = {endpoint for endpoint, _payload, _idx in demo_findings_payloads()}
        assert expected <= seeded

    def test_is_idempotent(self):
        call_command("seed_demo_tenant")
        first_count = BreachFinding.all_objects.filter(tenant=_demo_tenant()).count()

        call_command("seed_demo_tenant")
        call_command("seed_demo_tenant")

        assert BreachFinding.all_objects.filter(tenant=_demo_tenant()).count() == first_count
        assert Tenant.objects.filter(slug=DEMO_TENANT_SLUG).count() == 1
        assert Membership.all_objects.filter(tenant=_demo_tenant()).count() == len(DEMO_USERS)

    def test_reset_rebuilds_findings_from_scratch(self):
        call_command("seed_demo_tenant")
        tenant = _demo_tenant()
        BreachFinding.all_objects.filter(tenant=tenant).first().delete()

        call_command("seed_demo_tenant", reset=True)

        assert BreachFinding.all_objects.filter(tenant=tenant).count() == len(
            demo_findings_payloads()
        )

    def test_refuses_to_run_outside_debug_without_explicit_flag(self, settings):
        settings.DEBUG = False
        with pytest.raises(CommandError, match="production"):
            call_command("seed_demo_tenant")
        assert not Tenant.objects.filter(slug=DEMO_TENANT_SLUG).exists()

    def test_allow_production_flag_overrides_the_guard(self, settings):
        settings.DEBUG = False
        call_command("seed_demo_tenant", allow_production=True)
        assert Tenant.objects.filter(slug=DEMO_TENANT_SLUG).exists()


class TestDemoDataIsRecognisable:
    def test_tenant_name_carries_the_reserved_demo_prefix(self):
        call_command("seed_demo_tenant")
        assert _demo_tenant().name.startswith(DEMO_TENANT_NAME_PREFIX)

    def test_demo_password_is_not_a_real_looking_secret(self):
        assert "Demo" in DEMO_PASSWORD

    def test_seeded_secrets_are_never_persisted_in_clear(self):
        """ADR-014 s'applique aussi aux données de démo : elles passent par
        le vrai pipeline, donc le secret seedé doit être chiffré, pas en
        clair, même s'il est factice."""
        call_command("seed_demo_tenant")

        plain_secrets = [
            payload["pwd"] for _e, payload, _i in demo_findings_payloads() if "pwd" in payload
        ]
        for finding in BreachFinding.all_objects.filter(tenant=_demo_tenant()):
            blob = json.dumps(finding.raw_data) + finding.secret_masked
            for secret in plain_secrets:
                assert secret not in blob

    def test_a_seeded_finding_has_a_revealable_encrypted_secret(self):
        """Le scénario de démo inclut une révélation : au moins un finding
        doit réellement porter un secret déchiffrable."""
        from apps.threat_intelligence import services

        call_command("seed_demo_tenant")

        revealable = [
            f
            for f in BreachFinding.all_objects.filter(tenant=_demo_tenant())
            if f.has_secret and bytes(f.secret_encrypted)
        ]
        assert revealable
        assert services.decrypt_secret(bytes(revealable[0].secret_encrypted))
