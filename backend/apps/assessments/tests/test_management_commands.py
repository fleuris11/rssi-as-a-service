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

    measure = Measure.objects.get(code="H1")
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
