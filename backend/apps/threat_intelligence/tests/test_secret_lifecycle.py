"""Cycle de vie du secret de fuite (Phase 8C, ADR-014) : purge à échéance et
rotation de la clé de chiffrement.

Le point qui structure ces tests : **on purge le secret, pas la fuite**.
Supprimer le `BreachFinding` ferait perdre l'historique de conformité (« cette
fuite a été traitée le … »), qui est précisément ce qu'un tenant doit pouvoir
présenter. Chaque test de purge vérifie donc les deux faces : ce qui disparaît
et ce qui reste.
"""

from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.utils import timezone

from apps.threat_intelligence import services
from apps.threat_intelligence.models import BreachFinding, SecretPurgeRun, SecretRevealAudit
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db

# Clés générées à l'exécution, jamais écrites en dur : une constante de test
# finit tôt ou tard par être copiée dans un `.env` (ou l'inverse — c'est
# exactement ce qui s'est produit ici, la clé de développement ayant été
# reprise comme constante puis publiée dans le dépôt). Générer rend cette
# confusion structurellement impossible, sans rien coûter au test.
KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()


def _ingest(tenant, asset, *, secret="SuperSecret42", email="victime@example.com"):
    return services.ingest_raw_findings(
        tenant=tenant,
        asset=asset,
        raw_findings=[RawFinding(endpoint="creds", payload={"eml": email, "pwd": secret})],
    )[0]


def _age(finding, days):
    """Vieillit un finding : ``detected_at`` est un auto_now_add."""
    BreachFinding.all_objects.filter(pk=finding.pk).update(
        detected_at=timezone.now() - timedelta(days=days)
    )


class TestPurgeRespectsRetention:
    def test_recent_secret_is_kept(self, tenant, website_asset, settings):
        settings.BREACH_SECRET_RETENTION_DAYS = 90
        finding = _ingest(tenant, website_asset)
        _age(finding, 10)

        services.purge_expired_secrets()

        finding.refresh_from_db()
        assert finding.has_secret is True
        assert bytes(finding.secret_encrypted) != b""
        assert finding.secret_purged_at is None

    def test_expired_secret_is_erased(self, tenant, website_asset, settings):
        settings.BREACH_SECRET_RETENTION_DAYS = 90
        finding = _ingest(tenant, website_asset)
        _age(finding, 120)

        services.purge_expired_secrets()

        finding.refresh_from_db()
        assert finding.has_secret is False
        assert bytes(finding.secret_encrypted) == b""
        assert finding.secret_purged_at is not None

    def test_the_finding_itself_survives_the_purge(self, tenant, website_asset, settings):
        """Le point central : c'est le secret qui expire, pas la fuite."""
        settings.BREACH_SECRET_RETENTION_DAYS = 90
        finding = _ingest(tenant, website_asset)
        services.set_finding_status(finding, status=BreachFinding.Status.TREATED)
        _age(finding, 200)

        services.purge_expired_secrets()

        finding.refresh_from_db()
        assert finding.pk is not None
        assert finding.source_endpoint == "creds"
        assert finding.severity
        assert finding.status == BreachFinding.Status.TREATED
        assert finding.treated_at is not None
        assert finding.secret_masked  # la forme masquée reste affichable
        assert finding.identifier_masked or finding.identifier_plain

    def test_retention_delay_is_configurable(self, tenant, website_asset, settings):
        settings.BREACH_SECRET_RETENTION_DAYS = 10
        finding = _ingest(tenant, website_asset)
        _age(finding, 30)

        services.purge_expired_secrets()

        finding.refresh_from_db()
        assert finding.has_secret is False

    def test_purge_is_idempotent(self, tenant, website_asset, settings):
        settings.BREACH_SECRET_RETENTION_DAYS = 90
        finding = _ingest(tenant, website_asset)
        _age(finding, 120)

        first = services.purge_expired_secrets()
        purged_at = BreachFinding.all_objects.get(pk=finding.pk).secret_purged_at
        second = services.purge_expired_secrets()

        assert first.secrets_purged == 1
        assert second.secrets_purged == 0
        # L'horodatage de purge n'est pas réécrit au second passage.
        assert BreachFinding.all_objects.get(pk=finding.pk).secret_purged_at == purged_at

    def test_purge_spans_every_tenant(self, user_factory, tenant_factory, settings):
        from apps.monitoring import services as monitoring_services
        from apps.monitoring.models import Asset

        settings.BREACH_SECRET_RETENTION_DAYS = 90
        findings = []
        for name in ("A", "B"):
            owner = user_factory(email=f"owner-{name}@example.com")
            tenant = tenant_factory(owner, name=f"Entreprise {name}")
            asset = monitoring_services.create_asset(
                tenant=tenant,
                user=owner,
                type=Asset.Type.WEBSITE,
                value=f"https://{name.lower()}.example.com",
                ownership_confirmed=True,
            )
            finding = _ingest(tenant, asset)
            _age(finding, 120)
            findings.append(finding)

        run = services.purge_expired_secrets()

        assert run.secrets_purged == 2
        for finding in findings:
            finding.refresh_from_db()
            assert finding.has_secret is False


