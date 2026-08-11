"""ADR-016 — le score d'exposition. Ce qui est testé ici n'est pas « le
calcul ne plante pas » mais les propriétés produit dont dépend la crédibilité
du chiffre devant un client : déterminisme, bornes, ordre relatif, et le fait
que traiter une fuite fasse effectivement baisser le score.
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.threat_intelligence import exposure
from apps.threat_intelligence.models import BreachFinding

pytestmark = pytest.mark.django_db


def _finding(tenant, asset, *, severity, breach_days_ago=5, has_secret=False):
    """Crée un finding réel en base — le score lit ``secret_encrypted``, un
    objet non sauvegardé passerait à côté de ce chemin."""
    return BreachFinding.all_objects.create(
        tenant=tenant,
        asset=asset,
        source_endpoint=BreachFinding.SourceEndpoint.CREDS,
        finding_type="test",
        severity=severity,
        status=BreachFinding.Status.OPEN,
        breach_date=date.today() - timedelta(days=breach_days_ago),
        has_secret=has_secret,
        secret_encrypted=b"gAAAAA-chiffre-factice" if has_secret else b"",
        dedup_hash=f"hash-{severity}-{breach_days_ago}-{has_secret}-{timezone.now().timestamp()}",
    )


class TestScoreBounds:
    def test_no_findings_scores_zero_and_is_calm(self):
        result = exposure.compute_exposure_score([])
        assert result.score == 0
        assert result.level == exposure.LEVEL_CALM
        assert result.components == []

    def test_score_never_exceeds_one_hundred(self, tenant, website_asset):
        findings = [
            _finding(tenant, website_asset, severity="critical", breach_days_ago=d, has_secret=True)
            for d in range(1, 15)
        ]
        assert exposure.compute_exposure_score(findings).score == exposure.MAX_SCORE

    def test_score_is_deterministic(self, tenant, website_asset):
        """Deux calculs sur les mêmes données donnent le même chiffre — la
        propriété qui rend le score défendable (ADR-016)."""
        findings = [
            _finding(tenant, website_asset, severity="critical", has_secret=True),
            _finding(tenant, website_asset, severity="attention", breach_days_ago=200),
        ]
        now = timezone.now()
        first = exposure.compute_exposure_score(findings, now=now)
        second = exposure.compute_exposure_score(findings, now=now)
        assert first.score == second.score
        assert [c.points for c in first.components] == [c.points for c in second.components]


class TestRelativeOrdering:
    def test_critical_outweighs_several_minor_findings(self, tenant, website_asset):
        """Le point produit : dix broutilles ne doivent pas passer devant une
        vraie fuite critique."""
        critical = [_finding(tenant, website_asset, severity="critical")]
        minor = [
            _finding(tenant, website_asset, severity="attention", breach_days_ago=d)
            for d in range(1, 11)
        ]
        assert (
            exposure.compute_exposure_score(critical).score
            > exposure.compute_exposure_score(minor).score
        )

    def test_fresh_leak_scores_higher_than_an_old_one(self, tenant, website_asset):
        fresh = [_finding(tenant, website_asset, severity="high", breach_days_ago=3)]
        old = [_finding(tenant, website_asset, severity="high", breach_days_ago=900)]
        assert (
            exposure.compute_exposure_score(fresh).score
            > exposure.compute_exposure_score(old).score
        )

    def test_revealable_secret_raises_the_score(self, tenant, website_asset):
        without = [_finding(tenant, website_asset, severity="high", has_secret=False)]
        with_secret = [_finding(tenant, website_asset, severity="high", has_secret=True)]
        assert (
            exposure.compute_exposure_score(with_secret).score
            > exposure.compute_exposure_score(without).score
        )

    def test_has_secret_flag_without_ciphertext_grants_no_bonus(self, tenant, website_asset):
        """Un finding antérieur au chiffrement (ADR-014 mise à jour) porte
        ``has_secret`` sans blob déchiffrable : il ne doit pas gagner le bonus
        d'un secret réellement récupérable."""
        finding = _finding(tenant, website_asset, severity="high", has_secret=False)
        finding.has_secret = True  # drapeau seul, secret_encrypted reste vide
        finding.save(update_fields=["has_secret"])
        baseline = _finding(tenant, website_asset, severity="high", has_secret=False)

        assert (
            exposure.compute_exposure_score([finding]).score
            == exposure.compute_exposure_score([baseline]).score
        )

    def test_additional_findings_add_less_than_the_first(self, tenant, website_asset):
        one = [_finding(tenant, website_asset, severity="high")]
        two = one + [_finding(tenant, website_asset, severity="high", breach_days_ago=6)]
        score_one = exposure.compute_exposure_score(one).score
        score_two = exposure.compute_exposure_score(two).score
        assert score_one < score_two < score_one * 2

    def test_treating_the_worst_finding_lowers_the_score(self, tenant, website_asset):
        """Le geste doit payer : si traiter une fuite ne faisait pas baisser
        le score, le dirigeant n'aurait aucune raison de le faire."""
        worst = _finding(tenant, website_asset, severity="critical", has_secret=True)
        other = _finding(tenant, website_asset, severity="attention", breach_days_ago=300)
        before = exposure.compute_exposure_score([worst, other]).score
        after = exposure.compute_exposure_score([other]).score
        assert after < before


