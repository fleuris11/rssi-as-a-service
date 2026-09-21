"""La logique du parcours de formation (F1, ADR-039).

Le cloisonnement, et la seule exception
---------------------------------------
Un apprenant sur lien nominatif n'a ni compte, ni jeton JWT, ni en-tête
``X-Tenant-Id`` : le middleware de scoping ne pose donc **aucun** contexte de
client pour lui, et le manager par défaut — qui échoue fermé — rendrait des
ensembles vides.

La réponse retenue n'est pas de contourner le manager avec ``all_objects``
partout, ce qui reviendrait à désactiver le filet de sécurité du produit dans
la seule app où l'appelant n'est pas authentifié. Elle est de **poser le
contexte depuis le jeton**, exactement comme le middleware le pose depuis une
adhésion :

- ``resoudre_session`` est le seul endroit de ce module qui interroge la base
  hors contexte (``all_objects``), pour retrouver l'inscription d'un jeton —
  c'est le pendant exact de ``_resolve_membership`` dans le middleware ;
- le contexte est ensuite posé **depuis le client de l'inscription trouvée**,
  jamais depuis quoi que ce soit d'envoyé par l'appelant ;
- tout le reste du module utilise le manager scopé, comme partout ailleurs.

Le jour où quelqu'un ajoutera une fonction ici, elle sera cloisonnée par
défaut. C'était la condition pour que ce module ne devienne pas une exception
permanente.
"""

import hashlib
import secrets
from contextlib import contextmanager

from django.db import transaction
from django.utils import timezone

from apps.tenants.context import reset_current_tenant, set_current_tenant

from . import blocks as blocs_de_contenu
from . import variables
from .models import (
    QUESTIONS_MINIMUM_POUR_UN_SEUIL,
    Attempt,
    AttemptAnswer,
    Certificate,
    CourseAssignment,
    Enrollment,
    Learner,
    Question,
    Screen,
    ScreenProgress,
)


class TrainingError(Exception):
    """Erreur métier du module. Jamais un 500."""


class SessionIntrouvable(TrainingError):
    """Jeton inconnu, révoqué, expiré, ou salarié désactivé.

    Un seul type pour les quatre cas, **volontairement** : distinguer
    « inconnu » de « expiré » dans la réponse dirait à qui essaie des jetons
    au hasard lesquels ont existé.
    """


class QuizRefuse(TrainingError):
    """Le quiz ne peut pas être soumis, et la phrase dit pourquoi."""


class InscriptionRefusee(TrainingError):
    """L'inscription ne peut pas être créée telle quelle."""


# --- Le lien nominatif ------------------------------------------------------


def _hacher(jeton_en_clair: str) -> str:
    # SHA-256 et non un hacheur de mot de passe : le jeton fait 256 bits
    # d'aléa, il n'est pas devinable par force brute. Le coût d'un hacheur
    # lent serait payé à chaque ouverture d'écran, sans rien apporter. Même
    # raisonnement que ``accounts.services._hash_token``.
    return hashlib.sha256(jeton_en_clair.encode()).hexdigest()


def _emettre_un_jeton() -> tuple[str, str]:
    brut = secrets.token_urlsafe(32)
    return brut, _hacher(brut)


def lien_de_session(jeton_en_clair: str) -> str:
    from django.conf import settings

    base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    return f"{base}/formation/{jeton_en_clair}"


@contextmanager
def contexte_du_client(tenant):
    """Pose le contexte de cloisonnement pour la durée d'un bloc.

    Utilisé par les vues de l'apprenant, qui n'en ont pas reçu du middleware.
    Le ``finally`` n'est pas décoratif : sans lui, un contexte poserait sur le
    fil d'exécution d'une requête et fuiterait sur la suivante.
    """
    jeton = set_current_tenant(str(tenant.id if hasattr(tenant, "id") else tenant))
    try:
        yield
    finally:
        reset_current_tenant(jeton)


