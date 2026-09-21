"""Composer un cours (F2, ADR-040).

Deux auteurs possibles, et une seule mécanique : l'exploitant écrit les cours
de la bibliothèque, un client écrit les siens. La différence tient dans un
seul champ — ``Course.owner_tenant`` — et non dans deux jeux de fonctions.

La règle qui commande le reste : **un cours publié ne se modifie pas.**
Corriger une phrase pendant qu'un salarié suit le cours décalerait ses écrans
sous ses yeux et, pire, invaliderait la progression déjà enregistrée : une
ligne de progression désigne un écran, et l'écran aurait changé de sens. On
crée donc une nouvelle version, et les inscriptions en cours restent sur la
leur (ADR-039, décision 2).
"""

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.billing import entitlements, features

from . import blocks as blocs_de_contenu
from .models import (
    QUESTIONS_MINIMUM_POUR_UN_SEUIL,
    Choice,
    Course,
    CourseVersion,
    Question,
    Screen,
)


class StudioError(Exception):
    """Refus métier du studio. Jamais un 500."""


class VersionVerrouillee(StudioError):
    """On a tenté d'écrire dans une version déjà publiée."""


def peut_composer(*, tenant=None, user=None) -> bool:
    """Qui a le droit d'écrire un cours.

    L'administrateur plateforme, toujours : c'est lui qui alimente la
    bibliothèque. Un client, seulement si son offre comprend le studio.
    """
    if user is not None and getattr(user, "is_staff", False):
        return True
    if tenant is None:
        return False
    return entitlements.has_feature(tenant, features.TRAINING_STUDIO)


def _slug_libre(titre: str) -> str:
    base = slugify(titre)[:70] or "cours"
    candidat = base
    suffixe = 2
    while Course.objects.filter(slug=candidat).exists():
        candidat = f"{base}-{suffixe}"
        suffixe += 1
    return candidat


def _version_modifiable(version: CourseVersion) -> CourseVersion:
    if version.is_published:
        raise VersionVerrouillee(
            "Cette version est publiée : elle ne se modifie plus. Créez-en une nouvelle — "
            "les salariés en cours de parcours termineront sur celle qu'ils ont commencée."
        )
    return version


@transaction.atomic
def creer_cours(*, title, summary="", owner_tenant=None, actor=None) -> Course:
    """Un cours neuf, avec sa première version en brouillon."""
    cours = Course.objects.create(
        slug=_slug_libre(title),
        title=title.strip(),
        summary=summary.strip(),
        owner_tenant=owner_tenant,
        created_by=actor,
    )
    CourseVersion.objects.create(course=cours, number=1, change_note="Première version.")
    return cours


@transaction.atomic
def dupliquer(*, cours: Course, owner_tenant=None, actor=None, titre=None) -> Course:
    """Dérive un nouveau cours d'un cours existant.

    C'est ce qui permet à un client de partir d'un cours de la bibliothèque et
    de l'adapter à sa maison. La copie est **complète et indépendante** : le
    cours d'origine peut être republié ensuite sans rien changer à la copie.
    Le lien vers l'original est conservé pour la traçabilité, pas pour la
    synchronisation.

    On copie la version publiée si elle existe, sinon le brouillon : quelqu'un
    qui duplique son propre travail en cours veut son travail en cours.
    """
    source = cours.published_version or cours.draft_version
    if source is None:
        raise StudioError("Ce cours n'a aucun contenu à dupliquer.")

    copie = Course.objects.create(
        slug=_slug_libre(titre or f"{cours.title} (copie)"),
        title=(titre or f"{cours.title} (copie)").strip(),
        summary=cours.summary,
        owner_tenant=owner_tenant,
        derived_from=cours,
        created_by=actor,
    )
    version = CourseVersion.objects.create(
        course=copie,
        number=1,
        pass_threshold=source.pass_threshold,
        max_attempts=source.max_attempts,
        change_note=f"Dérivé de « {cours.title} » (version {source.number}).",
    )
    _recopier_contenu(source, version)
    return copie


@transaction.atomic
def nouvelle_version(cours: Course, *, change_note="") -> CourseVersion:
    """Rouvre l'écriture sur une copie de la dernière version publiée.

    Refuse s'il existe déjà un brouillon : deux brouillons simultanés posent
    la question insoluble de savoir lequel publier.
    """
    if cours.draft_version is not None:
        raise StudioError("Ce cours a déjà une version en cours d'écriture.")

    source = cours.published_version
    if source is None:
        raise StudioError("Ce cours n'a pas encore de version publiée.")

    version = CourseVersion.objects.create(
        course=cours,
        number=source.number + 1,
        pass_threshold=source.pass_threshold,
        max_attempts=source.max_attempts,
        change_note=change_note,
    )
    _recopier_contenu(source, version)
    return version


