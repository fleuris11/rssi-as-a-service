"""Périodes de restitution (V2-3, ADR-028).

Un comité se prépare sur une période, pas sur un instant. Ce module traduit
ce que le RSSI choisit à l'écran — « ce trimestre », « depuis janvier », deux
dates — en un couple de bornes, plus **les bornes de la période précédente**
de même longueur.

Cette période précédente n'est pas un supplément : c'est ce qui transforme un
chiffre en information. « 14 fuites ouvertes » ne dit rien ; « 14 contre 31 il
y a trois mois » dit que le travail a porté.

Volontairement sans état et sans base : une période est un calcul sur des
dates, il n'y a rien à stocker et rien à migrer.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.utils import timezone

PRESET_30D = "30d"
PRESET_QUARTER = "quarter"
PRESET_SEMESTER = "semester"
PRESET_YEAR = "year"
PRESET_CUSTOM = "custom"

#: Durée de chaque période prédéfinie, en jours. Le trimestre vaut 91 jours et
#: non « trois mois calendaires » : la comparaison à la période précédente
#: n'a de sens que si les deux durées sont égales, et deux trimestres
#: calendaires n'ont pas le même nombre de jours.
PRESET_DAYS = {
    PRESET_30D: 30,
    PRESET_QUARTER: 91,
    PRESET_SEMESTER: 182,
    PRESET_YEAR: 365,
}

PRESET_LABELS = {
    PRESET_30D: "30 derniers jours",
    PRESET_QUARTER: "Trimestre",
    PRESET_SEMESTER: "Semestre",
    PRESET_YEAR: "Année",
    PRESET_CUSTOM: "Période personnalisée",
}

DEFAULT_PRESET = PRESET_QUARTER

#: Plafond d'une plage personnalisée. Cinq ans couvre largement l'usage réel
#: (un comité regarde un trimestre, parfois un exercice) et borne le coût des
#: séries quotidiennes : au-delà, la série ferait plus de points que de pixels.
MAX_CUSTOM_DAYS = 366 * 5


class PeriodError(ValueError):
    """Période invalide — message destiné au client."""


@dataclass(frozen=True)
class Period:
    """Une période et celle qui la précède, de même durée."""

    key: str
    label: str
    start: datetime
    end: datetime
    previous_start: datetime
    previous_end: datetime

    @property
    def days(self) -> int:
        return (self.end.date() - self.start.date()).days + 1

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "start": self.start,
            "end": self.end,
            "previous_start": self.previous_start,
            "previous_end": self.previous_end,
            "days": self.days,
        }


def _debut_de_jour(jour):
    return timezone.make_aware(datetime.combine(jour, time.min), timezone.get_current_timezone())


def _fin_de_jour(jour):
    return timezone.make_aware(datetime.combine(jour, time.max), timezone.get_current_timezone())


def resolve(key: str | None = None, *, start=None, end=None, now=None) -> Period:
    """Bornes de la période demandée, et de celle qui la précède.

    Les bornes sont posées sur des JOURS entiers (minuit → 23 h 59 min 59 s) :
    un comité raisonne en jours, et une borne à l'heure près ferait varier les
    chiffres selon le moment où la page est ouverte — deux consultations le
    même après-midi ne donneraient pas le même total.
    """
    now = now or timezone.now()
    key = key or DEFAULT_PRESET

    if key == PRESET_CUSTOM:
        if start is None or end is None:
            raise PeriodError("Indiquez une date de début et une date de fin.")
        if start > end:
            raise PeriodError("La date de début doit précéder la date de fin.")
        debut, fin = _debut_de_jour(start), _fin_de_jour(end)
        jours = (end - start).days + 1
        if jours > MAX_CUSTOM_DAYS:
            raise PeriodError("La période demandée est trop longue (cinq ans au maximum).")
        libelle = PRESET_LABELS[PRESET_CUSTOM]
    else:
        if key not in PRESET_DAYS:
            raise PeriodError("Période inconnue.")
        jours = PRESET_DAYS[key]
        # ``localdate`` et non ``now.date()`` : ``now`` est en UTC, et les
        # bornes sont posées dans le fuseau d'affichage (Europe/Paris). Entre
        # minuit et deux heures du matin, la date UTC est encore celle de la
        # veille : la période se terminait alors « hier à 23 h 59 heure de
        # Paris », c'est-à-dire DANS LE PASSÉ, et le tableau de bord perdait
        # silencieusement tout ce qui s'était produit dans les deux dernières
        # heures. Défaut trouvé en V2-5 en lançant la suite à 1 h 50.
        aujourd_hui = timezone.localdate(now)
        fin = _fin_de_jour(aujourd_hui)
        debut = _debut_de_jour(aujourd_hui - timedelta(days=jours - 1))
        libelle = PRESET_LABELS[key]

    precedente_fin = debut - timedelta(microseconds=1)
    precedente_debut = _debut_de_jour((debut - timedelta(days=jours)).date())

    return Period(
        key=key,
        label=libelle,
        start=debut,
        end=fin,
        previous_start=precedente_debut,
        previous_end=precedente_fin,
    )


def available() -> list[dict]:
    """Ce que l'écran propose. Servi par l'API pour que le frontend n'ait pas
    à recopier la liste — une liste recopiée finit par diverger."""
    return [
        {"key": key, "label": PRESET_LABELS[key], "days": PRESET_DAYS[key]}
        for key in (PRESET_30D, PRESET_QUARTER, PRESET_SEMESTER, PRESET_YEAR)
    ] + [{"key": PRESET_CUSTOM, "label": PRESET_LABELS[PRESET_CUSTOM], "days": None}]
