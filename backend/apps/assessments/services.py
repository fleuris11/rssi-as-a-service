"""Public interface of the assessments app — other apps must go through
here instead of importing apps.assessments.models directly.

``Assessment``/``Answer`` are tenant-scoped, but every function here is
given an already-resolved ``tenant``/``assessment`` (never derives one from
ambient request context), so — unlike apps.tenants.services, which reads
through the request-scoped manager — these functions consistently use
``all_objects`` with an explicit ``tenant=`` filter. That makes the whole
module correct and unit-testable independently of whether it's called from
a request that went through TenantScopingMiddleware.

Depuis V2-4 (ADR-029) ce module ne connaît plus « le » référentiel : il
connaît un catalogue, des attributions par client, des sous-ensembles et des
surcharges d'énoncé. Trois règles s'y lisent partout :

- **produire demande une attribution active, lire n'en demande jamais.** Un
  client qui perd un référentiel garde ses évaluations passées ;
- **le périmètre d'une évaluation est porté par elle** (``referential`` et,
  s'il y en a un, ``subset``) et non par un réglage global — un diagnostic
  déjà commencé ne change pas de questionnaire sous les pieds de celui qui
  le remplit ;
- **la surcharge d'énoncé vit à côté** : elle est posée sur les instances au
  moment de la lecture, jamais écrite dans ``Measure``.
"""

import logging

from django.db.models import Q
from django.utils import timezone

from .models import (
    Answer,
    Assessment,
    Domain,
    Measure,
    MeasureStatementOverride,
    MeasureSubset,
    Referential,
    ReferentialAssignment,
    SubsetMeasure,
)

logger = logging.getLogger(__name__)


class AssessmentsError(Exception):
    """Base class for business-rule violations raised by this module."""


class NoActiveReferentialError(AssessmentsError):
    pass


class ReferentialNotAssignedError(AssessmentsError):
    """Le client n'a pas (ou n'a plus) ce référentiel. Refus de PRODUCTION
    uniquement : la lecture de ses évaluations passées reste ouverte."""


class MeasureNotInReferentialError(AssessmentsError):
    pass


class MeasureNotInScopeError(AssessmentsError):
    """La mesure appartient bien au référentiel, mais pas au sous-ensemble
    sur lequel porte cette évaluation."""


class SubsetError(AssessmentsError):
    pass


class AssessmentAlreadyCompletedError(AssessmentsError):
    pass


class IncompleteAssessmentError(AssessmentsError):
    def __init__(self, answered, total):
        self.answered = answered
        self.total = total
        super().__init__(
            f"{answered}/{total} mesures répondues : toutes les mesures doivent avoir une "
            "réponse (y compris « non applicable ») avant de terminer l'évaluation."
        )


VALUE_SCORES = {
    Answer.Value.YES: 1.0,
    Answer.Value.PARTIAL: 0.5,
    Answer.Value.NO: 0.0,
}

# Poids historique des niveaux ANSSI, conservé au seul usage de
# l'importateur ANSSI : une mesure « renforcée » compte pour moitié, elle est
# souhaitable sans être bloquante pour une TPE/PME. Le score, lui, ne lit plus
# cette table — il lit ``Measure.weight``, que chaque référentiel pose.
ANSSI_LEVEL_WEIGHTS = {
    Measure.Level.STANDARD: 1.0,
    Measure.Level.RENFORCE: 0.5,
}

# Re-exported so apps.actions can build a projected score (a "done" action
# item's measure counts as full credit) without importing Answer directly.
FULL_CREDIT_VALUE = Answer.Value.YES

# Re-exported so apps.actions can identify which answers are "gaps" worth an
# action item, without importing Answer directly.
GAP_VALUES = {Answer.Value.NO, Answer.Value.PARTIAL}


# --- Catalogue et attributions ----------------------------------------------


def list_catalog(*, include_inactive: bool = False):
    """Tout le catalogue, pour la console d'administration."""
    queryset = Referential.objects.all()
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return queryset.select_related("owner_tenant").order_by("name")


