"""ADR-014 (mise à jour) : chiffrement réversible + révélation privilégiée,
ré-authentifiée et tracée, en remplacement du masquage définitif. Couvre :
- le round-trip chiffrement/déchiffrement (services.encrypt_secret/decrypt_secret) ;
- la propriété "aucun secret en clair en base" (complète test_no_secret_persistence.py
  pour le nouveau champ secret_encrypted — couvert là-bas, pas dupliqué ici) ;
- les conditions cumulatives de l'endpoint de révélation (rôle, ré-authentification,
  étanchéité tenant, disponibilité du secret) ;
- que CHAQUE tentative (accordée ou refusée, quelle qu'en soit la raison) est tracée
  dans SecretRevealAudit, jamais le secret lui-même ;
- le rate limiting par utilisateur/IP ;
- le journal d'audit consultable par l'admin du tenant et par l'admin plateforme.
"""

import pyotp
import pytest
from cryptography.fernet import Fernet
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import services as accounts_services
from apps.tenants.models import Membership
from apps.threat_intelligence import services
from apps.threat_intelligence.models import SecretRevealAudit
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def _grant_secret_reveal(settings):
    """Place les entreprises de ce fichier sur une offre comprenant
    « Révélation de mot de passe ».

    Porté sur l'OFFRE D'ESSAI du module, et non sur un abonnement précis :
    plusieurs tests créent une seconde entreprise en cours de route, et elle
    doit disposer de la même fonctionnalité.

    Sans cette déclaration, ce fichier dépendait silencieusement de l'offre
    d'essai de production. Le jour où elle a changé, des tests sont passés au
    rouge en 402 sans que rien ne concerne leur objet. Un test déclare ses
    préconditions, il ne les hérite pas d'un réglage commercial.
    """
    settings.BILLING_DEFAULT_TRIAL_PLAN_CODE = "pilotage"


PASSWORD = "Str0ng!Passw0rd123"


def _login(api_client, email, password=PASSWORD):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


def _auth(api_client, user, tenant, password=PASSWORD):
    access = _login(api_client, user.email, password)
    return {"HTTP_AUTHORIZATION": f"Bearer {access}", "HTTP_X_TENANT_ID": str(tenant.id)}


def _auth_direct(user, tenant):
    """Issues a JWT directly (bypasses LoginView) — needed once 2FA is
    enabled on ``user``, since LoginView then returns an MFA challenge
    instead of tokens; the MFA login flow itself is covered by
    apps.accounts.tests.test_two_factor, not re-tested here."""
    access = str(RefreshToken.for_user(user).access_token)
    return {"HTTP_AUTHORIZATION": f"Bearer {access}", "HTTP_X_TENANT_ID": str(tenant.id)}


def _enable_totp(user):
    _credential, secret = accounts_services.start_totp_enrollment(user)
    accounts_services.confirm_totp_enrollment(user, pyotp.TOTP(secret).now())
    return secret


def _ingest_secret_finding(tenant, asset, *, secret="SuperSecretRealValue123"):
    raw = RawFinding(endpoint="creds", payload={"eml": "victime@example.com", "pwd": secret})
    return services.ingest_raw_findings(tenant=tenant, asset=asset, raw_findings=[raw])[0]


def _ingest_no_secret_finding(tenant, asset):
    raw = RawFinding(
        endpoint="darkweb", payload={"data": "example.com", "site": "ForumX", "found": "2026-01-01"}
    )
    return services.ingest_raw_findings(tenant=tenant, asset=asset, raw_findings=[raw])[0]


class TestSecretEncryptionRoundTrip:
    def test_encrypt_then_decrypt_returns_original_value(self, settings):
        encrypted = services.encrypt_secret("SuperSecretRealValue123")
        assert encrypted != b""
        assert b"SuperSecretRealValue123" not in encrypted
        assert services.decrypt_secret(encrypted) == "SuperSecretRealValue123"

    def test_empty_plaintext_encrypts_to_empty_bytes(self):
        assert services.encrypt_secret("") == b""

    def test_missing_key_raises_explicit_error(self, settings):
        settings.BREACH_SECRET_ENCRYPTION_KEY = ""
        with pytest.raises(services.ThreatIntelligenceError):
            services.encrypt_secret("x")

    def test_corrupted_ciphertext_raises_explicit_error(self):
        with pytest.raises(services.ThreatIntelligenceError):
            services.decrypt_secret(b"not-a-valid-fernet-token")


