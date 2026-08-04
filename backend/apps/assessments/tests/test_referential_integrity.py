"""Integrity checks for backend/data/anssi_hygiene.json and the referential
it loads into — a certification artefact (cadrage: traçabilité), so these
assert the concrete facts a reviewer would check by hand: 42 measures,
numbered 1-42 with no gap or duplicate, every required field present, and
the three layers (official/simplified/product_rating) not mixed up.
"""

import json

import pytest
from django.conf import settings
from django.core.management import call_command

from apps.assessments.models import Measure

FIXTURE_PATH = settings.BASE_DIR / "data" / "anssi_hygiene.json"

REQUIRED_META_KEYS = {
    "source",
    "document_title",
    "official_url",
    "pdf_url",
    "local_copy",
    "version",
    "publication_date",
    "license",
    "verified_on",
    "verification_report",
}

VALID_LEVELS = {"standard", "renforce"}
VALID_EFFORT_IMPACT = {"low", "medium", "high"}


@pytest.fixture(scope="module")
def raw_referential():
    with FIXTURE_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def all_measures(raw_referential):
    return [m for domain in raw_referential["domains"] for m in domain["measures"]]


class TestMetaBlock:
    def test_meta_present_with_required_keys(self, raw_referential):
        assert "meta" in raw_referential
        missing = REQUIRED_META_KEYS - raw_referential["meta"].keys()
        assert not missing, f"champs meta manquants : {missing}"

    def test_meta_points_at_the_pdf_saved_for_traceability(self, raw_referential):
        local_copy = settings.BASE_DIR.parent / raw_referential["meta"]["local_copy"]
        assert local_copy.exists(), f"PDF source introuvable : {local_copy}"
        assert local_copy.suffix == ".pdf"


class TestMeasureCount:
    def test_exactly_42_measures(self, all_measures):
        assert len(all_measures) == 42

    def test_numbers_are_unique_and_continuous_from_1_to_42(self, all_measures):
        numbers = sorted(m["official"]["number"] for m in all_measures)
        assert numbers == list(range(1, 43))

    def test_10_domains(self, raw_referential):
        assert len(raw_referential["domains"]) == 10


class TestRequiredFields:
    def test_every_measure_has_the_three_layers(self, all_measures):
        for measure in all_measures:
            assert set(measure.keys()) == {"official", "simplified", "product_rating"}, measure

    def test_official_layer_fields(self, all_measures):
        for measure in all_measures:
            official = measure["official"]
            assert set(official.keys()) == {"number", "title", "domain", "level"}
            assert isinstance(official["number"], int)
            assert official["title"], "intitulé officiel vide"
            assert official["domain"], "domaine manquant"
            assert official["level"] in VALID_LEVELS

    def test_simplified_layer_fields(self, all_measures):
        for measure in all_measures:
            simplified = measure["simplified"]
            assert set(simplified.keys()) == {"question"}
            assert simplified["question"].strip(), "reformulation vide"

    def test_product_rating_layer_fields(self, all_measures):
        for measure in all_measures:
            rating = measure["product_rating"]
            assert set(rating.keys()) == {"effort", "impact", "disclaimer"}
            assert rating["effort"] in VALID_EFFORT_IMPACT
            assert rating["impact"] in VALID_EFFORT_IMPACT
            assert rating["disclaimer"] is True, (
                "product_rating.disclaimer doit être vrai : effort/impact ne sont "
                "pas une donnée ANSSI, voir docs/verification_referentiel_anssi.md"
            )


class TestDomainConsistency:
    def test_measure_official_domain_matches_its_parent_domain(self, raw_referential):
        for domain in raw_referential["domains"]:
            for measure in domain["measures"]:
                assert measure["official"]["domain"] == domain["code"], (
                    f"mesure {measure['official']['number']} rattachée à "
                    f"{measure['official']['domain']!r} mais imbriquée sous "
                    f"{domain['code']!r}"
                )

    def test_domain_codes_are_unique(self, raw_referential):
        codes = [d["code"] for d in raw_referential["domains"]]
        assert len(codes) == len(set(codes))


class TestKnownRenforceMeasures:
    """Regression guard for the finding in
    docs/verification_referentiel_anssi.md: only measures 38, 41 and 42 are
    presented by the guide without a "standard" baseline at all (audits
    réguliers, analyse de risques formelle, produits qualifiés ANSSI) — a
    future edit that silently changes this should fail loudly, not slip
    through as a plain data tweak."""

    def test_renforce_only_measures_are_38_41_42(self, all_measures):
        renforce_numbers = {
            m["official"]["number"] for m in all_measures if m["official"]["level"] == "renforce"
        }
        assert renforce_numbers == {38, 41, 42}


@pytest.mark.django_db
class TestLoadedReferentialIntegrity:
    """Same invariants, checked against the database after the management
    command has run — catches a bug in the loader itself, not just the JSON."""

    def test_loaded_measures_match_json_exactly(self, all_measures):
        call_command("load_anssi_referential")

        assert Measure.objects.count() == 42
        numbers_in_db = set(Measure.objects.values_list("number", flat=True))
        assert numbers_in_db == set(range(1, 43))

        for measure in all_measures:
            official = measure["official"]
            db_measure = Measure.objects.get(number=official["number"])
            assert db_measure.official_title == official["title"]
            assert db_measure.level == official["level"]
            assert db_measure.domain.code == official["domain"]
            assert db_measure.plain_language == measure["simplified"]["question"]
            assert db_measure.effort == measure["product_rating"]["effort"]
            assert db_measure.impact == measure["product_rating"]["impact"]
            assert db_measure.effort_impact_disclaimer is True