def get_referential(*, slug=None, referential_id=None) -> Referential | None:
    queryset = Referential.objects.all()
    if slug is not None:
        return queryset.filter(slug=slug).first()
    return queryset.filter(id=referential_id).first()


def assignable_referentials(tenant):
    """Ce qu'on PEUT attribuer à ce client : le catalogue actif, moins les
    référentiels propres à un autre client."""
    return list_catalog().filter(Q(owner_tenant__isnull=True) | Q(owner_tenant=tenant))


def default_referentials():
    """Ce qu'une entreprise nouvellement créée reçoit d'office : les
    référentiels actifs **libres de droits**, et eux seuls.

    Un contenu sous licence ne s'attribue pas tout seul — c'est l'exploitant
    qui sait ce qu'il a le droit de servir, et à qui (ADR-029 §5). Un
    référentiel propre à un client ne concerne évidemment que lui.
    """
    return Referential.objects.filter(
        is_active=True, kind=Referential.Kind.OPEN, owner_tenant__isnull=True
    ).order_by("name")


def list_assignments(tenant, *, include_revoked: bool = True):
    queryset = ReferentialAssignment.all_objects.filter(tenant=tenant).select_related("referential")
    if not include_revoked:
        queryset = queryset.filter(revoked_at__isnull=True)
    return queryset.order_by("referential__name")


def granted_referentials(tenant):
    """Les référentiels que ce client peut utiliser MAINTENANT — ceux sur
    lesquels il peut commencer, remplir et terminer un diagnostic."""
    slugs = ReferentialAssignment.all_objects.filter(
        tenant=tenant, revoked_at__isnull=True
    ).values_list("referential_id", flat=True)
    return Referential.objects.filter(id__in=list(slugs), is_active=True).order_by("name")


def readable_referentials(tenant):
    """Ceux que le client peut LIRE : les attribués, plus tous ceux sur
    lesquels il a déjà produit une évaluation, même retirés depuis.

    C'est la règle du point 7 de V2-4, et elle est ici plutôt que dans les
    vues : une donnée déjà produite ne se reprend pas, et cela ne doit pas
    dépendre de l'endroit d'où on la demande.
    """
    attribues = ReferentialAssignment.all_objects.filter(
        tenant=tenant, revoked_at__isnull=True
    ).values_list("referential_id", flat=True)
    evalues = Assessment.all_objects.filter(tenant=tenant).values_list("referential_id", flat=True)
    return Referential.objects.filter(id__in=set(attribues) | set(evalues)).order_by("name")


def is_granted(tenant, referential) -> bool:
    return ReferentialAssignment.all_objects.filter(
        tenant=tenant, referential=referential, revoked_at__isnull=True
    ).exists()


def is_readable(tenant, referential) -> bool:
    if is_granted(tenant, referential):
        return True
    return Assessment.all_objects.filter(tenant=tenant, referential=referential).exists()


def ensure_granted(tenant, referential) -> None:
    """Garde des chemins de PRODUCTION. Jamais appelée en lecture."""
    if not is_granted(tenant, referential):
        raise ReferentialNotAssignedError(
            f"Le référentiel « {referential.name} » ne fait pas partie de ceux qui vous "
            "sont attribués. Vous pouvez en faire la demande depuis votre espace."
        )


def assign_referential(*, tenant, referential, granted_by=None, note: str = ""):
    """Attribue (ou ré-attribue) un référentiel à un client. Ré-attribuer
    lève simplement le retrait : la ligne d'origine est conservée, avec la
    date à laquelle l'accès avait été donné la première fois."""
    if referential.owner_tenant_id is not None and referential.owner_tenant_id != tenant.id:
        raise ReferentialNotAssignedError(
            "Ce référentiel est propre à un autre client et ne peut pas lui être attribué."
        )
    assignment, created = ReferentialAssignment.all_objects.get_or_create(
        tenant=tenant,
        referential=referential,
        defaults={"granted_by": granted_by, "note": note},
    )
    if not created and assignment.revoked_at is not None:
        assignment.revoked_at = None
        assignment.revoked_by = None
        if note:
            assignment.note = note
        assignment.save(update_fields=["revoked_at", "revoked_by", "note"])
    return assignment


