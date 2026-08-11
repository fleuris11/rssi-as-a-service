"""ADR-017 — corrélation « réutilisation possible ».

Deux familles d'exigences, de nature très différente :

1. **Correction du croisement** — et surtout absence de faux positifs. Un
   faux positif ici n'est pas un détail cosmétique : le produit dirait à un
   client que deux comptes sans rapport sont liés, et le premier utilisateur
   qui le vérifie cesse de croire au reste de l'interface.

2. **Vocabulaire** — la plateforme ne teste aucun identifiant nulle part. Tout
   texte laissant entendre qu'une réutilisation est *confirmée* serait un
   mensonge sur ce que le produit fait. C'est vérifié mécaniquement ici,
   parce qu'une règle de rédaction qui ne repose que sur la vigilance humaine
   finit toujours par céder.
"""

import pytest

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset
from apps.threat_intelligence import correlation, services
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db

MEMBER_EMAIL = "owner@example.com"  # correspond à la fixture tenant_owner


def _ingest(tenant, asset, endpoint, payload):
    return services.ingest_raw_findings(
        tenant=tenant,
        asset=asset,
        raw_findings=[RawFinding(endpoint=endpoint, payload=payload)],
        tenant_emails={MEMBER_EMAIL},
    )[0]


def _correlate(tenant, findings, assets=None):
    return correlation.correlate(
        findings,
        tenant_emails={MEMBER_EMAIL},
        assets=assets if assets is not None else list(monitoring_services.list_assets(tenant)),
    )


class TestRepeatedExposure:
    def test_same_identifier_in_two_leaks_is_flagged(self, tenant, website_asset):
        first = _ingest(tenant, website_asset, "creds", {"eml": MEMBER_EMAIL, "pwd": "a"})
        second = _ingest(tenant, website_asset, "combo", {"usr": MEMBER_EMAIL, "pwd": "b"})

        signals = _correlate(tenant, [first, second])

        assert first.id in signals
        assert second.id in signals
        types = {s["signal_type"] for s in signals[first.id]}
        assert correlation.SIGNAL_REPEATED_EXPOSURE in types
        assert signals[first.id][0]["related_finding_ids"] == [second.id]

    def test_single_occurrence_is_not_flagged(self, tenant, website_asset):
        only = _ingest(tenant, website_asset, "creds", {"eml": MEMBER_EMAIL, "pwd": "a"})
        assert _correlate(tenant, [only]) == {}

    def test_identifier_matching_ignores_case_and_whitespace(self, tenant, website_asset):
        first = _ingest(tenant, website_asset, "creds", {"eml": MEMBER_EMAIL, "pwd": "a"})
        second = _ingest(
            tenant, website_asset, "combo", {"usr": f"  {MEMBER_EMAIL.upper()} ", "pwd": "b"}
        )

        signals = _correlate(tenant, [first, second])

        assert first.id in signals and second.id in signals


