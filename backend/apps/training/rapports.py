"""Ce que la formation donne à voir — et ce qu'elle refuse de montrer (F3).

Trois règles, posées dans le code et pas seulement dans une note :

1. **L'agrégé d'abord.** Tout ce que rend ce module est un chiffre d'ensemble.
2. **Aucun classement de salariés par score.** Un module de sensibilisation
   qui produit un palmarès devient un outil de notation, avec les conséquences
   que cela emporte en droit du travail. La liste nominative existe, mais elle
   ne porte **pas** de score : seulement un état — pas ouvert, en cours,
   terminé — c'est-à-dire strictement ce qu'il faut pour relancer.
3. **La consultation nominative est tracée.**

La question la plus utile n'est pas le taux de réussite : ce sont **les
questions les plus ratées**. Elles disent ce que l'entreprise ne maîtrise pas,
donc ce qu'il faut expliquer autrement.
"""

from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    Attempt,
    AttemptAnswer,
    Certificate,
    Enrollment,
    NominativeAccessLog,
    Question,
    ScreenProgress,
)


def _inscriptions(tenant, *, course=None):
    qs = Enrollment.all_objects.filter(tenant=tenant, revoked_at__isnull=True).select_related(
        "version", "version__course", "learner"
    )
    if course is not None:
        qs = qs.filter(version__course=course)
    return qs


def _pourcent(partie, total) -> int:
    return round(100 * partie / total) if total else 0


def agregats(tenant, *, course=None) -> dict:
    """Participation, réussite, score moyen. Rien de nominatif."""
    inscriptions = list(_inscriptions(tenant, course=course))
    total = len(inscriptions)
    identifiants = [i.id for i in inscriptions]

    commences = set(
        ScreenProgress.all_objects.filter(
            tenant=tenant, enrollment_id__in=identifiants
        ).values_list("enrollment_id", flat=True)
    )
    reussis = set(
        Certificate.all_objects.filter(tenant=tenant, enrollment_id__in=identifiants).values_list(
            "enrollment_id", flat=True
        )
    )
    # « Ouvert mais pas commencé » compte comme non commencé : ouvrir un lien
    # n'est pas suivre un cours, et comptabiliser l'ouverture gonflerait la
    # participation sans que personne n'ait rien appris.
    en_cours = commences - reussis
    jamais = total - len(commences)

    tentatives = list(Attempt.all_objects.filter(tenant=tenant, enrollment_id__in=identifiants))
    scores = [t.score for t in tentatives]

    return {
        "learners_total": total,
        "not_started": jamais,
        "in_progress": len(en_cours),
        "completed": len(reussis),
        "participation_rate": _pourcent(len(commences), total),
        "success_rate": _pourcent(len(reussis), total),
        # Moyenne sur les TENTATIVES, pas sur les salariés : un salarié qui
        # repasse le quiz pèse ses deux notes, ce qui est le reflet honnête de
        # ce qui s'est passé.
        "average_score": round(sum(scores) / len(scores)) if scores else None,
        "attempts_total": len(tentatives),
    }


def questions_les_plus_ratees(tenant, *, course=None, limite=5) -> list[dict]:
    """Ce que l'entreprise ne maîtrise pas.

    Seules les questions ayant reçu au moins trois réponses sont retenues :
    une question ratée une fois sur une tentative ne dit rien, et la mettre en
    tête induirait en erreur. Le seuil a aussi un effet de discrétion — sur
    une ou deux réponses, on désignerait quelqu'un.
    """
    reponses = AttemptAnswer.all_objects.filter(tenant=tenant)
    if course is not None:
        reponses = reponses.filter(attempt__enrollment__version__course=course)

    compte = (
        reponses.values("question_id")
        .annotate(total=Count("id"), ratees=Count("id", filter=Q(is_correct=False)))
        .filter(total__gte=3)
    )
    par_question = {ligne["question_id"]: ligne for ligne in compte}
    if not par_question:
        return []

    questions = Question.objects.filter(id__in=par_question).select_related(
        "screen", "version__course"
    )
    lignes = [
        {
            "question_id": str(question.id),
            "text": question.text,
            "course_title": question.version.course.title,
            "screen_title": question.screen.title,
            "screen_order": question.screen.order,
            "answers": par_question[question.id]["total"],
            "failed": par_question[question.id]["ratees"],
            "failure_rate": _pourcent(
                par_question[question.id]["ratees"], par_question[question.id]["total"]
            ),
        }
        for question in questions
    ]
    lignes.sort(key=lambda ligne: (-ligne["failure_rate"], -ligne["answers"]))
    return lignes[:limite]


