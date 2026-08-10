"""Phase 8A — la notification « signal avant-coureur ». Le point à protéger
est le TON : un domaine ressemblant déposé n'est pas une fuite, et l'annoncer
comme une alerte rouge habituerait le dirigeant à ignorer les vraies. Le
message doit donc dire explicitement que rien n'a fuité.
"""

import pytest
from django.core import mail

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset
from apps.notifications import services
from apps.notifications.models import EmailLog
from apps.threat_intelligence import services as threat_intelligence_services
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db


@pytest.fixture
def website_asset(tenant, tenant_owner):
    return monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://example.com",
        ownership_confirmed=True,
    )


def _ingest(tenant, asset, endpoint, payload):
    return threat_intelligence_services.ingest_raw_findings(
        tenant=tenant, asset=asset, raw_findings=[RawFinding(endpoint=endpoint, payload=payload)]
    )[0]


@pytest.fixture
def typosquat_finding(tenant, website_asset):
    return _ingest(
        tenant,
        website_asset,
        "radar",
        {
            "data": "exemp1e-client.fr",
            "src": "Enregistrement de domaine similaire",
            "found": "2026-01-01",
        },
    )


class TestPreIncidentSignalEmail:
    def test_sends_a_calm_message_that_says_nothing_leaked_yet(self, typosquat_finding):
        services.send_pre_incident_signal_email(typosquat_finding)

        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert "Signal avant-coureur" in message.subject
        assert "n'a fuité" in message.body
        # Le ton doit se distinguer d'une vraie alerte de compromission.
        assert "🔴" not in message.subject

    def test_includes_the_plain_language_explanation_shown_in_the_app(self, typosquat_finding):
        """Même source de vérité que l'API (services.pre_incident_definition)
        — le dirigeant doit lire la même phrase dans l'email et à l'écran."""
        services.send_pre_incident_signal_email(typosquat_finding)

        definition = threat_intelligence_services.pre_incident_definition(
            threat_intelligence_services.SIGNAL_TYPOSQUAT
        )
        assert definition["plain_language"][:60] in mail.outbox[0].body

    def test_includes_the_observed_detail(self, typosquat_finding):
        services.send_pre_incident_signal_email(typosquat_finding)
        assert "exemp1e-client.fr" in mail.outbox[0].body

    def test_is_logged_under_its_own_kind(self, typosquat_finding, tenant):
        services.send_pre_incident_signal_email(typosquat_finding)

        log = EmailLog.all_objects.get(tenant=tenant)
        assert log.kind == EmailLog.Kind.PRE_INCIDENT_SIGNAL
        assert log.details["signal_type"] == threat_intelligence_services.SIGNAL_TYPOSQUAT

    def test_respects_the_realtime_alerts_preference(self, typosquat_finding, tenant):
        services.update_preferences(tenant, realtime_alerts_enabled=False)

        assert services.send_pre_incident_signal_email(typosquat_finding) is None
        assert mail.outbox == []


class TestWebhookDispatch:
    def test_webhook_delivered_signal_schedules_the_notification(
        self, tenant, website_asset, monkeypatch
    ):
        """Seul le webhook déclenche l'envoi : un scan de diagnostic remonte
        d'un coup tout l'historique de signaux, les mailer tous serait du
        bruit — la valeur ici est que quelque chose vient de CHANGER."""
        scheduled = []
        monkeypatch.setattr(
            "apps.notifications.tasks.send_pre_incident_signal_email.delay",
            lambda finding_id: scheduled.append(finding_id),
        )

        created = _ingest(
            tenant,
            website_asset,
            "darkweb",
            {"data": "example.com", "site": "ForumX", "found": "2026-01-01"},
        )
        threat_intelligence_services._notify_pre_incident_signals([created])

        assert scheduled == [created.id]

    def test_actual_breach_findings_do_not_trigger_the_pre_incident_email(
        self, tenant, website_asset, monkeypatch
    ):
        scheduled = []
        monkeypatch.setattr(
            "apps.notifications.tasks.send_pre_incident_signal_email.delay",
            lambda finding_id: scheduled.append(finding_id),
        )

        created = _ingest(tenant, website_asset, "stealer", {"usr": "a@example.com", "pwd": "x"})
        threat_intelligence_services._notify_pre_incident_signals([created])

        assert scheduled == []