class TestNoFalsePositives:
    def test_similar_but_distinct_identifiers_are_not_linked(self, tenant, website_asset):
        """« paul.martin@ » et « paul.martin2@ » sont deux comptes différents."""
        first = _ingest(
            tenant, website_asset, "creds", {"eml": "paul.martin@example.com", "pwd": "a"}
        )
        second = _ingest(
            tenant, website_asset, "combo", {"usr": "paul.martin2@example.com", "pwd": "b"}
        )

        assert _correlate(tenant, [first, second]) == {}

    def test_dotted_local_parts_are_not_merged(self, tenant, website_asset):
        """Certains fournisseurs ignorent les points dans la partie locale,
        d'autres non. Les fusionner ici lierait des comptes réellement
        distincts chez la majorité des fournisseurs — on s'abstient."""
        first = _ingest(tenant, website_asset, "creds", {"eml": "j.dupont@example.com", "pwd": "a"})
        second = _ingest(tenant, website_asset, "combo", {"usr": "jdupont@example.com", "pwd": "b"})

        assert _correlate(tenant, [first, second]) == {}

    def test_masked_identifiers_are_never_used_as_a_join_key(self, tenant, website_asset):
        """Un identifiant masqué (« j.••••@ex••••.com ») est ambigu par
        construction : plusieurs comptes distincts produisent le même masque.
        S'en servir pour croiser fabriquerait des liens faux."""
        first = _ingest(tenant, website_asset, "creds", {"eml": "tiers1@autre.com", "pwd": "a"})
        second = _ingest(tenant, website_asset, "combo", {"usr": "tiers2@autre.com", "pwd": "b"})

        assert first.identifier_plain == ""  # tiers => masqué (ADR-014 §4)
        assert second.identifier_plain == ""
        assert _correlate(tenant, [first, second]) == {}

    def test_pre_incident_signals_are_not_correlated(self, tenant, website_asset):
        """Radar/dark web décrivent une exposition publique, pas un compte."""
        radar = _ingest(
            tenant,
            website_asset,
            "radar",
            {"data": "exemp1e.fr", "src": "Enregistrement de domaine similaire"},
        )
        creds = _ingest(tenant, website_asset, "creds", {"eml": MEMBER_EMAIL, "pwd": "a"})

        assert radar.id not in _correlate(tenant, [radar, creds])

    def test_is_tenant_scoped(self, api_client, user_factory, tenant_factory):
        """Deux tenants différents peuvent avoir un homonyme : jamais de
        corrélation entre eux (les findings ne sont d'ailleurs jamais
        rassemblés — épinglé ici pour que ça reste vrai)."""
        owner_a = user_factory(email="a@example.com")
        tenant_a = tenant_factory(owner_a, name="A")
        asset_a = monitoring_services.create_asset(
            tenant=tenant_a,
            user=owner_a,
            type=Asset.Type.WEBSITE,
            value="https://a.example.com",
            ownership_confirmed=True,
        )
        owner_b = user_factory(email="b@example.com")
        tenant_b = tenant_factory(owner_b, name="B")
        asset_b = monitoring_services.create_asset(
            tenant=tenant_b,
            user=owner_b,
            type=Asset.Type.WEBSITE,
            value="https://b.example.com",
            ownership_confirmed=True,
        )
        services.ingest_raw_findings(
            tenant=tenant_a,
            asset=asset_a,
            raw_findings=[
                RawFinding(endpoint="creds", payload={"eml": "x@shared.com", "pwd": "a"})
            ],
            tenant_emails={"x@shared.com"},
        )
        services.ingest_raw_findings(
            tenant=tenant_b,
            asset=asset_b,
            raw_findings=[
                RawFinding(endpoint="combo", payload={"usr": "x@shared.com", "pwd": "b"})
            ],
            tenant_emails={"x@shared.com"},
        )

        feed_a = services.build_exposure_feed(tenant_a)
        signals = [s for g in feed_a["assets"] for s in g["reuse_signals"]]
        assert signals == []


class TestExternalServiceSignal:
    def test_member_email_leaked_from_an_external_service_is_flagged(self, tenant, website_asset):
        finding = _ingest(
            tenant,
            website_asset,
            "creds",
            {"eml": MEMBER_EMAIL, "pwd": "a", "dom": "boutique-externe.example"},
        )

        signals = _correlate(tenant, [finding])

        types = {s["signal_type"] for s in signals[finding.id]}
        assert correlation.SIGNAL_EXTERNAL_SERVICE in types

    def test_leak_from_the_tenants_own_domain_is_not_external(self, tenant, tenant_owner):
        own = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="example.com",
            ownership_confirmed=True,
        )
        finding = _ingest(
            tenant, own, "creds", {"eml": MEMBER_EMAIL, "pwd": "a", "dom": "example.com"}
        )

        signals = _correlate(tenant, [finding], assets=[own])

        types = {s["signal_type"] for s in signals.get(finding.id, [])}
        assert correlation.SIGNAL_EXTERNAL_SERVICE not in types

    def test_subdomain_of_the_tenant_is_not_external(self, tenant, tenant_owner):
        own = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="example.com",
            ownership_confirmed=True,
        )
        finding = _ingest(
            tenant, own, "creds", {"eml": MEMBER_EMAIL, "pwd": "a", "dom": "intranet.example.com"}
        )

        signals = _correlate(tenant, [finding], assets=[own])

        types = {s["signal_type"] for s in signals.get(finding.id, [])}
        assert correlation.SIGNAL_EXTERNAL_SERVICE not in types

    def test_non_member_identifier_does_not_trigger_the_external_signal(
        self, tenant, website_asset
    ):
        finding = _ingest(
            tenant,
            website_asset,
            "creds",
            {"eml": "inconnu@ailleurs.com", "pwd": "a", "dom": "boutique-externe.example"},
        )
        types = {s["signal_type"] for s in _correlate(tenant, [finding]).get(finding.id, [])}
        assert correlation.SIGNAL_EXTERNAL_SERVICE not in types