def resoudre_session(jeton_en_clair: str) -> Enrollment:
    """L'inscription que désigne ce jeton. Lève ``SessionIntrouvable`` sinon.

    **Le seul accès hors contexte du module.** Il est ici, isolé, court, et
    ne rend jamais autre chose qu'une inscription utilisable.
    """
    if not jeton_en_clair:
        raise SessionIntrouvable("Ce lien n'est pas valable.")

    inscription = (
        Enrollment.all_objects.select_related("learner", "version", "version__course", "tenant")
        .filter(token_hash=_hacher(jeton_en_clair))
        .first()
    )
    if inscription is None or not inscription.is_usable:
        raise SessionIntrouvable("Ce lien n'est plus valable.")

    if inscription.first_opened_at is None:
        inscription.first_opened_at = timezone.now()
        inscription.save(update_fields=["first_opened_at"])
    return inscription


def demander_un_acces(jeton_en_clair: str) -> bool:
    """Un salarié dont le lien est mort demande à retrouver l'accès.

    **Pourquoi cette page ne réémet pas un lien elle-même.** La validité d'un
    lien découle de l'échéance de la campagne : réémettre un jeton pour la même
    inscription produirait un lien tout aussi périmé. Rendre l'accès suppose de
    déplacer l'échéance ou de réinscrire — deux décisions de gestion, qui
    appartiennent à l'entreprise et non à un courriel automatique.

    Le message part donc vers les administrateurs du client, jamais vers le
    salarié, et ne contient aucun lien.

    Rend ``True`` si une demande a été déposée, ``False`` si elle a déjà été
    déposée aujourd'hui — sans le dire à l'appelant autrement, pour que
    quelqu'un qui détient un lien mort ne puisse pas relancer les
    administrateurs dix fois dans la journée.
    """
    inscription = (
        Enrollment.all_objects.select_related("learner", "version", "version__course", "tenant")
        .filter(token_hash=_hacher(jeton_en_clair or ""))
        .first()
    )
    # Révoqué : on ne prévient personne. Un accès retiré l'a été exprès, et
    # relancer l'administrateur qui vient de le retirer n'a aucun sens.
    if inscription is None or inscription.is_revoked or not inscription.learner.is_active:
        raise SessionIntrouvable("Ce lien n'est plus valable.")

    maintenant = timezone.now()
    deja = inscription.access_requested_at
    if deja is not None and deja.date() == maintenant.date():
        return False

    from . import emails

    emails.envoyer_demande_dacces(inscription)
    inscription.access_requested_at = maintenant
    inscription.save(update_fields=["access_requested_at"])
    return True


# --- Côté pilote : composer une campagne ------------------------------------


def creer_apprenant(*, tenant, full_name, email, actor=None, user=None) -> Learner:
    email = (email or "").strip().lower()
    existant = Learner.objects.filter(email=email).first()
    if existant is not None:
        raise InscriptionRefusee(f"{existant.full_name} figure déjà dans vos salariés formés.")
    return Learner.objects.create(
        tenant=tenant,
        full_name=full_name.strip(),
        email=email,
        user=user,
        created_by=actor,
    )


def attribuer_cours(*, tenant, course, actor=None) -> CourseAssignment:
    attribution, _ = CourseAssignment.objects.get_or_create(
        course=course, defaults={"tenant": tenant, "assigned_by": actor}
    )
    return attribution


def cours_attribues(tenant):
    """Les cours que ce client peut proposer, publiés uniquement."""
    return [
        attribution.course
        for attribution in CourseAssignment.objects.select_related("course").order_by(
            "course__title"
        )
        if attribution.course.is_active and attribution.course.published_version is not None
    ]