def _recopier_contenu(source: CourseVersion, cible: CourseVersion) -> None:
    """Copie écrans, questions et choix — en refaisant pointer chaque question
    vers l'écran CORRESPONDANT de la copie.

    C'est le point délicat : laisser les questions pointer vers les écrans de
    la version d'origine produirait une révision ciblée qui renvoie dans un
    autre cours, sans que rien ne le signale.
    """
    correspondance = {}
    for ecran in source.screens.all():
        copie = Screen.objects.create(
            version=cible,
            order=ecran.order,
            title=ecran.title,
            content=ecran.content,
            estimated_seconds=ecran.estimated_seconds,
        )
        correspondance[ecran.id] = copie

    for question in source.questions.prefetch_related("choices"):
        copie = Question.objects.create(
            version=cible,
            order=question.order,
            text=question.text,
            kind=question.kind,
            explanation=question.explanation,
            screen=correspondance[question.screen_id],
        )
        for choix in question.choices.all():
            Choice.objects.create(
                question=copie, order=choix.order, text=choix.text, is_correct=choix.is_correct
            )


# --- Écrire le contenu ------------------------------------------------------


def ecrire_ecran(*, version, screen_id=None, title, content, estimated_seconds=60) -> Screen:
    _version_modifiable(version)
    if screen_id:
        ecran = version.screens.filter(id=screen_id).first()
        if ecran is None:
            raise StudioError("Cet écran n'appartient pas à cette version.")
    else:
        dernier = version.screens.order_by("-order").first()
        ecran = Screen(version=version, order=(dernier.order + 1) if dernier else 1)

    ecran.title = title.strip()
    ecran.content = content
    ecran.estimated_seconds = estimated_seconds
    # La validation des blocs vit dans Screen.save : elle s'applique ici sans
    # que le studio ait à y penser, comme elle s'applique au chargement d'un
    # cours par une commande.
    ecran.save()
    return ecran


@transaction.atomic
def reordonner_ecrans(*, version, ordre_ids) -> list[Screen]:
    """Réordonne les écrans. ``ordre_ids`` doit citer TOUS les écrans."""
    _version_modifiable(version)
    ecrans = {str(e.id): e for e in version.screens.all()}
    demandes = [str(i) for i in ordre_ids]
    if set(demandes) != set(ecrans) or len(demandes) != len(ecrans):
        raise StudioError("L'ordre proposé ne correspond pas aux écrans de cette version.")

    # Deux passes : la contrainte d'unicité (version, order) refuserait un
    # échange direct entre deux rangs.
    for decalage, identifiant in enumerate(demandes, start=1):
        ecran = ecrans[identifiant]
        ecran.order = decalage + len(demandes)
        ecran.save(update_fields=["order"])
    for rang, identifiant in enumerate(demandes, start=1):
        ecran = ecrans[identifiant]
        ecran.order = rang
        ecran.save(update_fields=["order"])
    return list(version.screens.all())


def supprimer_ecran(*, version, screen_id) -> None:
    _version_modifiable(version)
    ecran = version.screens.filter(id=screen_id).first()
    if ecran is None:
        raise StudioError("Cet écran n'appartient pas à cette version.")
    if ecran.questions.exists():
        raise StudioError(
            "Des questions renvoient à cet écran. Rattachez-les ailleurs avant de le "
            "supprimer, sinon la révision après échec n'aurait plus où conduire."
        )
    ecran.delete()


@transaction.atomic
def ecrire_question(
    *, version, question_id=None, text, kind, explanation, screen_id, choix
) -> Question:
    """Écrit une question et ses choix d'un bloc.

    ``choix`` : liste de ``{"text": …, "is_correct": bool}``. Au moins une
    bonne réponse, sinon la question est impossible — et le quiz deviendrait
    un piège plutôt qu'une évaluation.
    """
    _version_modifiable(version)

    if not explanation or not explanation.strip():
        raise StudioError(
            "L'explication est obligatoire : c'est la seule partie du quiz qui forme. "
            "Un quiz qui dit seulement « faux » n'apprend rien."
        )
    if not any(c.get("is_correct") for c in choix):
        raise StudioError("Il faut au moins une bonne réponse.")
    if len(choix) < 2:
        raise StudioError("Il faut au moins deux propositions.")
    if kind == Question.Kind.SINGLE and sum(1 for c in choix if c.get("is_correct")) > 1:
        raise StudioError(
            "Une question à choix unique ne peut avoir qu'une bonne réponse. "
            "Passez-la en choix multiple."
        )

    ecran = version.screens.filter(id=screen_id).first()
    if ecran is None:
        raise StudioError("La question doit renvoyer à un écran de ce cours.")

    if question_id:
        question = version.questions.filter(id=question_id).first()
        if question is None:
            raise StudioError("Cette question n'appartient pas à cette version.")
    else:
        derniere = version.questions.order_by("-order").first()
        question = Question(version=version, order=(derniere.order + 1) if derniere else 1)

    question.text = text.strip()
    question.kind = kind
    question.explanation = explanation.strip()
    question.screen = ecran
    question.save()

    question.choices.all().delete()
    for rang, proposition in enumerate(choix, start=1):
        Choice.objects.create(
            question=question,
            order=rang,
            text=proposition["text"].strip(),
            is_correct=bool(proposition.get("is_correct")),
        )
    return question