class TestPurgeTraceability:
    def test_each_run_is_recorded_without_any_secret(self, tenant, website_asset, settings):
        settings.BREACH_SECRET_RETENTION_DAYS = 90
        finding = _ingest(tenant, website_asset, secret="TrèsSecret123")
        _age(finding, 120)

        run = services.purge_expired_secrets()

        assert SecretPurgeRun.objects.count() == 1
        assert run.retention_days == 90
        assert run.secrets_purged == 1
        assert "TrèsSecret123" not in str(run.__dict__)

    def test_runs_are_listed_for_the_back_office(self, tenant, website_asset):
        services.purge_expired_secrets()
        services.purge_expired_secrets()
        assert len(services.list_purge_runs()) == 2


class TestRevealAuditRetention:
    def test_audit_entries_outlive_the_secrets_they_protect(
        self, tenant, tenant_owner, website_asset, settings
    ):
        """Décision explicite : le journal des révélations est conservé plus
        longtemps que les secrets. C'est une piste d'audit de sécurité — sa
        valeur est justement de survivre à la donnée qu'elle protège."""
        settings.BREACH_SECRET_RETENTION_DAYS = 90
        settings.BREACH_REVEAL_AUDIT_RETENTION_DAYS = 365
        finding = _ingest(tenant, website_asset)
        audit = services.record_reveal_attempt(
            tenant=tenant, finding=finding, user=tenant_owner, success=True
        )
        SecretRevealAudit.all_objects.filter(pk=audit.pk).update(
            created_at=timezone.now() - timedelta(days=120)
        )
        _age(finding, 120)

        services.purge_expired_secrets()

        assert BreachFinding.all_objects.get(pk=finding.pk).has_secret is False
        assert SecretRevealAudit.all_objects.filter(pk=audit.pk).exists()

    def test_audit_entries_are_deleted_past_their_own_retention(
        self, tenant, tenant_owner, website_asset, settings
    ):
        settings.BREACH_REVEAL_AUDIT_RETENTION_DAYS = 365
        audit = services.record_reveal_attempt(
            tenant=tenant, finding=None, user=tenant_owner, success=False, denial_reason="role"
        )
        SecretRevealAudit.all_objects.filter(pk=audit.pk).update(
            created_at=timezone.now() - timedelta(days=400)
        )

        run = services.purge_expired_secrets()

        assert run.reveal_audits_deleted == 1
        assert not SecretRevealAudit.all_objects.filter(pk=audit.pk).exists()


class TestRetentionPolicyIsReadable:
    def test_policy_is_exposed_to_the_tenant(self, settings):
        settings.BREACH_SECRET_RETENTION_DAYS = 90
        settings.BREACH_REVEAL_AUDIT_RETENTION_DAYS = 365

        policy = services.retention_policy()

        assert policy["secret_retention_days"] == 90
        assert policy["reveal_audit_retention_days"] == 365

    def test_policy_is_carried_by_the_exposure_feed(self, tenant):
        feed = services.build_exposure_feed(tenant)
        assert "retention_policy" in feed


