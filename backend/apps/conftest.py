"""Fixtures shared by apps.assessments and apps.actions tests: a small,
fully-controlled referential (2 domains, 4 measures — one standard/one
renforcé per domain) so scoring math in tests is easy to hand-verify,
instead of the real 42-measure ANSSI fixture (covered separately by
apps/assessments/tests/test_management_commands.py).

Depuis V2-4 (ADR-029), un référentiel doit être **attribué** à un client pour
qu'il puisse produire dessus. Les deux fixtures se rattrapent l'une l'autre
(``referential`` attribue aux tenants déjà là, ``tenant_factory`` attribue les
référentiels déjà là) : l'ordre d'instanciation des fixtures dépend de la
signature de chaque test, et faire dépendre l'une de l'autre aurait forcé
tous les tests de tenant à charger un référentiel dont ils n'ont que faire.
Résultat : les tests écrits avant V2-4 voient le monde qu'ils voyaient — tout
client a accès au référentiel chargé. Ceux qui testent l'attribution
elle-même la manipulent explicitement.
"""

import pytest

from apps.assessments import services as assessments_services
from apps.assessments.models import Assessment, Domain, Measure, Referential
from apps.tenants.models import Tenant


def _attribuer(tenant, referential):
    assessments_services.assign_referential(tenant=tenant, referential=referential)


@pytest.fixture
def referential(db):
    ref = Referential.objects.create(
        slug="test-referential", name="Référentiel de test", version="1.0"
    )
    domain_a = Domain.objects.create(referential=ref, code="domaine-a", name="Domaine A", order=1)
    domain_b = Domain.objects.create(referential=ref, code="domaine-b", name="Domaine B", order=2)

    Measure.objects.create(
        referential=ref,
        domain=domain_a,
        code="1",
        number=1,
        order=1,
        official_title="Mesure standard à fort impact, faible effort",
        plain_language="Mesure 1 ?",
        level=Measure.Level.STANDARD,
        weight=1.0,
        effort=Measure.Effort.LOW,
        impact=Measure.Impact.HIGH,
    )
    Measure.objects.create(
        referential=ref,
        domain=domain_a,
        code="2",
        number=2,
        order=2,
        official_title="Mesure renforcée à impact moyen, effort moyen",
        plain_language="Mesure 2 ?",
        level=Measure.Level.RENFORCE,
        weight=0.5,
        effort=Measure.Effort.MEDIUM,
        impact=Measure.Impact.MEDIUM,
    )
    Measure.objects.create(
        referential=ref,
        domain=domain_b,
        code="3",
        number=3,
        order=1,
        official_title="Mesure standard à faible impact, effort moyen",
        plain_language="Mesure 3 ?",
        level=Measure.Level.STANDARD,
        weight=1.0,
        effort=Measure.Effort.MEDIUM,
        impact=Measure.Impact.LOW,
    )
    Measure.objects.create(
        referential=ref,
        domain=domain_b,
        code="4",
        number=4,
        order=2,
        official_title="Mesure renforcée à fort impact, fort effort",
        plain_language="Mesure 4 ?",
        level=Measure.Level.RENFORCE,
        weight=0.5,
        effort=Measure.Effort.HIGH,
        impact=Measure.Impact.HIGH,
    )
    for tenant in Tenant.objects.all():
        _attribuer(tenant, ref)
    return ref


@pytest.fixture
def second_referential(db):
    """Un deuxième référentiel, volontairement dissemblable du premier : un
    seul domaine, deux mesures, des poids égaux. C'est ce qu'il faut pour que
    les tests de consolidation portent sur deux choses qui ne se ressemblent
    pas — consolider deux copies du même référentiel ne prouverait rien."""
    ref = Referential.objects.create(
        slug="autre-referentiel",
        name="Autre référentiel",
        version="2024",
        kind=Referential.Kind.LICENSED,
        publisher="Organisme tiers",
        licence_notice="Contenu importé par l'exploitant.",
    )
    domain = Domain.objects.create(referential=ref, code="gouvernance", name="Gouvernance", order=1)
    for position, code in enumerate(["A.1", "A.2"], start=1):
        Measure.objects.create(
            referential=ref,
            domain=domain,
            code=code,
            order=position,
            official_title=f"Contrôle {code}",
            plain_language=f"Question {code} ?",
            level="",
            weight=1.0,
            effort=Measure.Effort.MEDIUM,
            impact=Measure.Impact.MEDIUM,
        )
    for tenant in Tenant.objects.all():
        _attribuer(tenant, ref)
    return ref


@pytest.fixture
def subset_factory(db):
    """Compose un sous-ensemble à partir d'un référentiel déjà chargé."""

    def make(referential, codes, *, slug="essentiel", name="Essentiel", owner_tenant=None):
        return assessments_services.create_subset(
            referential=referential,
            slug=slug,
            name=name,
            measure_codes=codes,
            owner_tenant=owner_tenant,
        )

    return make


@pytest.fixture
def tenant_factory(tenant_factory):
    """Surcharge la fabrique racine : tout client créé dans les tests reçoit
    les référentiels déjà chargés."""

    def make(owner, name="Entreprise Test", **kwargs):
        tenant = tenant_factory(owner, name=name, **kwargs)
        for referential in Referential.objects.filter(is_active=True):
            _attribuer(tenant, referential)
        return tenant

    return make


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