@transaction.atomic
def inscrire(*, tenant, learner, course, due_date, actor=None) -> tuple[Enrollment, str]:
    """Inscrit un salarié à la version publiée d'un cours. Rend le jeton en
    clair — qui n'existe qu'une fois, dans la réponse qui suit."""
    if not learner.is_active:
        raise InscriptionRefusee(
            f"{learner.full_name} n'est plus actif : réactivez-le avant de l'inscrire."
        )

    if not CourseAssignment.objects.filter(course=course).exists():
        raise InscriptionRefusee("Ce cours n'est pas proposé à votre entreprise.")

    version = course.published_version
    if version is None:
        raise InscriptionRefusee("Ce cours n'a pas encore de version publiée.")

    deja = Enrollment.objects.filter(
        learner=learner, version=version, revoked_at__isnull=True
    ).first()
    if deja is not None:
        raise InscriptionRefusee(
            f"{learner.full_name} est déjà inscrit à « {course.title} » "
            f"jusqu'au {deja.due_date:%d/%m/%Y}."
        )

    brut, hache = _emettre_un_jeton()
    inscription = Enrollment.objects.create(
        tenant=tenant,
        learner=learner,
        version=version,
        due_date=due_date,
        token_hash=hache,
        token_issued_at=timezone.now(),
        created_by=actor,
    )
    return inscription, brut


def renouveler_le_lien(*, enrollment, actor=None) -> str:
    """Émet un nouveau jeton pour cette inscription. L'ancien cesse
    immédiatement de fonctionner — un lien renouvelé qui laisserait vivre le
    précédent ne renouvellerait rien."""
    if enrollment.is_revoked:
        raise InscriptionRefusee("Cet accès a été retiré ; il ne peut pas être renouvelé.")
    brut, hache = _emettre_un_jeton()
    enrollment.token_hash = hache
    enrollment.token_issued_at = timezone.now()
    enrollment.save(update_fields=["token_hash", "token_issued_at"])
    return brut


def revoquer(*, enrollment, actor=None) -> Enrollment:
    """Retire l'accès. Immédiat : un salarié qui quitte l'entreprise ne doit
    pas garder un lien vivant jusqu'à l'échéance de la campagne."""
    if enrollment.is_revoked:
        return enrollment
    enrollment.revoked_at = timezone.now()
    enrollment.revoked_by = actor
    enrollment.save(update_fields=["revoked_at", "revoked_by"])
    return enrollment


def accorder_des_essais(*, enrollment, nombre=1, actor=None) -> Enrollment:
    """Réarme le quiz pour CE salarié.

    Sans recours, un blocage définitif produit un appel au support — et il y
    aura toujours un cas légitime, une coupure réseau au milieu d'un quiz par
    exemple.
    """
    if nombre < 1:
        raise InscriptionRefusee("Le nombre d'essais accordés doit être d'au moins un.")
    enrollment.extra_attempts += nombre
    enrollment.attempts_granted_by = actor
    enrollment.attempts_granted_at = timezone.now()
    enrollment.save(update_fields=["extra_attempts", "attempts_granted_by", "attempts_granted_at"])
    return enrollment


# --- Côté apprenant : suivre le cours ---------------------------------------


def _ecrans(enrollment):
    return list(enrollment.version.screens.all())


def _questions(enrollment):
    return list(enrollment.version.questions.select_related("screen").prefetch_related("choices"))


def contextualiser(blocs, tenant) -> list[dict]:
    """Remplace les variables d'un écran par les chiffres réels du client.

    Le calcul se fait **à l'affichage**, jamais à l'inscription : un cours
    suivi trois semaines après son attribution doit montrer la situation du
    jour, pas celle d'un mercredi oublié. Rien n'est stocké — ni dans la
    progression, ni dans la tentative, ni dans l'attestation.

    Le repli s'applique au BLOC entier, et non variable par variable. Sinon on
    produirait des phrases bancales : « votre entreprise a eu — comptes
    compromis ces 6 mois ». Un bloc se lit d'un tenant ou pas du tout.
    """
    resultat = []
    for bloc in blocs or []:
        champs = blocs_de_contenu._textes_du_bloc(bloc)
        cles = {
            cle for _champ, texte in champs for cle in blocs_de_contenu.variables_du_texte(texte)
        }
        if not cles:
            resultat.append(bloc)
            continue

        try:
            valeurs = {cle: variables.valeur(cle, tenant) for cle in cles}
        except variables.ValeurIndisponible:
            # Une seule variable manquante fait basculer tout le bloc : c'est
            # le prix d'une phrase qui se tient.
            resultat.append({"type": blocs_de_contenu.PARAGRAPHE, "texte": bloc.get("repli", "")})
            continue

        remplace = dict(bloc)
        for champ, texte in champs:
            rendu = texte
            for cle, valeur in valeurs.items():
                rendu = rendu.replace(f"{{{cle}}}", str(valeur))
            if champ.startswith("items["):
                rang = int(champ[6:-1]) - 1
                items = list(remplace.get("items") or [])
                items[rang] = rendu
                remplace["items"] = items
            else:
                remplace[champ] = rendu
        resultat.append(remplace)
    return resultat


