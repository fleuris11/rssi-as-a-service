"""Phase 8B, tâche 2 — la couche de vulgarisation.

Ces tests sont autant éditoriaux que fonctionnels : la valeur produit tient
au fait que chaque type de fuite ait une explication **spécifique** et une
action **concrète**, pas une paraphrase générique. Un test qui vérifierait
seulement « la clé existe » laisserait passer une entrée vide de sens.
"""

import pytest

from apps.threat_intelligence import plain_language
from apps.threat_intelligence.models import BreachFinding

pytestmark = pytest.mark.django_db


def _finding(tenant, asset, endpoint, finding_type="test"):
    return BreachFinding.all_objects.create(
        tenant=tenant,
        asset=asset,
        source_endpoint=endpoint,
        finding_type=finding_type,
        severity=BreachFinding.Severity.HIGH,
        dedup_hash=f"hash-{endpoint}-{finding_type}",
    )


class TestEditorialCoverage:
    def test_every_source_endpoint_has_an_entry(self):
        covered = set(plain_language.all_explanations())
        for endpoint in BreachFinding.SourceEndpoint.values:
            assert endpoint in covered, f"vulgarisation manquante pour {endpoint}"

    @pytest.mark.parametrize("endpoint", BreachFinding.SourceEndpoint.values)
    def test_each_entry_is_a_real_sentence_with_a_real_action(self, endpoint):
        entry = plain_language.all_explanations()[endpoint]
        assert len(entry["meaning"]) > 60
        assert len(entry["action"]) > 40
        assert entry["meaning"].endswith(".")
        assert entry["action"].endswith(".")

    @pytest.mark.parametrize("endpoint", BreachFinding.SourceEndpoint.values)
    def test_no_unexplained_jargon(self, endpoint):
        """Le ton exigé : zéro terme technique laissé nu. « stealer »,
        « combo list », « credential stuffing » n'ont aucun sens pour un
        dirigeant de TPE."""
        entry = plain_language.all_explanations()[endpoint]
        text = f"{entry['meaning']} {entry['action']}".lower()
        for jargon in ("stealer", "combo list", "credential stuffing", "infostealer", "payload"):
            assert jargon not in text

    @pytest.mark.parametrize("endpoint", BreachFinding.SourceEndpoint.values)
    def test_uses_formal_address(self, endpoint):
        """Vouvoiement : le tutoiement passerait mal auprès de la cible."""
        entry = plain_language.all_explanations()[endpoint]
        text = f"{entry['meaning']} {entry['action']}".lower()
        for informal in (" tu ", " ton ", " tes ", "peux-tu"):
            assert informal not in text


class TestSpecificExplanations:
    def test_sessions_explains_the_mfa_bypass(self, tenant, website_asset):
        """Le point qui fait la différence sur ce cas : le cookie contourne
        le mot de passe ET la double authentification."""
        finding = _finding(tenant, website_asset, BreachFinding.SourceEndpoint.SESSIONS)
        explanation = plain_language.explain(finding)

        assert "cookie de session" in explanation["meaning"]
        assert "double authentification" in explanation["meaning"]
        assert "déconnect" in explanation["action"].lower()

    def test_nhi_explains_unmonitored_machine_access(self, tenant, website_asset):
        finding = _finding(tenant, website_asset, BreachFinding.SourceEndpoint.NHI)
        explanation = plain_language.explain(finding)

        assert "programme" in explanation["meaning"] or "machine" in explanation["meaning"]
        assert "permanent" in explanation["meaning"]
        assert "révoqu" in explanation["action"].lower()

    def test_stealer_explains_the_infected_machine_and_reuse(self, tenant, website_asset):
        finding = _finding(tenant, website_asset, BreachFinding.SourceEndpoint.STEALER)
        explanation = plain_language.explain(finding)

        assert "infect" in explanation["meaning"].lower()
        assert "réutilis" in explanation["action"].lower()

    def test_docs_mentions_the_regulatory_deadline(self, tenant, website_asset):
        """Un document fuité peut contenir des données clients : le délai de
        72 h est l'information la plus actionnable pour un dirigeant."""
        finding = _finding(tenant, website_asset, BreachFinding.SourceEndpoint.DOCS)
        assert "72" in plain_language.explain(finding)["action"]


class TestSubtypes:
    def test_asm_phishing_gets_its_own_urgent_explanation(self, tenant, website_asset):
        phishing = _finding(
            tenant,
            website_asset,
            BreachFinding.SourceEndpoint.ASM,
            finding_type=plain_language.ASM_PHISHING_TYPE,
        )
        inventory = _finding(
            tenant, website_asset, BreachFinding.SourceEndpoint.ASM, finding_type="mx"
        )

        phishing_text = plain_language.explain(phishing)
        assert phishing_text != plain_language.explain(inventory)
        assert "faux email" in phishing_text["meaning"]
        assert "comptabilité" in phishing_text["action"]

    def test_unknown_endpoint_falls_back_rather_than_raising(self, tenant, website_asset):
        finding = _finding(tenant, website_asset, "un-endpoint-futur")
        explanation = plain_language.explain(finding)
        assert explanation["meaning"]
        assert explanation["action"]


class TestSerializerExposesExplanations:
    def test_finding_serializer_carries_meaning_and_action(self, tenant, website_asset):
        from apps.threat_intelligence.serializers import BreachFindingSerializer

        finding = _finding(tenant, website_asset, BreachFinding.SourceEndpoint.SESSIONS)
        data = BreachFindingSerializer(finding).data

        assert "double authentification" in data["meaning"]
        assert data["recommended_action"]