def revoke_referential(*, tenant, referential, revoked_by=None):
    """Retire l'accès. Retrait LOGIQUE : les évaluations produites restent
    lisibles (readable_referentials)."""
    assignment = ReferentialAssignment.all_objects.filter(
        tenant=tenant, referential=referential
    ).first()
    if assignment is None or assignment.revoked_at is not None:
        return assignment
    assignment.revoked_at = timezone.now()
    assignment.revoked_by = revoked_by
    assignment.save(update_fields=["revoked_at", "revoked_by"])
    return assignment


def get_default_referential(tenant) -> Referential:
    """Le référentiel proposé par défaut à ce client : le premier attribué.

    Existe pour les appelants qui n'en désignent aucun — l'ancien endpoint
    ``/referential/`` et le démarrage d'un diagnostic sans précision.
    """
    referential = granted_referentials(tenant).first()
    if referential is None:
        # Ce message remonte au CLIENT. Il ne lui apprend rien de notre
        # outillage : le détail exploitable part dans les journaux.
        logger.warning(
            "Aucun référentiel attribué au tenant %s : le diagnostic lui est indisponible. "
            "Attribuer un référentiel depuis la console (Clients → Référentiels).",
            tenant.id,
        )
        raise NoActiveReferentialError(
            "Aucun référentiel ne vous est attribué pour le moment. Vous pouvez en "
            "demander un depuis votre espace ; nous revenons vers vous rapidement."
        )
    return referential


def get_active_referential() -> Referential:
    """Compatibilité : le référentiel actif de la plateforme, quand il n'y a
    pas de client sous la main (chargement initial, scripts d'exploitation).

    N'est plus le chemin normal — il ne sait rien des attributions. Les vues
    passent par ``get_default_referential(tenant)``.
    """
    referential = Referential.objects.filter(is_active=True).order_by("-id").first()
    if referential is None:
        logger.error(
            "Aucun référentiel en base : le diagnostic est indisponible pour tous les "
            "clients. Charger un référentiel avec `manage.py import_referential`."
        )
        raise NoActiveReferentialError(
            "Le diagnostic est momentanément indisponible. Nos équipes en sont "
            "informées ; réessayez d'ici quelques minutes."
        )
    return referential


# --- Sous-ensembles ---------------------------------------------------------


def list_subsets(tenant, *, referential=None):
    """Les compositions utilisables par ce client : les modèles de plateforme
    et les siennes."""
    queryset = MeasureSubset.objects.filter(is_active=True).filter(
        Q(owner_tenant__isnull=True) | Q(owner_tenant=tenant)
    )
    if referential is not None:
        queryset = queryset.filter(referential=referential)
    return queryset.select_related("referential").order_by("name")


def get_subset(*, tenant, subset_id=None, slug=None) -> MeasureSubset | None:
    queryset = list_subsets(tenant)
    if slug is not None:
        return queryset.filter(slug=slug).first()
    return queryset.filter(id=subset_id).first()