def etat_de_session(enrollment) -> dict:
    """Tout ce que le lecteur de cours a besoin de savoir, en un appel.

    Un seul aller-retour parce que l'apprenant type est dans les transports :
    trois requêtes en série sur un réseau mobile, c'est trois occasions de voir
    une page à moitié chargée.
    """
    ecrans = _ecrans(enrollment)
    vus = set(
        ScreenProgress.objects.filter(enrollment=enrollment).values_list("screen_id", flat=True)
    )
    essais = list(Attempt.objects.filter(enrollment=enrollment).order_by("number"))
    attestation = Certificate.objects.filter(enrollment=enrollment).first()

    # La reprise : le premier écran non terminé. Dérivé, jamais stocké — un
    # curseur en base se désynchroniserait de la progression réelle.
    index_de_reprise = 0
    for position, ecran in enumerate(ecrans):
        if ecran.id not in vus:
            index_de_reprise = position
            break
    else:
        index_de_reprise = max(0, len(ecrans) - 1)

    return {
        "learner_name": enrollment.learner.full_name,
        "company_name": enrollment.tenant.name,
        "course_title": enrollment.version.course.title,
        "course_summary": enrollment.version.course.summary,
        "course_version": enrollment.version.number,
        "estimated_minutes": enrollment.version.estimated_minutes,
        "due_date": enrollment.due_date,
        "expires_at": enrollment.expires_at,
        "screens": [
            {
                "id": str(ecran.id),
                "order": ecran.order,
                "title": ecran.title,
                # Contextualisé ici, au moment où l'apprenant le lit.
                "content": contextualiser(ecran.content, enrollment.tenant),
                "completed": ecran.id in vus,
            }
            for ecran in ecrans
        ],
        "screens_total": len(ecrans),
        "screens_completed": len(vus),
        "resume_index": index_de_reprise,
        # Le quiz ne s'ouvre qu'une fois le cours parcouru : c'est un quiz DE
        # FIN, et le proposer avant ferait de la formation un examen.
        "quiz_unlocked": bool(ecrans) and len(vus) >= len(ecrans),
        "pass_threshold": enrollment.version.pass_threshold,
        "attempts_used": len(essais),
        "attempts_allowed": enrollment.attempts_allowed,
        "passed": any(essai.passed for essai in essais),
        "certificate": _attestation_en_clair(attestation) if attestation else None,
        # Le quiz fait partie de l'ÉTAT, et non d'un appel séparé.
        #
        # Il ne l'était pas : seule la première lecture le servait, et l'état
        # renvoyé après « écran terminé » revenait sans lui. L'interface, qui
        # remplace sa session par la réponse reçue, se retrouvait au septième
        # écran avec un questionnaire disparu. Aucun test d'API ne le voyait —
        # ils n'appelaient jamais les deux points d'entrée à la suite — et il a
        # fallu un navigateur pour s'en apercevoir.
        #
        # La leçon est de forme, pas de contenu : deux points d'entrée qui
        # décrivent la même chose doivent la décrire pareil.
        "quiz": questions_du_quiz(enrollment),
    }