class TestLevels:
    @pytest.mark.parametrize(
        "score,expected",
        [(0, exposure.LEVEL_CALM), (19, exposure.LEVEL_CALM), (20, exposure.LEVEL_WATCH)],
    )
    def test_watch_threshold_is_inclusive(self, score, expected):
        assert exposure.level_for(score) == expected

    @pytest.mark.parametrize(
        "score,expected",
        [
            (49, exposure.LEVEL_WATCH),
            (50, exposure.LEVEL_CONCERNING),
            (74, exposure.LEVEL_CONCERNING),
            (75, exposure.LEVEL_CRITICAL),
            (100, exposure.LEVEL_CRITICAL),
        ],
    )
    def test_upper_thresholds(self, score, expected):
        assert exposure.level_for(score) == expected

    def test_thresholds_come_from_settings_not_hardcoded(self, settings):
        settings.EXPOSURE_LEVEL_THRESHOLDS = {"watch": 5, "concerning": 10, "critical": 15}
        assert exposure.level_for(6) == exposure.LEVEL_WATCH
        assert exposure.level_for(16) == exposure.LEVEL_CRITICAL


class TestExplainability:
    def test_every_finding_contributes_one_traceable_component(self, tenant, website_asset):
        findings = [
            _finding(tenant, website_asset, severity="critical"),
            _finding(tenant, website_asset, severity="high", breach_days_ago=40),
        ]
        result = exposure.compute_exposure_score(findings)

        assert len(result.components) == 2
        assert {c.finding_id for c in result.components} == {f.id for f in findings}
        for component in result.components:
            assert component.points > 0
            assert component.detail  # le « pourquoi », jamais vide

    def test_component_detail_mentions_severity_and_freshness(self, tenant, website_asset):
        finding = _finding(tenant, website_asset, severity="critical", breach_days_ago=3)
        component = exposure.compute_exposure_score([finding]).components[0]
        assert "critique" in component.detail
        assert "moins d'un mois" in component.detail

    def test_component_detail_flags_a_recoverable_password(self, tenant, website_asset):
        finding = _finding(tenant, website_asset, severity="high", has_secret=True)
        component = exposure.compute_exposure_score([finding]).components[0]
        assert "récupérable" in component.detail


class TestFreshnessFallback:
    def test_finding_without_breach_date_uses_detection_date(self, tenant, website_asset):
        """Sans date de fuite, on retombe sur la détection — sinon une fuite
        sans date échapperait entièrement à l'amortissement de fraîcheur."""
        finding = _finding(tenant, website_asset, severity="high")
        finding.breach_date = None
        finding.save(update_fields=["breach_date"])

        result = exposure.compute_exposure_score([finding])
        assert result.score > 0
        assert "moins d'un mois" in result.components[0].detail
