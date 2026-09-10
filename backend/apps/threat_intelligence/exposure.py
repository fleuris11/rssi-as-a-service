"""Score d'exposition par actif — déterministe et explicable (ADR-016).

Aucune IA n'intervient ici, et c'est une décision, pas une simplification :
un score présenté à un client doit être **reproductible** (deux calculs sur
les mêmes données donnent le même chiffre) et **justifiable** (« pourquoi
78 ? » doit avoir une réponse exacte, pas une intuition de modèle). La
fonction renvoie donc toujours ses composantes en même temps que son total.

Le score est volontairement **borné à 100 et non linéaire** : dix fuites
mineures ne doivent pas dépasser une fuite critique fraîche avec secret
révélable. On additionne des contributions décroissantes plutôt qu'un
simple total, et on plafonne.
"""

from dataclasses import dataclass, field

from django.conf import settings
from django.db.models import BooleanField, Case, Q, Value, When
from django.utils import timezone

from .models import BreachFinding

MAX_SCORE = 100

LEVEL_CALM = "calme"
LEVEL_WATCH = "a_surveiller"
LEVEL_CONCERNING = "preoccupant"
LEVEL_CRITICAL = "critique"

LEVEL_LABELS = {
    LEVEL_CALM: "Calme",
    LEVEL_WATCH: "À surveiller",
    LEVEL_CONCERNING: "Préoccupant",
    LEVEL_CRITICAL: "Critique",
}

# Poids de base par sévérité — l'ordre de grandeur qui fait qu'une fuite
# critique pèse structurellement plus que plusieurs fuites mineures.
SEVERITY_WEIGHTS = {
    BreachFinding.Severity.CRITICAL: 40,
    BreachFinding.Severity.HIGH: 22,
    BreachFinding.Severity.ATTENTION: 8,
}

# Fraîcheur : une fuite d'il y a trois ans n'appelle pas la même urgence
# qu'une fuite de la semaine dernière (le mot de passe a souvent déjà
# changé). Multiplicateur appliqué au poids de sévérité.
FRESHNESS_TIERS = (
    (30, 1.0, "moins d'un mois"),
    (90, 0.85, "moins de trois mois"),
    (365, 0.6, "moins d'un an"),
)
FRESHNESS_OLD_MULTIPLIER = 0.35
FRESHNESS_OLD_LABEL = "plus d'un an"

# Un secret réellement révélable (ADR-014) rend la fuite immédiatement
# exploitable : c'est un facteur aggravant, pas une catégorie à part.
REVEALABLE_SECRET_BONUS = 10

# Amortissement des fuites suivantes sur un même actif : la 1re compte
# pleinement, la 2e à 60 %, la 3e à 36 %... Empêche qu'un grand nombre de
# fuites anciennes et mineures sature le score.
ADDITIONAL_FINDING_DECAY = 0.6


@dataclass
class ScoreComponent:
    """Une ligne du « pourquoi ce score » — restituée telle quelle par l'API."""

    finding_id: int
    label: str
    severity: str
    points: int
    detail: str


@dataclass
class ExposureScore:
    score: int
    level: str
    level_label: str
    components: list[ScoreComponent] = field(default_factory=list)
    findings_count: int = 0

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "level": self.level,
            "level_label": self.level_label,
            "findings_count": self.findings_count,
            "components": [
                {
                    "finding_id": c.finding_id,
                    "label": c.label,
                    "severity": c.severity,
                    "points": c.points,
                    "detail": c.detail,
                }
                for c in self.components
            ],
        }


def _freshness(finding: BreachFinding, now) -> tuple[float, str]:
    """Multiplicateur de fraîcheur + libellé lisible. On se base sur la date
    de fuite quand le fournisseur la donne, sinon sur la date de détection —
    jamais sur rien, sinon une fuite sans date échapperait à l'amortissement."""
    reference = finding.breach_date
    if reference is not None:
        age_days = (now.date() - reference).days
    else:
        age_days = (now - finding.detected_at).days
    age_days = max(0, age_days)

    for max_days, multiplier, label in FRESHNESS_TIERS:
        if age_days < max_days:
            return multiplier, label
    return FRESHNESS_OLD_MULTIPLIER, FRESHNESS_OLD_LABEL


