import pytest
from django.core.management import call_command

from apps.assessments.models import Domain, Measure, Referential

pytestmark = pytest.mark.django_db


def test_load_anssi_referential_creates_expected_structure():
    call_command("load_anssi_referential")

    referential = Referential.objects.get(slug="anssi-hygiene-informatique")
    assert referential.is_active is True
    assert Domain.objects.filter(referential=referential).count() == 10
    assert Measure.objects.filter(domain__referential=referential).count() == 42

    measure = Measure.objects.get(number=1)
    assert measure.domain.referential_id == referential.id
    assert measure.level in {Measure.Level.STANDARD, Measure.Level.RENFORCE}
    assert measure.effort in {Measure.Effort.LOW, Measure.Effort.MEDIUM, Measure.Effort.HIGH}
    assert measure.impact in {Measure.Impact.LOW, Measure.Impact.MEDIUM, Measure.Impact.HIGH}


def test_load_anssi_referential_is_idempotent():
    call_command("load_anssi_referential")
    call_command("load_anssi_referential")

    assert Referential.objects.filter(slug="anssi-hygiene-informatique").count() == 1
    assert Measure.objects.count() == 42


def test_load_anssi_referential_missing_file_raises(tmp_path):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("load_anssi_referential", file=tmp_path / "does-not-exist.json")


def test_load_anssi_referential_rejects_domain_mismatch(tmp_path):
    """The loader cross-checks official.domain against the parent domain's
    code — catches a data-entry mistake (measure filed under the wrong
    chapter) instead of silently loading it."""
    import json

    from django.core.management.base import CommandError

    bad_data = {
        "slug": "broken",
        "name": "Référentiel cassé",
        "version": "1.0",
        "domains": [
            {
                "code": "domaine-a",
                "order": 1,
                "name": "Domaine A",
                "measures": [
                    {
                        "official": {
                            "number": 1,
                            "title": "Mesure mal rattachée",
                            "domain": "domaine-b",
                            "level": "standard",
                        },
                        "simplified": {"question": "?"},
                        "product_rating": {"effort": "low", "impact": "low", "disclaimer": True},
                    }
                ],
            }
        ],
    }
    bad_file = tmp_path / "broken.json"
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(CommandError, match="ne correspond pas au domaine"):
        call_command("load_anssi_referential", file=bad_file)