class TestKeyRotation:
    def test_secret_encrypted_with_an_old_key_stays_readable(self, tenant, website_asset, settings):
        """Le cœur de la rotation sans coupure : la nouvelle clé chiffre, mais
        l'ancienne déchiffre toujours l'existant."""
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_A]
        finding = _ingest(tenant, website_asset, secret="AvantRotation")

        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_B, KEY_A]  # KEY_B devient courante

        assert services.decrypt_secret(bytes(finding.secret_encrypted)) == "AvantRotation"

    def test_new_secrets_use_the_current_key(self, tenant, website_asset, settings):
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_B, KEY_A]
        finding = _ingest(tenant, website_asset, secret="ApresRotation")

        # Déchiffrable par la seule clé courante => c'est bien elle qui a servi.
        assert Fernet(KEY_B).decrypt(bytes(finding.secret_encrypted)).decode() == "ApresRotation"

    def test_command_reencrypts_existing_secrets(self, tenant, website_asset, settings):
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_A]
        finding = _ingest(tenant, website_asset, secret="ÀReChiffrer")
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_B, KEY_A]

        call_command("rotate_breach_secret_key")

        finding.refresh_from_db()
        # Lisible par la nouvelle clé SEULE : l'ancienne peut désormais partir.
        assert Fernet(KEY_B).decrypt(bytes(finding.secret_encrypted)).decode() == "ÀReChiffrer"

    def test_old_key_can_be_removed_after_rotation(self, tenant, website_asset, settings):
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_A]
        finding = _ingest(tenant, website_asset, secret="Persistant")
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_B, KEY_A]
        call_command("rotate_breach_secret_key")

        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_B]  # retrait de l'ancienne

        finding.refresh_from_db()
        assert services.decrypt_secret(bytes(finding.secret_encrypted)) == "Persistant"

    def test_rotation_is_replayable(self, tenant, website_asset, settings):
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_A]
        finding = _ingest(tenant, website_asset, secret="Rejouable")
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_B, KEY_A]

        call_command("rotate_breach_secret_key")
        call_command("rotate_breach_secret_key")

        finding.refresh_from_db()
        assert services.decrypt_secret(bytes(finding.secret_encrypted)) == "Rejouable"

    def test_dry_run_writes_nothing(self, tenant, website_asset, settings):
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_A]
        finding = _ingest(tenant, website_asset, secret="Intact")
        before = bytes(finding.secret_encrypted)
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_B, KEY_A]

        call_command("rotate_breach_secret_key", dry_run=True)

        finding.refresh_from_db()
        assert bytes(finding.secret_encrypted) == before

    def test_unreadable_secret_is_reported_not_destroyed(self, tenant, website_asset, settings):
        """Un secret qu'aucune clé configurée n'ouvre (clé oubliée) ne doit
        surtout pas être effacé : une clé retrouvée plus tard peut encore le
        lire. On le signale, on passe."""
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_A]
        finding = _ingest(tenant, website_asset, secret="Orphelin")
        before = bytes(finding.secret_encrypted)
        settings.BREACH_SECRET_ENCRYPTION_KEYS = [KEY_B]  # KEY_A absente

        call_command("rotate_breach_secret_key")

        finding.refresh_from_db()
        assert bytes(finding.secret_encrypted) == before
        assert finding.has_secret is True

    def test_single_key_setting_still_works(self, tenant, website_asset, settings):
        """Rétrocompatibilité : un déploiement existant n'a que
        BREACH_SECRET_ENCRYPTION_KEY et doit continuer de fonctionner."""
        settings.BREACH_SECRET_ENCRYPTION_KEYS = []
        settings.BREACH_SECRET_ENCRYPTION_KEY = KEY_A

        finding = _ingest(tenant, website_asset, secret="MonoClé")

        assert services.decrypt_secret(bytes(finding.secret_encrypted)) == "MonoClé"