def level_for(score: int) -> str:
    thresholds = settings.EXPOSURE_LEVEL_THRESHOLDS
    if score >= thresholds["critical"]:
        return LEVEL_CRITICAL
    if score >= thresholds["concerning"]:
        return LEVEL_CONCERNING
    if score >= thresholds["watch"]:
        return LEVEL_WATCH
    return LEVEL_CALM


def compute_exposure_score(findings: list[BreachFinding], *, now=None) -> ExposureScore:
    """Score 0-100 pour un ensemble de fuites **ouvertes** d'un même actif.

    Les fuites traitées/ignorées ne sont pas passées ici : traiter une fuite
    doit faire baisser le score, c'est tout l'intérêt du geste pour le
    dirigeant. L'appelant filtre donc en amont (voir services.build_exposure_feed).
    """
    now = now or timezone.now()
    # Contribution décroissante : on classe d'abord par poids brut décroissant
    # pour que l'amortissement s'applique aux fuites les MOINS graves — sinon
    # traiter la fuite la plus grave ferait remonter le poids d'une autre.
    scored = []
    for finding in findings:
        multiplier, freshness_label = _freshness(finding, now)
        base = SEVERITY_WEIGHTS.get(
            finding.severity, SEVERITY_WEIGHTS[BreachFinding.Severity.ATTENTION]
        )
        raw = base * multiplier
        if finding.has_secret and bytes(finding.secret_encrypted):
            raw += REVEALABLE_SECRET_BONUS
        scored.append((raw, freshness_label, finding))

    scored.sort(key=lambda item: item[0], reverse=True)

    total = 0.0
    components: list[ScoreComponent] = []
    for rank, (raw, freshness_label, finding) in enumerate(scored):
        decayed = raw * (ADDITIONAL_FINDING_DECAY**rank)
        total += decayed
        points = int(round(decayed))
        detail_parts = [
            f"gravité {BreachFinding.Severity(finding.severity).label.lower()}",
            f"fuite {freshness_label}",
        ]
        if finding.has_secret and bytes(finding.secret_encrypted):
            detail_parts.append("mot de passe récupérable")
        if rank > 0:
            detail_parts.append(f"{rank + 1}e fuite sur cet actif, pondérée à la baisse")
        # Une composante à 0 point n'explique rien : elle dit « cette fuite
        # n'a pas bougé le score ». Avec un amortissement de 0,6 par rang,
        # tout ce qui suit le 30e environ retombe à zéro — sur un actif réel
        # de production, cela faisait 28 420 lignes de « 4 231e fuite,
        # pondérée à la baisse — 0 point », transportées jusqu'au navigateur
        # et rendues à l'écran. Le total, lui, continue de sommer TOUTES les
        # fuites juste au-dessus : le score reste exact au point près, seule
        # sa justification s'arrête là où elle cesse d'être une justification.
        if points <= 0:
            continue
        components.append(
            ScoreComponent(
                finding_id=finding.id,
                label=BreachFinding.SourceEndpoint(finding.source_endpoint).label,
                severity=finding.severity,
                points=points,
                detail=", ".join(detail_parts),
            )
        )

    score = min(MAX_SCORE, int(round(total)))
    level = level_for(score)
    return ExposureScore(
        score=score,
        level=level,
        level_label=LEVEL_LABELS[level],
        components=components,
        findings_count=len(findings),
    )


# --- Score sans matérialiser d'objets (V2-3) --------------------------------
#
# Le tableau de bord a besoin du score à plusieurs dates. Le calculer par le
# chemin habituel supposerait de charger, pour chacune, l'ensemble des fuites
# ouvertes à cette date-là : sur l'actif réel qui en porte 28 450, la seule
# matérialisation des instances Django coûtait 3,79 s (mesuré le 06/09/2026,
# journal du même jour). Deux dates, et le tableau de bord dépasse les huit
# secondes avant d'avoir affiché quoi que ce soit.
#
# La leçon de ce jour-là était que le coût vient des OBJETS, pas des données :
# un `defer()` sur les colonnes larges n'avait rien changé. Cette fonction
# prend donc des n-uplets bruts (`values_list`), pas des instances.
#
# Elle ne rend que le total et le niveau — pas les composantes, qui n'ont de
# sens que dans le fil d'exposition où l'on explique fuite par fuite. Un test
# vérifie qu'elle donne EXACTEMENT le même score que la fonction complète sur
# les mêmes données : deux calculs qui divergeraient seraient pires que pas de
# tableau de bord (l'écran de détail et le tableau de bord se contrediraient).