class TestVocabulary:
    """La règle qui protège la promesse produit : jamais laisser croire qu'une
    réutilisation a été vérifiée."""

    FORBIDDEN = (
        "confirmé",
        "confirmée",
        "avéré",
        "avérée",
        "compromis",
        "compromise",
        "accès validé",
        "vérifié que",
        "prouvé",
    )
    REQUIRED_HEDGE = ("possible", "pourrait", "à vérifier", "hypothèse")

    @pytest.mark.parametrize("signal_type", list(correlation.SIGNAL_DEFINITIONS))
    def test_no_wording_claims_a_confirmed_reuse(self, signal_type):
        definition = correlation.SIGNAL_DEFINITIONS[signal_type]
        text = f"{definition['label']} {definition['explanation']}".lower()
        for banned in self.FORBIDDEN:
            assert banned not in text, f"vocabulaire interdit « {banned} » dans {signal_type}"

    @pytest.mark.parametrize("signal_type", list(correlation.SIGNAL_DEFINITIONS))
    def test_wording_marks_the_finding_as_a_hypothesis(self, signal_type):
        definition = correlation.SIGNAL_DEFINITIONS[signal_type]
        text = f"{definition['label']} {definition['explanation']}".lower()
        assert any(hedge in text for hedge in self.REQUIRED_HEDGE)

    @pytest.mark.parametrize("signal_type", list(correlation.SIGNAL_DEFINITIONS))
    def test_explanation_says_how_to_settle_it(self, signal_type):
        """L'utilisateur doit savoir comment lever l'hypothèse, sinon le
        signal est anxiogène sans être actionnable."""
        explanation = correlation.SIGNAL_DEFINITIONS[signal_type]["explanation"].lower()
        assert "vérifier" in explanation

    def test_the_product_states_it_does_not_test_credentials(self):
        explanation = correlation.SIGNAL_DEFINITIONS[correlation.SIGNAL_REPEATED_EXPOSURE][
            "explanation"
        ].lower()
        assert "nous ne testons aucun identifiant" in explanation


class TestRevealRecommendation:
    def test_recommends_reveal_when_the_password_is_available(self, tenant, website_asset):
        finding = _ingest(tenant, website_asset, "creds", {"eml": MEMBER_EMAIL, "pwd": "a"})
        text = correlation.recommended_verification(finding)
        assert "révéler" in text.lower()
        assert "tracé" in text  # rappel que l'accès est journalisé

    def test_falls_back_when_the_password_was_purged(self, tenant, website_asset):
        finding = _ingest(tenant, website_asset, "creds", {"eml": MEMBER_EMAIL, "pwd": "a"})
        finding.has_secret = False
        finding.secret_encrypted = b""
        finding.save(update_fields=["has_secret", "secret_encrypted"])

        text = correlation.recommended_verification(finding)
        assert "révéler" not in text.lower()
        assert "personne concernée" in text


class TestFeedIntegration:
    def test_reuse_signals_reach_the_feed_and_enrich_the_action(self, tenant, website_asset):
        _ingest(tenant, website_asset, "creds", {"eml": MEMBER_EMAIL, "pwd": "a"})
        _ingest(tenant, website_asset, "combo", {"usr": MEMBER_EMAIL, "pwd": "b"})

        feed = services.build_exposure_feed(tenant)
        group = feed["assets"][0]

        assert group["reuse_signals"]
        flagged = [f for f in group["findings"] if f["reuse_signals"]]
        assert flagged
        assert "révéler" in flagged[0]["recommended_action"].lower()