def questions_du_quiz(enrollment) -> list[dict]:
    """Les questions, SANS les bonnes réponses.

    La correction se fait au serveur. Envoyer ``is_correct`` au navigateur
    mettrait la réponse dans la page, à un clic droit de distance.
    """
    return [
        {
            "id": str(question.id),
            "order": question.order,
            "text": question.text,
            "kind": question.kind,
            "choices": [
                {"id": str(choix.id), "text": choix.text}
                for choix in sorted(question.choices.all(), key=lambda c: c.order)
            ],
        }
        for question in _questions(enrollment)
    ]


def marquer_ecran_vu(*, enrollment, screen_id) -> dict:
    """Enregistre qu'un écran est terminé. Idempotent.

    Revenir en arrière ne retire jamais de ligne : la navigation est libre, la
    progression enregistrée reste la progression réelle.
    """
    ecran = Screen.objects.filter(version=enrollment.version, id=screen_id).first()
    if ecran is None:
        raise TrainingError("Cet écran n'appartient pas à ce cours.")
    ScreenProgress.objects.get_or_create(
        enrollment=enrollment, screen=ecran, defaults={"tenant": enrollment.tenant}
    )
    return etat_de_session(enrollment)


def _corriger(question, choisis: set, attendus: set) -> bool:
    """Juste = exactement les bonnes réponses, ni plus ni moins.

    Sur une question à choix multiple, cocher les deux bonnes réponses ET une
    mauvaise n'est pas « à moitié juste » : c'est se tromper sur la mauvaise.
    """
    if question.kind == Question.Kind.SINGLE and len(choisis) != 1:
        return False
    return bool(choisis) and choisis == attendus


@transaction.atomic
def soumettre_le_quiz(*, enrollment, reponses: dict) -> dict:
    """Corrige une tentative, explique chaque question, et délivre
    l'attestation si le seuil est atteint.

    ``reponses`` : {identifiant de question: [identifiants de choix]}.
    """
    questions = _questions(enrollment)
    if not questions:
        raise QuizRefuse("Ce cours ne comporte pas encore de quiz.")

    etat = etat_de_session(enrollment)
    if etat["passed"]:
        raise QuizRefuse("Vous avez déjà réussi ce cours.")
    if not etat["quiz_unlocked"]:
        raise QuizRefuse(
            "Terminez d'abord les écrans du cours : le quiz porte sur ce qui y est expliqué."
        )
    if etat["attempts_used"] >= etat["attempts_allowed"]:
        raise QuizRefuse(
            "Vous avez utilisé vos essais. Demandez à votre responsable de vous en "
            "accorder un nouveau."
        )

    manquantes = [q for q in questions if not reponses.get(str(q.id))]
    if manquantes:
        raise QuizRefuse(
            f"Il reste {len(manquantes)} question(s) sans réponse. Répondez à tout "
            "avant de valider."
        )

    numero = etat["attempts_used"] + 1
    detail = []
    justes = 0
    for question in questions:
        choisis = {str(identifiant) for identifiant in reponses.get(str(question.id), [])}
        attendus = {str(identifiant) for identifiant in question.correct_choice_ids}
        # La comparaison se fait sur des chaînes des deux côtés : les
        # identifiants arrivent du réseau en texte, et comparer un UUID à sa
        # représentation rendrait toute réponse fausse — silencieusement.
        correct = _corriger(question, choisis, attendus)
        if correct:
            justes += 1
        detail.append((question, choisis, attendus, correct))

    score = round(100 * justes / len(questions))
    reussi = score >= enrollment.version.pass_threshold

    tentative = Attempt.objects.create(
        tenant=enrollment.tenant,
        enrollment=enrollment,
        number=numero,
        score=score,
        passed=reussi,
    )
    AttemptAnswer.objects.bulk_create(
        [
            AttemptAnswer(
                tenant=enrollment.tenant,
                attempt=tentative,
                question=question,
                selected_choice_ids=sorted(choisis),
                is_correct=correct,
            )
            for question, choisis, _attendus, correct in detail
        ]
    )

    attestation = _delivrer_lattestation(enrollment, score) if reussi else None

    return {
        "score": score,
        "passed": reussi,
        "pass_threshold": enrollment.version.pass_threshold,
        "attempt_number": numero,
        "attempts_used": numero,
        "attempts_allowed": enrollment.attempts_allowed,
        "questions": [
            {
                "id": str(question.id),
                "text": question.text,
                "correct": correct,
                # L'explication est servie dans TOUS les cas, juste ou faux.
                # Un quiz qui n'explique que les erreurs laisse croire que
                # celui qui a bien répondu avait forcément la bonne raison.
                "explanation": question.explanation,
                "correct_choice_ids": sorted(attendus),
                "selected_choice_ids": sorted(choisis),
                "screen": {
                    "id": str(question.screen_id),
                    "order": question.screen.order,
                    "title": question.screen.title,
                },
            }
            for question, choisis, attendus, correct in detail
        ],
        # Les écrans à revoir, et eux seuls : renvoyer quelqu'un dans le cours
        # entier pour deux erreurs, c'est le renvoyer nulle part.
        #
        # Dédoublonnés, et dans l'ordre du cours : deux questions ratées sur le
        # même écran désignent UN écran à relire. L'afficher deux fois ferait
        # croire à deux choses à revoir, et paraîtrait plus lourd que ce ne
        # l'est — au moment précis où quelqu'un vient d'échouer.
        "screens_to_review": _ecrans_a_revoir(detail),
        "certificate": _attestation_en_clair(attestation) if attestation else None,
    }


