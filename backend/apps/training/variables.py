"""Les variables contextuelles d'un cours (F2, ADR-040).

Ce qu'aucun catalogue de formation ne sait faire : écrire « votre entreprise a
eu 4 comptes compromis » dans un cours, avec le chiffre réel du client qui le
suit.

Trois règles commandent tout ce fichier, et elles sont dans le code plutôt que
dans une consigne de rédaction :

1. **Aucune donnée nominative, par construction.** Une variable rend un
   NOMBRE, jamais du texte. Il n'existe donc aucun chemin par lequel un nom,
   une adresse ou un domaine pourrait se retrouver dans un cours — pas même
   par erreur d'un auteur. Un test l'épingle en vérifiant le type rendu.
2. **Aucun mot de passe, même partiel.** Conséquence directe de la règle 1 :
   il n'y a pas de variable de texte.
3. **Un petit nombre désigne une personne.** Dans une entreprise de six
   salariés, « 1 compte compromis » dit à tout le monde de qui il s'agit. En
   dessous de ``SEUIL_DISCRETION``, la valeur est traitée comme indisponible
   et l'écran bascule sur sa formulation de repli. C'est la règle que la
   consigne « jamais de donnée nominative » ne couvrait pas.
"""

from collections.abc import Callable
from dataclasses import dataclass

from apps.billing import features

#: En dessous de ce décompte, on ne donne pas le chiffre.
#:
#: Trois est un choix, pas un seuil réglementaire : c'est le premier nombre
#: au-dessus duquel un salarié ne peut plus deviner « c'est moi » ou « c'est
#: lui » dans une équipe réduite. Ne s'applique qu'aux DÉCOMPTES de personnes
#: ou de comptes — un score sur 100 ne désigne personne.
SEUIL_DISCRETION = 3


@dataclass(frozen=True)
class Variable:
    cle: str
    libelle: str
    description: str
    #: Rend un entier, ou None quand la donnée n'existe pas.
    resoudre: Callable
    #: Vrai pour un décompte de comptes ou de personnes — donc soumis au seuil
    #: de discrétion. Faux pour un score, qui ne désigne personne.
    est_un_decompte: bool = True
    #: Clé d'offre nécessaire. Vide = disponible à tous. Un client dont
    #: l'offre ne comprend pas la clé reçoit la formulation de repli, jamais
    #: une erreur ni un blanc.
    feature: str = ""


def _fuites_critiques(tenant):
    from apps.threat_intelligence import services as ti

    return ti.count_critical_open_findings(tenant)


def _fuites_ouvertes(tenant):
    from apps.threat_intelligence import services as ti

    return len(list(ti.list_findings(tenant, status="open")))


def _score_exposition(tenant):
    from django.utils import timezone

    from apps.threat_intelligence import services as ti

    return ti.exposure_score_at(tenant, timezone.now())


def _score_maturite(tenant):
    from apps.assessments import services as assessments

    consolide = assessments.consolidated_scores(tenant).get("consolidated")
    return None if consolide is None else round(consolide)


def _actifs_surveilles(tenant):
    from apps.monitoring import services as monitoring

    return monitoring.list_assets(tenant).count()


REGISTRE: dict[str, Variable] = {
    variable.cle: variable
    for variable in [
        Variable(
            "fuites_ouvertes",
            "Compromissions ouvertes",
            "Nombre de comptes de l'entreprise retrouvés dans une fuite et non encore traités.",
            _fuites_ouvertes,
        ),
        Variable(
            "fuites_critiques",
            "Compromissions critiques ouvertes",
            "Parmi les précédentes, celles jugées critiques.",
            _fuites_critiques,
        ),
        Variable(
            "score_exposition",
            "Score d'exposition",
            "Sur 100. Plus il est bas, mieux c'est.",
            _score_exposition,
            est_un_decompte=False,
        ),
        Variable(
            "score_maturite",
            "Score de maturité",
            "Sur 100, d'après le ou les référentiels du client.",
            _score_maturite,
            est_un_decompte=False,
        ),
        Variable(
            "actifs_surveilles",
            "Actifs surveillés",
            "Nombre de sites et de domaines déclarés par l'entreprise.",
            _actifs_surveilles,
            # Un actif n'est pas une personne : pas de seuil de discrétion.
            est_un_decompte=False,
            feature=features.REALTIME_MONITORING,
        ),
    ]
}


def cles_connues() -> list[str]:
    return list(REGISTRE)


def catalogue() -> list[dict]:
    """Ce que le studio propose à l'auteur. On n'écrit pas une variable qui
    n'existe pas : la liste vient d'ici, jamais de la mémoire de l'auteur."""
    return [
        {
            "cle": variable.cle,
            "libelle": variable.libelle,
            "description": variable.description,
            "exemple": "12" if variable.est_un_decompte else "68",
            "feature": variable.feature,
        }
        for variable in REGISTRE.values()
    ]


class ValeurIndisponible(Exception):
    """La variable ne peut pas être servie à ce client : donnée absente, nulle,
    trop petite pour être discrète, ou hors de son offre."""


def valeur(cle: str, tenant) -> int:
    """La valeur d'une variable pour ce client, ou ``ValeurIndisponible``.

    Ne rend JAMAIS zéro : un cours qui afficherait « vous avez eu 0 incident »
    sur le ton de l'alerte serait au mieux ridicule, au pire inquiétant pour
    rien. L'absence de problème se dit avec des mots, pas avec un zéro — c'est
    le rôle de la formulation de repli.
    """
    variable = REGISTRE.get(cle)
    if variable is None:
        raise ValeurIndisponible(f"Variable inconnue : {cle}")

    if variable.feature:
        from apps.billing import entitlements

        if not entitlements.has_feature(tenant, variable.feature):
            raise ValeurIndisponible(f"Hors de l'offre du client : {cle}")

    try:
        brute = variable.resoudre(tenant)
    except Exception as exc:  # noqa: BLE001 - une panne de calcul n'est pas une panne de cours
        raise ValeurIndisponible(f"Calcul impossible pour {cle} : {exc}") from exc

    if brute is None or brute <= 0:
        raise ValeurIndisponible(f"Aucune donnée pour {cle}")

    if variable.est_un_decompte and brute < SEUIL_DISCRETION:
        # Voir SEUIL_DISCRETION : un très petit nombre désigne quelqu'un.
        raise ValeurIndisponible(f"Sous le seuil de discrétion pour {cle}")

    return int(brute)