def campagnes(tenant) -> list[dict]:
    """L'évolution, campagne après campagne.

    Une **campagne** n'est pas une table : c'est un cours et une échéance. Le
    couple suffit à distinguer « la sensibilisation de mars » de « celle de
    septembre », et éviter une table de plus évite surtout d'avoir à la tenir
    à jour.
    """
    groupes = {}
    for inscription in _inscriptions(tenant):
        cle = (inscription.version.course_id, inscription.due_date)
        groupes.setdefault(
            cle,
            {
                "course_id": str(inscription.version.course_id),
                "course_title": inscription.version.course.title,
                "due_date": inscription.due_date,
                "enrollments": [],
            },
        )["enrollments"].append(inscription.id)

    lignes = []
    for groupe in groupes.values():
        identifiants = groupe.pop("enrollments")
        total = len(identifiants)
        commences = (
            ScreenProgress.all_objects.filter(tenant=tenant, enrollment_id__in=identifiants)
            .values("enrollment_id")
            .distinct()
            .count()
        )
        reussis = Certificate.all_objects.filter(
            tenant=tenant, enrollment_id__in=identifiants
        ).count()
        lignes.append(
            {
                **groupe,
                "learners_total": total,
                "participation_rate": _pourcent(commences, total),
                "success_rate": _pourcent(reussis, total),
            }
        )
    lignes.sort(key=lambda ligne: ligne["due_date"])
    return lignes


def suivi_nominatif(tenant, *, actor=None, course=None) -> list[dict]:
    """Qui relancer. **Sans score, et tracé.**

    Le score n'y figure pas, et ce n'est pas un oubli : il n'est d'aucune
    utilité pour relancer quelqu'un, et sa présence transformerait cette liste
    en classement dès qu'un tableur s'en emparerait.
    """
    inscriptions = list(_inscriptions(tenant, course=course))
    identifiants = [i.id for i in inscriptions]
    commences = set(
        ScreenProgress.all_objects.filter(
            tenant=tenant, enrollment_id__in=identifiants
        ).values_list("enrollment_id", flat=True)
    )
    reussis = set(
        Certificate.all_objects.filter(tenant=tenant, enrollment_id__in=identifiants).values_list(
            "enrollment_id", flat=True
        )
    )

    lignes = []
    for inscription in inscriptions:
        if inscription.id in reussis:
            etat = "termine"
        elif inscription.id in commences:
            etat = "en_cours"
        else:
            etat = "pas_commence"
        lignes.append(
            {
                "enrollment_id": str(inscription.id),
                "full_name": inscription.learner.full_name,
                "email": inscription.learner.email,
                "course_title": inscription.version.course.title,
                "due_date": inscription.due_date,
                "state": etat,
                "overdue": inscription.due_date < timezone.localdate() and etat != "termine",
            }
        )

    NominativeAccessLog.objects.create(tenant=tenant, actor=actor, course=course, rows=len(lignes))
    # Tri par état puis par nom : jamais par résultat.
    ordre = {"pas_commence": 0, "en_cours": 1, "termine": 2}
    lignes.sort(key=lambda ligne: (ordre[ligne["state"]], ligne["full_name"]))
    return lignes


def rapport(tenant, *, course=None) -> dict:
    """Le rapport complet, tel qu'il est servi et exporté."""
    return {
        "tenant_name": tenant.name,
        "course_title": course.title if course else "Tous les cours",
        "generated_at": timezone.now(),
        "summary": agregats(tenant, course=course),
        "hardest_questions": questions_les_plus_ratees(tenant, course=course),
        "campaigns": campagnes(tenant),
    }