def create_subset(
    *, referential, slug, name, measure_codes, description="", owner_tenant=None, created_by=None
) -> MeasureSubset:
    """Compose un questionnaire à partir d'un référentiel complet et
    l'enregistre comme modèle réutilisable.

    ``measure_codes`` fixe aussi l'ORDRE de passage : composer, c'est autant
    choisir que ranger. Un code inconnu est une erreur et non un silence — un
    sous-ensemble amputé d'une mesure qu'on croyait dedans donnerait un score
    faux sans jamais le dire.
    """
    if not measure_codes:
        raise SubsetError("Un sous-ensemble doit contenir au moins une mesure.")

    par_code = {m.code: m for m in Measure.objects.filter(referential=referential)}
    inconnus = [code for code in measure_codes if code not in par_code]
    if inconnus:
        raise SubsetError(f"Mesures inconnues dans « {referential.name} » : {', '.join(inconnus)}.")

    subset, _ = MeasureSubset.objects.update_or_create(
        referential=referential,
        slug=slug,
        defaults={
            "name": name,
            "description": description,
            "owner_tenant": owner_tenant,
            "created_by": created_by,
            "is_active": True,
        },
    )
    SubsetMeasure.objects.filter(subset=subset).delete()
    SubsetMeasure.objects.bulk_create(
        [
            SubsetMeasure(subset=subset, measure=par_code[code], order=position)
            for position, code in enumerate(measure_codes, start=1)
        ]
    )
    return subset


def subset_measure_ids(subset: MeasureSubset) -> list[int]:
    return list(
        SubsetMeasure.objects.filter(subset=subset)
        .order_by("order")
        .values_list("measure_id", flat=True)
    )


# --- Surcharges d'énoncé ----------------------------------------------------


def set_measure_override(
    *, tenant, measure, plain_language: str = "", context_note: str = "", created_by=None
) -> MeasureStatementOverride:
    """Reformule une mesure pour un client. N'écrit jamais dans ``Measure``."""
    override, _ = MeasureStatementOverride.all_objects.update_or_create(
        tenant=tenant,
        measure=measure,
        defaults={
            "plain_language": plain_language,
            "context_note": context_note,
            "created_by": created_by,
        },
    )
    return override


def clear_measure_override(*, tenant, measure) -> None:
    """Retire la surcharge : l'énoncé d'origine réapparaît, intact."""
    MeasureStatementOverride.all_objects.filter(tenant=tenant, measure=measure).delete()


def list_overrides(tenant, *, referential=None):
    queryset = MeasureStatementOverride.all_objects.filter(tenant=tenant).select_related("measure")
    if referential is not None:
        queryset = queryset.filter(measure__referential=referential)
    return queryset


def apply_overrides(measures, tenant):
    """Pose les surcharges du client sur des instances ``Measure`` déjà
    chargées, en mémoire. Renvoie la même liste.

    Un attribut privé (``_override_statement``) et non le champ lui-même :
    une instance dont ``plain_language`` aurait été écrasé pourrait être
    sauvegardée par erreur et corrompre le référentiel pour tout le monde.
    ``Measure.statement`` lit l'un ou l'autre.
    """
    measures = list(measures)
    if not measures or tenant is None:
        return measures
    surcharges = {
        override.measure_id: override
        for override in MeasureStatementOverride.all_objects.filter(
            tenant=tenant, measure_id__in=[m.id for m in measures]
        )
    }
    for measure in measures:
        override = surcharges.get(measure.id)
        if override is None:
            continue
        measure._override_statement = override.plain_language
        measure._override_note = override.context_note
    return measures


# --- Structure du questionnaire ---------------------------------------------


def get_referential_structure(referential: Referential, *, tenant=None, subset=None):
    """Domaines ordonnés, chacun portant ses mesures **dans le périmètre**,
    surcharges du client appliquées.

    Renvoie une liste de dicts et non des ``Domain`` avec un prefetch : le
    filtrage par sous-ensemble et l'application des surcharges se font en
    Python, et un objet Django dont on aurait remplacé le contenu de
    ``measures`` mentirait à la lecture suivante.
    """
    measures = list(
        Measure.objects.filter(referential=referential).select_related("domain").order_by("order")
    )
    if subset is not None:
        rangs = {
            measure_id: position for position, measure_id in enumerate(subset_measure_ids(subset))
        }
        measures = sorted((m for m in measures if m.id in rangs), key=lambda m: rangs[m.id])
    apply_overrides(measures, tenant)

    par_domaine: dict[int, list] = {}
    for measure in measures:
        par_domaine.setdefault(measure.domain_id, []).append(measure)

    structure = []
    for domain in Domain.objects.filter(referential=referential).order_by("order"):
        du_domaine = par_domaine.get(domain.id, [])
        if not du_domaine:
            # Un domaine sans mesure dans le périmètre n'a rien à afficher.
            continue
        structure.append({"domain": domain, "measures": du_domaine})
    return structure