#: Colonnes à demander à la base, dans cet ordre, pour alimenter
#: ``score_from_rows``. Défini ici pour que l'appelant ne puisse pas se
#: tromper d'ordre ni en oublier une.
#:
#: ``is_revealable`` est une ANNOTATION, pas une colonne — voir
#: ``annotate_revealable``. Rapatrier ``secret_encrypted`` lui-même coûtait
#: cher pour rien : le score n'a besoin que de savoir s'il est vide, et ce
#: sont des blocs chiffrés de plusieurs centaines d'octets. Sur 28 450 fuites,
#: c'est plusieurs mégaoctets transportés pour produire un booléen.
SCORE_ROW_FIELDS = ("severity", "breach_date", "detected_at", "is_revealable")


def annotate_revealable(queryset):
    """Ajoute ``is_revealable`` : le secret existe ET n'est pas vide.

    Calculé par la base. La condition est exactement celle de
    ``compute_exposure_score`` (``finding.has_secret and
    bytes(finding.secret_encrypted)``) — un test compare les deux chemins sur
    les mêmes données, parce que deux définitions du même bonus finiraient par
    diverger.
    """
    return queryset.annotate(
        is_revealable=Case(
            When(Q(has_secret=True) & ~Q(secret_encrypted=b""), then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    )


def _freshness_multiplier(breach_date, detected_at, now) -> float:
    reference = breach_date
    if reference is not None:
        age_days = (now.date() - reference).days
    else:
        age_days = (now - detected_at).days
    age_days = max(0, age_days)
    for max_days, multiplier, _label in FRESHNESS_TIERS:
        if age_days < max_days:
            return multiplier
    return FRESHNESS_OLD_MULTIPLIER


def score_from_rows(rows, *, now=None) -> int:
    """Score 0-100 à partir de n-uplets ``SCORE_ROW_FIELDS``.

    Même formule, mêmes constantes et même ordre de tri que
    ``compute_exposure_score`` — volontairement, puisque c'est la seule chose
    qui garantit que les deux ne divergent pas.
    """
    now = now or timezone.now()

    raws = []
    for severity, breach_date, detected_at, is_revealable in rows:
        base = SEVERITY_WEIGHTS.get(severity, SEVERITY_WEIGHTS[BreachFinding.Severity.ATTENTION])
        raw = base * _freshness_multiplier(breach_date, detected_at, now)
        if is_revealable:
            raw += REVEALABLE_SECRET_BONUS
        raws.append(raw)

    raws.sort(reverse=True)
    total = sum(raw * (ADDITIONAL_FINDING_DECAY**rang) for rang, raw in enumerate(raws))
    return min(MAX_SCORE, int(round(total)))


def freshness_sort_key(finding: BreachFinding):
    """Tri intra-groupe : sévérité décroissante puis fraîcheur décroissante —
    ce qu'un dirigeant doit regarder en premier, en haut."""
    severity_rank = {
        BreachFinding.Severity.CRITICAL: 0,
        BreachFinding.Severity.HIGH: 1,
        BreachFinding.Severity.ATTENTION: 2,
    }
    reference = finding.breach_date or finding.detected_at.date()
    return (severity_rank.get(finding.severity, 99), -reference.toordinal())


__all__ = [
    "MAX_SCORE",
    "LEVEL_CALM",
    "LEVEL_WATCH",
    "LEVEL_CONCERNING",
    "LEVEL_CRITICAL",
    "LEVEL_LABELS",
    "SEVERITY_WEIGHTS",
    "REVEALABLE_SECRET_BONUS",
    "ADDITIONAL_FINDING_DECAY",
    "ExposureScore",
    "ScoreComponent",
    "compute_exposure_score",
    "score_from_rows",
    "annotate_revealable",
    "SCORE_ROW_FIELDS",
    "level_for",
    "freshness_sort_key",
]
