"""Quand la formation prouve une mesure du diagnostic (F3, ADR-041).

Le guide d'hygiène de l'ANSSI comporte une mesure de sensibilisation des
utilisateurs. Aujourd'hui, un client y répond « oui » sans rien à l'appui —
et c'est vrai de la plupart des questionnaires de conformité.

Une campagne de formation terminée, elle, **est** la preuve : des salariés
nommés, des dates, un taux de participation, un taux de réussite. Ce module
fait le lien.

**Une proposition, jamais une validation.** Le produit refuse depuis le début
de cocher une case de conformité à la place de quelqu'un : une mesure
renseignée sans qu'une personne l'ait décidée est une affirmation que le
client n'a pas faite, et qu'il découvrirait devant un auditeur. On propose, on
montre les chiffres, et on attend.
"""

from django.db import transaction
from django.utils import timezone

from . import rapports, services
from .models import Course, Enrollment, MeasureSuggestion

#: Le référentiel et la mesure concernés. Écrits ici, pas devinés : si le
#: client n'a que ce référentiel, c'est le seul lien possible aujourd'hui.
REFERENTIEL = "anssi-hygiene-informatique"
MESURE = "2"

#: Ce qui fait d'une campagne une preuve : **un seul seuil**, et c'est voulu.
#:
#: Le premier jet en posait deux — 80 % de participation ET 80 % de réussite.
#: Une neutralisation a montré que le premier ne décidait jamais rien : le
#: taux de réussite se calcule sur l'effectif TOTAL, il est donc toujours
#: inférieur ou égal au taux de participation. Exiger 80 % de réussite exige
#: déjà, mécaniquement, 80 % de participation.
#:
#: Garder les deux aurait donné l'apparence d'un contrôle supplémentaire qui
#: n'existait pas — et aucun test n'aurait pu tenir le second, faute de
#: situation où il départage quoi que ce soit. Le taux de participation reste
#: relevé et figé dans la preuve : il est informatif, pas décisionnel.
SEUIL_REUSSITE = 80

#: En deçà, la campagne ne prouve rien de statistique — et « 2 salariés sur
#: 2 » désigne des personnes.
MINIMUM_SALARIES = 3


class PreuveError(services.TrainingError):
    """La preuve ne peut pas être reportée telle quelle."""


def _periode(tenant, course):
    dates = list(
        Enrollment.all_objects.filter(
            tenant=tenant, version__course=course, revoked_at__isnull=True
        ).values_list("due_date", flat=True)
    )
    return (min(dates), max(dates)) if dates else (None, None)


def campagnes_probantes(tenant) -> list[dict]:
    """Les cours dont les résultats atteignent les deux seuils."""
    probantes = []
    for cours in Course.objects.filter(
        id__in=Enrollment.all_objects.filter(tenant=tenant, revoked_at__isnull=True).values_list(
            "version__course_id", flat=True
        )
    ):
        chiffres = rapports.agregats(tenant, course=cours)
        if chiffres["learners_total"] < MINIMUM_SALARIES:
            continue
        if chiffres["success_rate"] < SEUIL_REUSSITE:
            continue
        debut, fin = _periode(tenant, cours)
        probantes.append({"course": cours, "chiffres": chiffres, "debut": debut, "fin": fin})
    return probantes


def titre_de_la_mesure(tenant) -> str:
    """Le libellé de la mesure, lu dans le référentiel du client.

    Passe par les services d'``assessments`` et jamais par ses modèles : c'est
    la règle d'architecture du projet, et elle évite surtout qu'un changement
    de structure du référentiel casse ce module en silence.
    """
    from apps.assessments import services as assessments

    evaluation = assessments.get_current_assessment(tenant)
    if evaluation is None:
        evaluation = assessments.get_latest_completed_assessment(tenant)
    if evaluation is None:
        return "Sensibiliser les utilisateurs aux bonnes pratiques élémentaires"
    for mesure in assessments.get_assessment_measures(evaluation):
        if mesure.code == MESURE:
            return mesure.official_title
    return "Sensibiliser les utilisateurs aux bonnes pratiques élémentaires"


