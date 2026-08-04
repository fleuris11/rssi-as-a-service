"""Fixtures shared by apps.assessments and apps.actions tests: a small,
fully-controlled referential (2 domains, 4 measures — one standard/one
renforcé per domain) so scoring math in tests is easy to hand-verify,
instead of the real 42-measure ANSSI fixture (covered separately by
apps/assessments/tests/test_management_commands.py)."""

import pytest

from apps.assessments.models import Assessment, Domain, Measure, Referential


@pytest.fixture
def referential(db):
    ref = Referential.objects.create(
        slug="test-referential", name="Référentiel de test", version="1.0"
    )
    domain_a = Domain.objects.create(referential=ref, code="domaine-a", name="Domaine A", order=1)
    domain_b = Domain.objects.create(referential=ref, code="domaine-b", name="Domaine B", order=2)

    Measure.objects.create(
        domain=domain_a,
        code="M1",
        order=1,
        official_title="Mesure standard à fort impact, faible effort",
        plain_language="Mesure 1 ?",
        level=Measure.Level.STANDARD,
        effort=Measure.Effort.LOW,
        impact=Measure.Impact.HIGH,
    )
    Measure.objects.create(
        domain=domain_a,
        code="M2",
        order=2,
        official_title="Mesure renforcée à impact moyen, effort moyen",
        plain_language="Mesure 2 ?",
        level=Measure.Level.RENFORCE,
        effort=Measure.Effort.MEDIUM,
        impact=Measure.Impact.MEDIUM,
    )
    Measure.objects.create(
        domain=domain_b,
        code="M3",
        order=1,
        official_title="Mesure standard à faible impact, effort moyen",
        plain_language="Mesure 3 ?",
        level=Measure.Level.STANDARD,
        effort=Measure.Effort.MEDIUM,
        impact=Measure.Impact.LOW,
    )
    Measure.objects.create(
        domain=domain_b,
        code="M4",
        order=2,
        official_title="Mesure renforcée à fort impact, fort effort",
        plain_language="Mesure 4 ?",
        level=Measure.Level.RENFORCE,
        effort=Measure.Effort.HIGH,
        impact=Measure.Impact.HIGH,
    )
    return ref


@pytest.fixture
def tenant_owner(user_factory):
    return user_factory(email="owner@example.com")


@pytest.fixture
def tenant(tenant_owner, tenant_factory):
    return tenant_factory(tenant_owner)


@pytest.fixture
def assessment(referential, tenant, tenant_owner):
    return Assessment.all_objects.create(
        tenant=tenant, referential=referential, started_by=tenant_owner
    )