def get_referential_measures(referential: Referential):
    return list(Measure.objects.filter(referential=referential).select_related("domain"))


def get_assessment_measures(assessment: Assessment):
    """Les mesures sur lesquelles porte CETTE évaluation — le référentiel
    entier, ou le seul sous-ensemble choisi au démarrage.

    Point d'entrée unique du périmètre : progression, score et plan d'action
    en dépendent tous, et deux définitions du périmètre finiraient par
    diverger (un plan d'action listant des mesures jamais posées).
    """
    measures = get_referential_measures(assessment.referential)
    if assessment.subset_id is None:
        return measures
    rangs = {
        measure_id: position
        for position, measure_id in enumerate(subset_measure_ids(assessment.subset))
    }
    return sorted((m for m in measures if m.id in rangs), key=lambda m: rangs[m.id])


# --- Cycle de vie d'une évaluation ------------------------------------------


def get_current_assessment(tenant, *, referential=None):
    queryset = Assessment.all_objects.filter(tenant=tenant, status=Assessment.Status.IN_PROGRESS)
    if referential is not None:
        queryset = queryset.filter(referential=referential)
    return queryset.order_by("-started_at").first()


def start_or_resume_assessment(*, tenant, user, referential=None, subset=None):
    """Démarre un diagnostic, ou reprend celui en cours SUR CE RÉFÉRENTIEL.

    « En cours » se compte désormais par référentiel : un client qui en a
    deux mène deux diagnostics de front, et reprendre l'un ne doit pas
    renvoyer l'autre.
    """
    if referential is None:
        referential = get_default_referential(tenant)
    ensure_granted(tenant, referential)

    if subset is not None:
        if subset.referential_id != referential.id:
            raise SubsetError("Ce questionnaire n'appartient pas au référentiel choisi.")
        if subset.owner_tenant_id is not None and subset.owner_tenant_id != tenant.id:
            raise SubsetError("Ce questionnaire ne vous est pas accessible.")

    current = get_current_assessment(tenant, referential=referential)
    if current is not None:
        return current
    return Assessment.all_objects.create(
        tenant=tenant, referential=referential, subset=subset, started_by=user
    )


def list_assessments(tenant, *, referential=None):
    """History of a tenant's assessments, most recent first (US-2.3)."""
    queryset = Assessment.all_objects.filter(tenant=tenant).select_related("referential", "subset")
    if referential is not None:
        queryset = queryset.filter(referential=referential)
    return queryset.order_by("-started_at")


def get_latest_completed_assessment(tenant, *, referential=None):
    queryset = Assessment.all_objects.filter(tenant=tenant, status=Assessment.Status.COMPLETED)
    if referential is not None:
        queryset = queryset.filter(referential=referential)
    return queryset.order_by("-completed_at").first()


def get_assessment(*, tenant, assessment_id):
    return (
        Assessment.all_objects.filter(tenant=tenant, id=assessment_id)
        .select_related("referential", "subset")
        .first()
    )


def submit_answer(
    *, assessment: Assessment, measure: Measure, value: str, note: str = ""
) -> Answer:
    if assessment.status == Assessment.Status.COMPLETED:
        raise AssessmentAlreadyCompletedError("Cette évaluation est déjà terminée.")
    if measure.referential_id != assessment.referential_id:
        raise MeasureNotInReferentialError(
            "Cette mesure n'appartient pas au référentiel de cette évaluation."
        )
    if assessment.subset_id is not None and measure.id not in set(
        subset_measure_ids(assessment.subset)
    ):
        raise MeasureNotInScopeError(
            "Cette mesure ne fait pas partie du questionnaire de cette évaluation."
        )
    answer, _created = Answer.all_objects.update_or_create(
        assessment=assessment,
        measure=measure,
        defaults={"tenant": assessment.tenant, "value": value, "note": note},
    )
    return answer


