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
    "level_for",
    "freshness_sort_key",
]