@transaction.atomic
def proposer(tenant) -> list[MeasureSuggestion]:
    """Crée les propositions manquantes. Idempotent.

    Une proposition déjà en attente n'est pas recréée, et une proposition
    ÉCARTÉE non plus : reproposer chaque nuit ce que le client vient de
    refuser serait le transformer en automate insistant.
    """
    creees = []
    for probante in campagnes_probantes(tenant):
        cours = probante["course"]
        deja = MeasureSuggestion.objects.filter(course=cours, measure_code=MESURE).exclude(
            status=MeasureSuggestion.Status.ACCEPTED
        )
        if deja.exists():
            continue

        chiffres = probante["chiffres"]
        creees.append(
            MeasureSuggestion.objects.create(
                tenant=tenant,
                course=cours,
                referential_slug=REFERENTIEL,
                measure_code=MESURE,
                measure_title=titre_de_la_mesure(tenant),
                learners_total=chiffres["learners_total"],
                learners_done=chiffres["completed"],
                participation_rate=chiffres["participation_rate"],
                success_rate=chiffres["success_rate"],
                period_start=probante["debut"],
                period_end=probante["fin"],
            )
        )
    return creees


def texte_de_preuve(suggestion: MeasureSuggestion) -> str:
    """La phrase déposée dans la note de la mesure. C'est elle que lira
    l'auditeur — elle doit donc porter les chiffres, pas un renvoi."""
    return (
        f"Campagne de formation « {suggestion.course.title} », "
        f"du {suggestion.period_start:%d/%m/%Y} au {suggestion.period_end:%d/%m/%Y} : "
        f"{suggestion.learners_done} salarié(s) sur {suggestion.learners_total} ont terminé "
        f"({suggestion.participation_rate} % de participation, "
        f"{suggestion.success_rate} % de réussite au questionnaire). "
        f"Renseigné depuis le module de formation, confirmé par un administrateur."
    )


@transaction.atomic
def confirmer(*, suggestion: MeasureSuggestion, actor=None) -> MeasureSuggestion:
    """Reporte la preuve dans le diagnostic EN COURS du client.

    Refuse s'il n'y en a pas : écrire dans un diagnostic terminé reviendrait à
    modifier après coup un résultat déjà restitué, et en ouvrir un nouveau à la
    place du client serait précisément la décision qu'on lui laisse.
    """
    from apps.assessments import services as assessments

    if suggestion.status != MeasureSuggestion.Status.PENDING:
        raise PreuveError("Cette proposition a déjà été traitée.")

    evaluation = assessments.get_current_assessment(suggestion.tenant)
    if evaluation is None:
        raise PreuveError(
            "Aucun diagnostic n'est en cours. Ouvrez-en un, puis revenez confirmer : "
            "la preuve y sera reportée avec ses chiffres."
        )

    mesure = next(
        (m for m in assessments.get_assessment_measures(evaluation) if m.code == MESURE), None
    )
    if mesure is None:
        raise PreuveError(
            "La mesure de sensibilisation ne fait pas partie du questionnaire en cours."
        )

    assessments.submit_answer(
        assessment=evaluation,
        measure=mesure,
        value="yes",
        note=texte_de_preuve(suggestion),
    )

    suggestion.status = MeasureSuggestion.Status.ACCEPTED
    suggestion.decided_by = actor
    suggestion.decided_at = timezone.now()
    suggestion.save(update_fields=["status", "decided_by", "decided_at"])
    return suggestion


def ecarter(*, suggestion: MeasureSuggestion, actor=None) -> MeasureSuggestion:
    if suggestion.status != MeasureSuggestion.Status.PENDING:
        raise PreuveError("Cette proposition a déjà été traitée.")
    suggestion.status = MeasureSuggestion.Status.DISMISSED
    suggestion.decided_by = actor
    suggestion.decided_at = timezone.now()
    suggestion.save(update_fields=["status", "decided_by", "decided_at"])
    return suggestion


def en_attente(tenant):
    return MeasureSuggestion.objects.filter(status=MeasureSuggestion.Status.PENDING).select_related(
        "course"
    )