def list_answers(assessment: Assessment):
    """Every answer recorded on ``assessment`` — used to pre-fill the
    questionnaire when a tenant resumes an in-progress assessment."""
    return Answer.all_objects.filter(
        tenant=assessment.tenant, assessment=assessment
    ).select_related("measure")


def get_progress(assessment: Assessment) -> dict:
    measures = get_assessment_measures(assessment)
    answered_ids = set(
        Answer.all_objects.filter(tenant=assessment.tenant, assessment=assessment).values_list(
            "measure_id", flat=True
        )
    )
    par_domaine: dict[int, list] = {}
    for measure in measures:
        par_domaine.setdefault(measure.domain_id, []).append(measure)

    by_domain = []
    for domain in Domain.objects.filter(referential=assessment.referential).order_by("order"):
        du_domaine = par_domaine.get(domain.id, [])
        if not du_domaine:
            continue
        by_domain.append(
            {
                "domain_code": domain.code,
                "domain_name": domain.name,
                "answered": sum(1 for m in du_domaine if m.id in answered_ids),
                "total": len(du_domaine),
            }
        )
    return {
        "answered": sum(1 for m in measures if m.id in answered_ids),
        "total": len(measures),
        "by_domain": by_domain,
    }


# --- Score ------------------------------------------------------------------


def score_from_values(measure_values: dict, measures) -> float | None:
    """Weighted score (0-100) for ``measures`` given a ``{measure_id: value}``
    mapping. Measures with no value, or an explicit "non applicable" value,
    are excluded from the denominator. Returns None when nothing scorable
    remains (e.g. every measure is N/A, or none have been answered yet) —
    never a misleading 0.

    Le poids est celui porté par la mesure (``Measure.weight``). Pour l'ANSSI
    il vaut 1.0 (standard) et 0.5 (renforcé) : le score d'un diagnostic ANSSI
    est exactement celui d'avant V2-4.

    Public and reused as-is by apps.actions.services for the projected
    score (same formula, substituting "done" action items' measures with a
    hypothetical "yes").
    """
    weighted_sum = 0.0
    weight_total = 0.0
    for measure in measures:
        value = measure_values.get(measure.id)
        if value is None or value == Answer.Value.NOT_APPLICABLE:
            continue
        weight = measure.weight
        weighted_sum += VALUE_SCORES[value] * weight
        weight_total += weight
    if weight_total == 0:
        return None
    return round(100 * weighted_sum / weight_total, 1)


def get_answer_values(assessment: Assessment) -> dict:
    """``{measure_id: value}`` for every answer recorded on ``assessment``.

    Exposed publicly so apps.actions can build a *projected* score (actual
    answers with "done" action items' measures overridden to full credit)
    via compute_scores(assessment, measure_values=...) without importing
    this app's models directly.
    """
    return dict(
        Answer.all_objects.filter(tenant=assessment.tenant, assessment=assessment).values_list(
            "measure_id", "value"
        )
    )


def compute_scores(assessment: Assessment, *, measure_values: dict | None = None) -> dict:
    """Global + per-domain weighted scores, sur le périmètre de l'évaluation.

    Reads the assessment's actual answers by default; pass
    ``measure_values`` to score a hypothetical set of answers instead (used
    by apps.actions for the plan's projected score).
    """
    measures = get_assessment_measures(assessment)
    if measure_values is None:
        measure_values = get_answer_values(assessment)

    par_domaine: dict[int, list] = {}
    for measure in measures:
        par_domaine.setdefault(measure.domain_id, []).append(measure)

    by_domain = []
    for domain in Domain.objects.filter(referential=assessment.referential).order_by("order"):
        du_domaine = par_domaine.get(domain.id, [])
        if not du_domaine:
            continue
        by_domain.append(
            {
                "domain_code": domain.code,
                "domain_name": domain.name,
                "score": score_from_values(measure_values, du_domaine),
            }
        )

    return {
        "global": score_from_values(measure_values, measures),
        "by_domain": by_domain,
    }


