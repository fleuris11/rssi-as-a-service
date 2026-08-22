"""Phase 8B, tâche 4 — la synthèse IA d'exposition.

Trois exigences distinctes sont vérifiées ici :
1. la page reste complète **sans** synthèse (c'est une couche au-dessus, pas
   un prérequis) ;
2. le cache est invalidé quand l'état des fuites change, sinon l'analyse
   décrirait un état périmé sans le dire ;
3. aucun identifiant réel ne part chez le fournisseur (ADR-005) — testé sur
   le payload exact transmis, pas sur une inspection du contexte en amont.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.threat_intelligence import services
from apps.threat_intelligence.models import ExposureSynthesis
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def _grant_exposure_synthesis(settings):
    """Place les entreprises de ce fichier sur une offre comprenant
    « Synthèse d'exposition ».

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


def _auth(api_client, user, tenant):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": user.email, "password": PASSWORD}, format="json"
    )
    return {
        "HTTP_AUTHORIZATION": f"Bearer {response.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


def _ingest(tenant, asset, endpoint="creds", payload=None):
    payload = payload or {"eml": "victime@example.com", "pwd": "SuperSecret42"}
    return services.ingest_raw_findings(
        tenant=tenant, asset=asset, raw_findings=[RawFinding(endpoint=endpoint, payload=payload)]
    )[0]


@pytest.fixture
def mock_claude():
    """Mocke le SDK au niveau du client, comme test_pseudonymization : c'est
    ce qui permet d'inspecter le payload RÉELLEMENT transmis."""
    with patch("apps.ai_assistant.services._get_client") as get_client:
        client = MagicMock()
        message = MagicMock()
        block = MagicMock()
        block.type = "text"
        block.text = "Votre exposition est concentrée sur un compte."
        message.content = [block]
        message.usage.input_tokens = 100
        message.usage.output_tokens = 50
        client.messages.create.return_value = message
        get_client.return_value = client
        yield client


class TestSynthesisIsOptional:
    def test_feed_is_complete_without_any_synthesis(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        _ingest(tenant, website_asset)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-exposure-feed"), **headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["synthesis"] is None
        assert response.data["assets"]  # le contenu utile est bien là

    def test_feed_never_triggers_an_ai_call(
        self, api_client, tenant, tenant_owner, website_asset, mock_claude
    ):
        """Aucun appel IA dans le cycle requête/réponse (CLAUDE.md)."""
        _ingest(tenant, website_asset)
        headers = _auth(api_client, tenant_owner, tenant)

        api_client.get(reverse("breach-exposure-feed"), **headers)

        mock_claude.messages.create.assert_not_called()


class TestSynthesisCacheAndInvalidation:
    def test_generation_caches_the_result(self, tenant, website_asset, mock_claude):
        _ingest(tenant, website_asset)

        services.refresh_exposure_synthesis(tenant)

        synthesis = services.get_exposure_synthesis(tenant)
        assert synthesis is not None
        assert synthesis.is_stale is False
        assert synthesis.content

    def test_only_one_row_per_tenant(self, tenant, website_asset, mock_claude):
        _ingest(tenant, website_asset)
        services.refresh_exposure_synthesis(tenant)
        services.refresh_exposure_synthesis(tenant)

        assert ExposureSynthesis.all_objects.filter(tenant=tenant).count() == 1

    def test_new_finding_marks_the_synthesis_stale(self, tenant, website_asset, mock_claude):
        _ingest(tenant, website_asset)
        services.refresh_exposure_synthesis(tenant)

        _ingest(tenant, website_asset, payload={"eml": "autre@example.com", "pwd": "x"})

        assert services.get_exposure_synthesis(tenant).is_stale is True

    def test_treating_a_finding_marks_the_synthesis_stale(
        self, tenant, tenant_owner, website_asset, mock_claude
    ):
        finding = _ingest(tenant, website_asset)
        services.refresh_exposure_synthesis(tenant)

        services.set_finding_status(finding, status="treated", user=tenant_owner)

        assert services.get_exposure_synthesis(tenant).is_stale is True

    def test_stale_synthesis_is_still_served(
        self, api_client, tenant, tenant_owner, website_asset, mock_claude
    ):
        """Obsolète ≠ supprimée : on l'affiche avec une mention, plutôt que de
        faire disparaître le bandeau sans explication."""
        _ingest(tenant, website_asset)
        services.refresh_exposure_synthesis(tenant)
        services.mark_synthesis_stale(tenant)
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(reverse("breach-exposure-feed"), **headers)

        assert response.data["synthesis"]["is_stale"] is True
        assert response.data["synthesis"]["content"]

    def test_fingerprint_changes_when_findings_change(self, tenant, website_asset):
        before = services.findings_fingerprint(tenant)
        _ingest(tenant, website_asset)
        assert services.findings_fingerprint(tenant) != before


class TestSynthesisRefreshEndpoint:
    def test_returns_a_job_and_schedules_the_task(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        _ingest(tenant, website_asset)
        headers = _auth(api_client, tenant_owner, tenant)

        with patch("apps.ai_assistant.tasks.generate_exposure_synthesis_task.delay") as delayed:
            response = api_client.post(reverse("breach-exposure-synthesis-refresh"), **headers)

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "job_id" in response.data
        delayed.assert_called_once()

    def test_cooldown_returns_429(
        self, api_client, tenant, tenant_owner, website_asset, mock_claude
    ):
        _ingest(tenant, website_asset)
        services.refresh_exposure_synthesis(tenant)
        headers = _auth(api_client, tenant_owner, tenant)

        with patch("apps.ai_assistant.tasks.generate_exposure_synthesis_task.delay"):
            response = api_client.post(reverse("breach-exposure-synthesis-refresh"), **headers)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_ai_disabled_returns_403_not_500(self, api_client, tenant, tenant_owner, website_asset):
        tenant.ai_enabled = False
        tenant.save(update_fields=["ai_enabled"])
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(reverse("breach-exposure-synthesis-refresh"), **headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reader_cannot_trigger_generation(
        self, api_client, tenant, website_asset, user_factory
    ):
        from apps.tenants.models import Membership

        reader = user_factory(email="reader@example.com", password=PASSWORD)
        Membership.all_objects.create(tenant=tenant, user=reader, role=Membership.Role.READER)
        headers = _auth(api_client, reader, tenant)

        response = api_client.post(reverse("breach-exposure-synthesis-refresh"), **headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestSynthesisSendsNoRealIdentifier:
    """Test de propriété (ADR-005) : on inspecte le payload EXACT transmis au
    fournisseur, pas le contexte en amont — un défaut de pseudonymisation ne
    se verrait pas autrement."""

    def _transmitted_payload(self, mock_claude) -> str:
        kwargs = mock_claude.messages.create.call_args.kwargs
        return kwargs["system"] + str(kwargs["messages"])

    def test_no_real_domain_or_email_reaches_the_provider(
        self, tenant, tenant_owner, website_asset, mock_claude
    ):
        _ingest(
            tenant,
            website_asset,
            payload={"eml": tenant_owner.email, "pwd": "SuperSecret42"},
        )

        services.refresh_exposure_synthesis(tenant)

        payload = self._transmitted_payload(mock_claude)
        assert tenant.name not in payload
        assert tenant_owner.email not in payload
        assert website_asset.value not in payload
        assert "example.com" not in payload

    def test_no_secret_reaches_the_provider_even_masked(self, tenant, website_asset, mock_claude):
        """Ni le secret en clair (évidemment), ni sa forme masquée : elle
        n'aide en rien une mise en relation et n'a rien à faire chez un
        tiers."""
        finding = _ingest(tenant, website_asset)
        services.refresh_exposure_synthesis(tenant)

        payload = self._transmitted_payload(mock_claude)
        assert "SuperSecret42" not in payload
        assert finding.secret_masked not in payload

    def test_context_still_carries_useful_signal(self, tenant, website_asset, mock_claude):
        """Le pendant du test précédent : vérifier qu'on n'a pas « réussi » à
        ne rien fuiter en n'envoyant rien d'utile."""
        _ingest(tenant, website_asset)
        services.refresh_exposure_synthesis(tenant)

        payload = self._transmitted_payload(mock_claude)
        assert "score_exposition" in payload
        assert "{{" in payload  # des placeholders, donc des valeurs bien substituées

    def test_response_is_rehydrated_before_storage(self, tenant, website_asset, mock_claude):
        """Le placeholder ne doit jamais arriver jusqu'à l'utilisateur."""
        _ingest(tenant, website_asset)
        block = mock_claude.messages.create.return_value.content[0]
        block.text = "Le domaine {{DOMAIN_1}} est concerné."

        services.refresh_exposure_synthesis(tenant)

        content = services.get_exposure_synthesis(tenant).content
        assert "{{DOMAIN_1}}" not in content