def _ecrans_a_revoir(detail) -> list[dict]:
    vus = {}
    for question, _choisis, _attendus, correct in detail:
        if correct or question.screen_id in vus:
            continue
        vus[question.screen_id] = {
            "id": str(question.screen_id),
            "order": question.screen.order,
            "title": question.screen.title,
        }
    return sorted(vus.values(), key=lambda ecran: ecran["order"])


def _delivrer_lattestation(enrollment, score) -> Certificate:
    """Fige tout ce qui figurera sur l'attestation. Voir le docstring du
    modèle : un cours renommé ne doit pas réécrire un document délivré."""
    existante = Certificate.objects.filter(enrollment=enrollment).first()
    if existante is not None:
        return existante
    return Certificate.objects.create(
        tenant=enrollment.tenant,
        enrollment=enrollment,
        serial=Certificate.build_serial(),
        learner_name=enrollment.learner.full_name,
        course_title=enrollment.version.course.title,
        course_version=enrollment.version.number,
        company_name=enrollment.tenant.name,
        score=score,
    )


def _attestation_en_clair(attestation) -> dict:
    return {
        "serial": attestation.serial,
        "issued_at": attestation.issued_at,
        "learner_name": attestation.learner_name,
        "course_title": attestation.course_title,
        "company_name": attestation.company_name,
        "score": attestation.score,
    }


def avertissements_de_quiz(version) -> list[str]:
    """Ce qui rend un quiz bancal sans être invalide. Sert au chargement de
    cours, et servira au studio de F2.

    Avertir et non interdire : un micro-cours de trois questions peut être un
    choix — mais il faut que l'auteur sache qu'à ce compte-là, un seuil de 70 %
    est arithmétiquement un quiz de deux questions.
    """
    total = version.questions.count()
    problemes = []
    if total < QUESTIONS_MINIMUM_POUR_UN_SEUIL:
        problemes.append(
            f"{total} question(s) : en deçà de {QUESTIONS_MINIMUM_POUR_UN_SEUIL}, un seuil "
            f"de {version.pass_threshold} % ne veut plus dire grand-chose — une seule erreur "
            "fait basculer le résultat."
        )
    sans_bonne_reponse = [
        question.order
        for question in version.questions.prefetch_related("choices")
        if not question.correct_choice_ids
    ]
    if sans_bonne_reponse:
        rangs = ", ".join(str(rang) for rang in sans_bonne_reponse)
        problemes.append(f"Questions sans bonne réponse : {rangs}.")
    return problemes