# --- Consolidation multi-référentiels (ADR-030) -----------------------------

# Nom de la règle, transporté dans chaque réponse d'API : un chiffre
# consolidé qui ne dit pas comment il est fabriqué n'est pas défendable en
# comité.
CONSOLIDATION_METHOD = "moyenne_par_referentiel"


def consolidated_scores(tenant, *, at=None) -> dict:
    """Le score par référentiel, et le consolidé quand il y en a plusieurs.

    **Règle (ADR-030), et elle est explicite parce qu'elle est arbitraire :**
    le consolidé est la moyenne NON pondérée des scores par référentiel —
    chaque référentiel compte pour un, quel que soit son nombre de mesures.

    Pourquoi pas une moyenne pondérée par le nombre de mesures : additionner
    les 42 mesures de l'ANSSI et les 93 contrôles de l'annexe A d'ISO 27001
    dans un même dénominateur laisserait ISO décider du chiffre à 69 %, sans
    que personne l'ait choisi. Et pourquoi pas de déduplication des mesures
    qui se recouvrent : nous n'avons aucune table de correspondance entre
    référentiels, et en inventer une reviendrait à décider que « gérer les
    mots de passe » chez l'ANSSI et chez l'ISO sont la même exigence — ce que
    ni l'un ni l'autre n'affirme.

    Le consolidé n'est donc JAMAIS rendu seul : le détail par référentiel
    l'accompagne toujours, et c'est lui qu'on lit.
    """
    lignes = []
    for referential in readable_referentials(tenant):
        queryset = Assessment.all_objects.filter(
            tenant=tenant,
            referential=referential,
            status=Assessment.Status.COMPLETED,
            score_global__isnull=False,
        )
        if at is not None:
            queryset = queryset.filter(completed_at__lte=at)
        dernier = queryset.order_by("-completed_at").first()
        if dernier is None:
            lignes.append(
                {
                    "referential_id": referential.id,
                    "referential_slug": referential.slug,
                    "referential_name": referential.name,
                    "assessment_id": None,
                    "score": None,
                    "completed_at": None,
                    "measure_count": Measure.objects.filter(referential=referential).count(),
                    "granted": is_granted(tenant, referential),
                }
            )
            continue
        lignes.append(
            {
                "referential_id": referential.id,
                "referential_slug": referential.slug,
                "referential_name": referential.name,
                "assessment_id": dernier.id,
                "score": dernier.score_global,
                "completed_at": dernier.completed_at,
                "measure_count": len(get_assessment_measures(dernier)),
                "granted": is_granted(tenant, referential),
            }
        )

    notes = [ligne["score"] for ligne in lignes if ligne["score"] is not None]
    return {
        "by_referential": lignes,
        "consolidated": round(sum(notes) / len(notes), 1) if notes else None,
        "method": CONSOLIDATION_METHOD,
        "scored_referentials": len(notes),
        # Ceux qui sont attribués mais pas encore évalués : le consolidé ne
        # les compte pas, et taire leur existence le ferait passer pour une
        # image complète.
        "unscored_referentials": [
            ligne["referential_name"] for ligne in lignes if ligne["score"] is None
        ],
    }


# --- Indicateurs pour le comité (V2-3, ADR-028) -----------------------------


