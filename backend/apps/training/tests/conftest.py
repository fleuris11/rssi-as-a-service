"""Un cours minuscule et entièrement contrôlé.

Trois écrans et quatre questions : assez pour que la reprise, le seuil et la
révision ciblée aient un sens, assez peu pour que chaque arithmétique de test
se vérifie de tête. Le cours de démonstration (7 écrans, 6 questions) est
testé séparément, par sa propre commande.

Le seuil est fixé à 75 % sur quatre questions : une erreur donne 75 % et passe
tout juste, deux erreurs donnent 50 % et échouent. C'est le réglage qui rend
la frontière visible dans les tests.
"""

import pytest

from apps.training import services
from apps.training.models import Choice, Course, CourseVersion, Question, Screen


@pytest.fixture
def cours(db):
    cours = Course.objects.create(
        slug="cours-test", title="Cours de test", summary="Trois écrans, quatre questions."
    )
    version = CourseVersion.objects.create(
        course=cours, number=1, pass_threshold=75, max_attempts=2, published_at="2026-09-01T08:00Z"
    )
    ecrans = [
        Screen.objects.create(
            version=version,
            order=rang,
            title=f"Écran {rang}",
            content=[{"type": "paragraphe", "texte": f"Contenu de l'écran {rang}."}],
            estimated_seconds=60,
        )
        for rang in (1, 2, 3)
    ]
    for rang in (1, 2, 3, 4):
        # Les questions 1 et 2 portent sur l'écran 1, la 3 sur l'écran 2, la 4
        # sur l'écran 3 : deux questions sur un même écran permettent de
        # vérifier que la liste des écrans à revoir ne le cite pas deux fois.
        ecran = ecrans[0] if rang in (1, 2) else ecrans[rang - 2]
        question = Question.objects.create(
            version=version,
            order=rang,
            text=f"Question {rang} ?",
            kind=Question.Kind.SINGLE,
            explanation=f"Parce que c'est ainsi, pour la question {rang}.",
            screen=ecran,
        )
        Choice.objects.create(question=question, order=1, text="Bonne", is_correct=True)
        Choice.objects.create(question=question, order=2, text="Mauvaise", is_correct=False)
    return cours


@pytest.fixture
def version(cours):
    return cours.published_version


@pytest.fixture
def salarie(tenant, tenant_owner, cours):
    with services.contexte_du_client(tenant):
        services.attribuer_cours(tenant=tenant, course=cours, actor=tenant_owner)
        return services.creer_apprenant(
            tenant=tenant,
            full_name="Camille Martin",
            email="camille.martin@exemple.fr",
            actor=tenant_owner,
        )


@pytest.fixture
def inscription_et_jeton(tenant, tenant_owner, salarie, cours):
    """L'inscription et son jeton en clair — qui n'existe qu'ici, comme en
    production il n'existe que dans la réponse de création."""
    from datetime import date, timedelta

    with services.contexte_du_client(tenant):
        return services.inscrire(
            tenant=tenant,
            learner=salarie,
            course=cours,
            due_date=date.today() + timedelta(days=14),
            actor=tenant_owner,
        )


@pytest.fixture
def inscription(inscription_et_jeton):
    return inscription_et_jeton[0]


@pytest.fixture
def jeton(inscription_et_jeton):
    return inscription_et_jeton[1]


@pytest.fixture
def bonnes_reponses(version):
    """{question: [bon choix]} — de quoi réussir sans recopier la structure
    dans chaque test."""

    def construire(fausses=()):
        reponses = {}
        for question in version.questions.prefetch_related("choices").order_by("order"):
            choix = sorted(question.choices.all(), key=lambda c: c.order)
            voulu = choix[1] if question.order in fausses else choix[0]
            reponses[str(question.id)] = [str(voulu.id)]
        return reponses

    return construire