def supprimer_question(*, version, question_id) -> None:
    _version_modifiable(version)
    question = version.questions.filter(id=question_id).first()
    if question is None:
        raise StudioError("Cette question n'appartient pas à cette version.")
    question.delete()


# --- Publier ----------------------------------------------------------------


def controles_avant_publication(version: CourseVersion) -> tuple[list[str], list[str]]:
    """Rend ``(refus, avertissements)``.

    La distinction est le cœur de cette fonction : un cours sans écran ne peut
    pas être publié, un cours de trois questions le peut — mal. On refuse ce
    qui est cassé, on signale ce qui est bancal, et on ne confond pas les deux.
    """
    refus = []
    avertissements = []

    if not version.screens.exists():
        refus.append("Un cours doit comporter au moins un écran.")

    questions = list(version.questions.prefetch_related("choices"))
    if not questions:
        refus.append("Un cours doit comporter au moins une question.")

    for question in questions:
        if not question.correct_choice_ids:
            refus.append(f"La question {question.order} n'a aucune bonne réponse.")
        if not question.explanation.strip():
            refus.append(f"La question {question.order} n'a pas d'explication.")

    if questions and len(questions) < QUESTIONS_MINIMUM_POUR_UN_SEUIL:
        avertissements.append(
            f"{len(questions)} question(s) : en deçà de {QUESTIONS_MINIMUM_POUR_UN_SEUIL}, un "
            f"seuil de {version.pass_threshold} % ne veut plus dire grand-chose — une seule "
            "erreur fait basculer le résultat."
        )

    # Un écran qu'aucune question ne vise n'est pas un défaut : tous les
    # écrans n'ont pas à être évalués. Mais une question sans écran, si — et
    # c'est impossible par construction, le rattachement étant obligatoire.
    for ecran in version.screens.all():
        for _champ, texte in (
            (champ, texte)
            for bloc in ecran.content
            for champ, texte in blocs_de_contenu._textes_du_bloc(bloc)
        ):
            if blocs_de_contenu.variables_du_texte(texte):
                avertissements.append(
                    f"L'écran {ecran.order} utilise des variables : vérifiez sa formulation "
                    "de repli, c'est elle que verront les clients sans données."
                )
                break

    return refus, avertissements


@transaction.atomic
def publier(version: CourseVersion) -> CourseVersion:
    if version.is_published:
        raise StudioError("Cette version est déjà publiée.")

    refus, _avertissements = controles_avant_publication(version)
    if refus:
        raise StudioError(" ".join(refus))

    version.published_at = timezone.now()
    version.save(update_fields=["published_at"])
    return version


def apercu(version: CourseVersion, tenant=None) -> dict:
    """Le cours tel que l'apprenant le verra, sans inscription ni jeton.

    Les variables sont résolues avec les données du client quand on en a un —
    c'est le seul moyen de voir si la phrase se tient avec de vrais chiffres,
    et si la formulation de repli sonne juste quand il n'y en a pas.
    """
    from . import services

    return {
        "course_title": version.course.title,
        "course_version": version.number,
        "estimated_minutes": version.estimated_minutes,
        "pass_threshold": version.pass_threshold,
        "max_attempts": version.max_attempts,
        "is_published": version.is_published,
        "screens": [
            {
                "id": str(ecran.id),
                "order": ecran.order,
                "title": ecran.title,
                "content": (
                    services.contextualiser(ecran.content, tenant) if tenant else ecran.content
                ),
                "content_brut": ecran.content,
                "estimated_seconds": ecran.estimated_seconds,
            }
            for ecran in version.screens.all()
        ],
        "questions": [
            {
                "id": str(question.id),
                "order": question.order,
                "text": question.text,
                "kind": question.kind,
                "explanation": question.explanation,
                "screen_id": str(question.screen_id),
                "choices": [
                    {"id": str(c.id), "text": c.text, "is_correct": c.is_correct}
                    for c in sorted(question.choices.all(), key=lambda c: c.order)
                ],
            }
            for question in version.questions.prefetch_related("choices")
        ],
    }