def maturity_indicators(tenant, *, start, end) -> dict:
    """Maturité : le score du dernier diagnostic terminé, et la progression.

    Lit les instantanés ``score_global`` posés à la clôture de chaque
    diagnostic — jamais un recalcul. C'était déjà le choix du modèle
    (« deliberately not recomputed later ») et c'est ce qui rend la
    comparaison honnête : un score de juin recalculé avec le référentiel de
    septembre ne serait plus le score de juin.

    Multi-référentiels (V2-4, ADR-030) : ``score`` est le consolidé — la
    moyenne des derniers scores par référentiel — et ``by_referential`` porte
    le détail. Le delta n'est calculé que si CHAQUE référentiel du consolidé
    courant a lui aussi un diagnostic antérieur : comparer une moyenne de deux
    référentiels à une moyenne d'un seul afficherait une progression qui
    n'aurait eu lieu nulle part.

    Ne renvoie AUCUNE fusion avec l'exposition. Maturité et exposition
    mesurent deux choses sans rapport — l'organisation d'un côté, ce qui
    circule de l'autre — et les additionner rendrait les deux injustifiables
    (ADR-028).
    """
    termines = (
        Assessment.all_objects.filter(
            tenant=tenant,
            status=Assessment.Status.COMPLETED,
            completed_at__isnull=False,
            score_global__isnull=False,
        )
        .order_by("-completed_at")
        .values("id", "referential_id", "referential__name", "completed_at", "score_global")
    )

    dans_la_periode = [ligne for ligne in termines if ligne["completed_at"] <= end]

    courants: dict[int, dict] = {}
    precedents: dict[int, dict] = {}
    for ligne in dans_la_periode:  # déjà triés du plus récent au plus ancien
        referential_id = ligne["referential_id"]
        if referential_id not in courants:
            courants[referential_id] = ligne
        elif referential_id not in precedents:
            precedents[referential_id] = ligne

    scores_courants = [ligne["score_global"] for ligne in courants.values()]
    score = round(sum(scores_courants) / len(scores_courants), 1) if scores_courants else None

    # Delta seulement si l'ensemble comparé est le même des deux côtés.
    comparable = bool(courants) and set(courants) == set(precedents)
    scores_precedents = (
        [precedents[ref_id]["score_global"] for ref_id in courants] if comparable else []
    )
    previous_score = (
        round(sum(scores_precedents) / len(scores_precedents), 1) if scores_precedents else None
    )

    dernier = max(courants.values(), key=lambda ligne: ligne["completed_at"], default=None)
    precedent_le_plus_recent = (
        max(precedents.values(), key=lambda ligne: ligne["completed_at"], default=None)
        if comparable
        else None
    )

    historique = [
        {
            "date": ligne["completed_at"],
            "score": ligne["score_global"],
            "referential": ligne["referential__name"],
        }
        for ligne in dans_la_periode
        if ligne["completed_at"] >= start
    ]
    historique.reverse()

    return {
        "score": score,
        "measured_at": dernier["completed_at"] if dernier else None,
        "previous_score": previous_score,
        "previous_measured_at": (
            precedent_le_plus_recent["completed_at"] if precedent_le_plus_recent else None
        ),
        "delta": (
            round(score - previous_score, 1)
            if score is not None and previous_score is not None
            else None
        ),
        "completed_in_period": len(historique),
        "history": historique,
        # Le détail derrière le consolidé (ADR-030) : jamais le chiffre seul.
        "referential_count": len(courants),
        "method": CONSOLIDATION_METHOD if len(courants) > 1 else None,
        "by_referential": [
            {
                "referential": ligne["referential__name"],
                "score": ligne["score_global"],
                "measured_at": ligne["completed_at"],
                "assessment_id": ligne["id"],
            }
            for ligne in sorted(courants.values(), key=lambda ligne: ligne["referential__name"])
        ],
    }


def complete_assessment(assessment: Assessment) -> Assessment:
    if assessment.status == Assessment.Status.COMPLETED:
        raise AssessmentAlreadyCompletedError("Cette évaluation est déjà terminée.")

    total = len(get_assessment_measures(assessment))
    answered = Answer.all_objects.filter(tenant=assessment.tenant, assessment=assessment).count()
    if answered < total:
        raise IncompleteAssessmentError(answered, total)

    scores = compute_scores(assessment)
    assessment.status = Assessment.Status.COMPLETED
    assessment.completed_at = timezone.now()
    assessment.score_global = scores["global"]
    assessment.save(update_fields=["status", "completed_at", "score_global"])
    return assessment