class TestBreachFindingRevealAPI:
    def test_admin_can_reveal_with_correct_password(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        finding = _ingest_secret_finding(tenant, website_asset)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": PASSWORD},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["secret"] == "SuperSecretRealValue123"
        assert response["Cache-Control"] == "no-store"
        audit = SecretRevealAudit.all_objects.get(tenant=tenant)
        assert audit.success is True
        assert audit.user_id == tenant_owner.id
        assert audit.finding_id == finding.id

    def test_admin_can_reveal_with_valid_totp_code(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        finding = _ingest_secret_finding(tenant, website_asset)
        secret_totp = _enable_totp(tenant_owner)
        headers = _auth_direct(tenant_owner, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"totp_code": pyotp.TOTP(secret_totp).now()},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["secret"] == "SuperSecretRealValue123"

    def test_denied_without_admin_role_and_audited(
        self, api_client, tenant, website_asset, user_factory
    ):
        finding = _ingest_secret_finding(tenant, website_asset)
        reader = user_factory(email="reader@example.com", password=PASSWORD)
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        headers = _auth(api_client, reader, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": PASSWORD},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        audit = SecretRevealAudit.all_objects.get(tenant=tenant)
        assert audit.success is False
        assert audit.denial_reason == SecretRevealAudit.DenialReason.ROLE
        assert audit.user_id == reader.id

    def test_denied_with_wrong_password_and_audited(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        finding = _ingest_secret_finding(tenant, website_asset)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": "WrongPassword!!"},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        audit = SecretRevealAudit.all_objects.get(tenant=tenant)
        assert audit.success is False
        assert audit.denial_reason == SecretRevealAudit.DenialReason.STEP_UP

    def test_denied_with_wrong_totp_code(self, api_client, tenant, tenant_owner, website_asset):
        finding = _ingest_secret_finding(tenant, website_asset)
        _enable_totp(tenant_owner)
        headers = _auth_direct(tenant_owner, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"totp_code": "000000"},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_requires_password_or_totp_code(self, api_client, tenant, tenant_owner, website_asset):
        finding = _ingest_secret_finding(tenant, website_asset)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]), {}, format="json", **headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_admin_cannot_reveal_another_tenants_finding(
        self, api_client, user_factory, tenant_factory
    ):
        from apps.monitoring import services as monitoring_services
        from apps.monitoring.models import Asset

        owner_a = user_factory(email="owner-a@example.com", password=PASSWORD)
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        owner_b = user_factory(email="owner-b@example.com", password=PASSWORD)
        tenant_b = tenant_factory(owner_b, name="Entreprise B")
        asset_b = monitoring_services.create_asset(
            tenant=tenant_b,
            user=owner_b,
            type=Asset.Type.WEBSITE,
            value="https://b.example.com",
            ownership_confirmed=True,
        )
        finding_b = _ingest_secret_finding(tenant_b, asset_b)

        headers_a = _auth(api_client, owner_a, tenant_a, password=PASSWORD)
        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding_b.id]),
            {"password": PASSWORD},
            format="json",
            **headers_a,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        audit = SecretRevealAudit.all_objects.get(tenant=tenant_a)
        assert audit.denial_reason == SecretRevealAudit.DenialReason.NOT_FOUND
        assert audit.finding is None

    def test_denied_when_no_secret_available(self, api_client, tenant, tenant_owner, website_asset):
        finding = _ingest_no_secret_finding(tenant, website_asset)
        assert finding.has_secret is False
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": PASSWORD},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        audit = SecretRevealAudit.all_objects.get(tenant=tenant)
        assert audit.denial_reason == SecretRevealAudit.DenialReason.NO_SECRET

    def test_platform_staff_member_of_tenant_bypasses_role_requirement(
        self, api_client, tenant, website_asset, user_factory
    ):
        """(ou admin plateforme) : is_staff bypasses the tenant ADMIN role
        requirement, but only within a tenant the staff user already
        belongs to (no cross-tenant impersonation mechanism exists in this
        codebase — see ADR-014 update for the explicit scope note)."""
        finding = _ingest_secret_finding(tenant, website_asset)
        staff_reader = user_factory(
            email="staff-reader@example.com", password=PASSWORD, is_staff=True
        )
        Membership.all_objects.create(tenant=tenant, user=staff_reader, role=Membership.Role.READER)
        headers = _auth(api_client, staff_reader, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": PASSWORD},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK

    def test_reveal_rate_limited_per_user(self, api_client, tenant, tenant_owner, website_asset):
        finding = _ingest_secret_finding(tenant, website_asset)
        headers = _auth(api_client, tenant_owner, tenant)
        url = reverse("breach-finding-reveal", args=[finding.id])

        statuses = []
        for _ in range(6):
            response = api_client.post(
                url, {"password": "WrongPassword!!"}, format="json", **headers
            )
            statuses.append(response.status_code)

        assert status.HTTP_429_TOO_MANY_REQUESTS in statuses


class TestSecretRevealAuditAPI:
    def test_tenant_admin_sees_only_own_tenant_audit_entries(
        self, api_client, user_factory, tenant_factory
    ):
        from apps.monitoring import services as monitoring_services
        from apps.monitoring.models import Asset

        owner_a = user_factory(email="owner-a@example.com", password=PASSWORD)
        tenant_a = tenant_factory(owner_a, name="Entreprise A")
        asset_a = monitoring_services.create_asset(
            tenant=tenant_a,
            user=owner_a,
            type=Asset.Type.WEBSITE,
            value="https://a.example.com",
            ownership_confirmed=True,
        )
        owner_b = user_factory(email="owner-b@example.com", password=PASSWORD)
        tenant_b = tenant_factory(owner_b, name="Entreprise B")
        asset_b = monitoring_services.create_asset(
            tenant=tenant_b,
            user=owner_b,
            type=Asset.Type.WEBSITE,
            value="https://b.example.com",
            ownership_confirmed=True,
        )
        finding_a = _ingest_secret_finding(tenant_a, asset_a)
        finding_b = _ingest_secret_finding(tenant_b, asset_b)
        headers_a = _auth(api_client, owner_a, tenant_a, password=PASSWORD)
        headers_b = _auth(api_client, owner_b, tenant_b, password=PASSWORD)
        api_client.post(
            reverse("breach-finding-reveal", args=[finding_a.id]),
            {"password": PASSWORD},
            format="json",
            **headers_a,
        )
        api_client.post(
            reverse("breach-finding-reveal", args=[finding_b.id]),
            {"password": PASSWORD},
            format="json",
            **headers_b,
        )

        response = api_client.get(reverse("breach-reveal-audit-list"), **headers_a)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["finding_id"] == finding_a.id

    def test_reader_cannot_view_audit_log(self, api_client, tenant, website_asset, user_factory):
        reader = user_factory(email="reader@example.com", password=PASSWORD)
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        headers = _auth(api_client, reader, tenant, password=PASSWORD)

        response = api_client.get(reverse("breach-reveal-audit-list"), **headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_platform_admin_status_includes_recent_reveal_audits(
        self, api_client, tenant, tenant_owner, website_asset, user_factory
    ):
        finding = _ingest_secret_finding(tenant, website_asset)
        headers = _auth(api_client, tenant_owner, tenant)
        api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": PASSWORD},
            format="json",
            **headers,
        )
        staff = user_factory(email="staff@example.com", is_staff=True)
        access = _login(api_client, staff.email)

        response = api_client.get(
            reverse("threat-intelligence-admin-status"), HTTP_AUTHORIZATION=f"Bearer {access}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["recent_reveal_audits"]) == 1
        assert response.data["recent_reveal_audits"][0]["tenant_name"] == tenant.name
        assert "secret" not in str(response.data["recent_reveal_audits"])


class TestUnreadableSecret:
    """Rotation menée sans re-chiffrement, ancienne clé retirée trop tôt,
    donnée corrompue : le secret est là mais illisible. Trouvé en conditions
    réelles (Phase 8D) — le conteneur tournait avec la clé d'avant rotation et
    l'endpoint renvoyait une 500 brute."""

    def test_returns_a_clean_error_not_a_crash(
        self, api_client, tenant, tenant_owner, website_asset, settings
    ):
        finding = _ingest_secret_finding(tenant, website_asset)
        # Clé valide mais différente : le blob existant devient indéchiffrable.
        settings.BREACH_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()
        settings.BREACH_SECRET_ENCRYPTION_KEYS = []
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": PASSWORD},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "illisible" in response.data["detail"]

    def test_the_failed_attempt_is_still_audited(
        self, api_client, tenant, tenant_owner, website_asset, settings
    ):
        finding = _ingest_secret_finding(tenant, website_asset)
        settings.BREACH_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()
        settings.BREACH_SECRET_ENCRYPTION_KEYS = []
        headers = _auth(api_client, tenant_owner, tenant)

        api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": PASSWORD},
            format="json",
            **headers,
        )

        audit = SecretRevealAudit.all_objects.get(tenant=tenant)
        assert audit.success is False

    def test_no_secret_material_leaks_in_the_error(
        self, api_client, tenant, tenant_owner, website_asset, settings
    ):
        finding = _ingest_secret_finding(tenant, website_asset)
        settings.BREACH_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()
        settings.BREACH_SECRET_ENCRYPTION_KEYS = []
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("breach-finding-reveal", args=[finding.id]),
            {"password": PASSWORD},
            format="json",
            **headers,
        )

        assert "SuperSecretRealValue123" not in str(response.data)
