"""Lecture d'un fichier de référentiel, et son écriture en base.

Deux formats d'entrée, un seul chemin d'écriture (``import_referential``) :

- **JSON** — la forme de référence, documentée dans
  ``docs/format_import_referentiel.md`` ;
- **CSV / tableur** — une ligne par mesure, pour les référentiels qu'on
  reçoit sous forme de tableur (c'est le cas le plus fréquent chez un client
  qui a écrit le sien).

Le parseur accepte aussi la forme **héritée** du fichier ANSSI
(``official`` / ``simplified`` / ``product_rating``), qui sépare la donnée
officielle de la couche produit. Ce fichier est vérifié ligne à ligne contre
le PDF source (docs/verification_referentiel_anssi.md) : le convertir pour
faire plaisir à un nouveau format aurait invalidé cette vérification pour
rien.

**Droits.** L'importateur ne juge pas ce qu'on a le droit d'importer — il
enregistre ce que le fichier déclare (``kind``, ``licence_notice``). Le dépôt
n'embarque que l'ANSSI, sous Licence Ouverte. ISO 27001, le NIST CSF et les
CIS Controls sont fournis comme **structure d'accueil vide** : c'est
l'exploitant ou le client, détenteur de la licence, qui importe le contenu.
"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from .models import Domain, Measure, Referential
from .services import ANSSI_LEVEL_WEIGHTS

DEFAULT_EFFORT = Measure.Effort.MEDIUM
DEFAULT_IMPACT = Measure.Impact.MEDIUM

# Colonnes du format tableur. En français : ce fichier est rempli par un
# client ou un consultant, pas par un développeur.
CSV_COLUMNS = [
    "domaine_code",
    "domaine_nom",
    "domaine_ordre",
    "mesure_code",
    "mesure_numero",
    "intitule_officiel",
    "enonce_clair",
    "niveau",
    "poids",
    "effort",
    "impact",
]


class ReferentialImportError(Exception):
    """Fichier invalide. Toujours levée AVANT la moindre écriture."""


@dataclass
class ParsedMeasure:
    code: str
    official_title: str
    plain_language: str
    number: int | None = None
    level: str = ""
    weight: float = 1.0
    effort: str = DEFAULT_EFFORT
    impact: str = DEFAULT_IMPACT
    effort_impact_disclaimer: bool = True


@dataclass
class ParsedDomain:
    code: str
    name: str
    order: int
    description: str = ""
    measures: list[ParsedMeasure] = field(default_factory=list)


@dataclass
class ParsedReferential:
    slug: str
    name: str
    version: str
    description: str = ""
    publisher: str = ""
    kind: str = Referential.Kind.OPEN
    source_url: str = ""
    licence_notice: str = ""
    domains: list[ParsedDomain] = field(default_factory=list)

    @property
    def measure_count(self) -> int:
        return sum(len(domain.measures) for domain in self.domains)


def _float(value, *, default: float, label: str) -> float:
    if value in (None, ""):
        return default
    try:
        poids = float(value)
    except (TypeError, ValueError) as exc:
        raise ReferentialImportError(f"{label} : poids illisible ({value!r}).") from exc
    if poids <= 0:
        raise ReferentialImportError(
            f"{label} : le poids doit être strictement positif (reçu {poids})."
        )
    return poids


def _choice(value, *, choices, default: str, label: str, champ: str) -> str:
    if value in (None, ""):
        return default
    valeur = str(value).strip().lower()
    if valeur not in choices:
        raise ReferentialImportError(
            f"{label} : {champ} « {value} » inconnu (valeurs admises : {', '.join(choices)})."
        )
    return valeur


def _parse_measure(raw: dict, *, label: str) -> ParsedMeasure:
    """Une mesure, dans la forme générique OU dans la forme héritée ANSSI."""
    if "official" in raw:
        # Forme héritée : la donnée officielle d'un côté, la couche produit de
        # l'autre. Le poids n'y figure pas — il se déduit du niveau ANSSI.
        official = raw["official"]
        simplified = raw.get("simplified", {})
        rating = raw.get("product_rating", {})
        numero = official.get("number")
        code = str(official.get("code") or numero or "").strip()
        niveau = official.get("level", "")
        return ParsedMeasure(
            code=code,
            number=numero,
            official_title=official.get("title", "").strip(),
            plain_language=simplified.get("question", "").strip(),
            level=niveau,
            weight=ANSSI_LEVEL_WEIGHTS.get(niveau, 1.0),
            effort=_choice(
                rating.get("effort"),
                choices=Measure.Effort.values,
                default=DEFAULT_EFFORT,
                label=label,
                champ="effort",
            ),
            impact=_choice(
                rating.get("impact"),
                choices=Measure.Impact.values,
                default=DEFAULT_IMPACT,
                label=label,
                champ="impact",
            ),
            effort_impact_disclaimer=bool(rating.get("disclaimer", True)),
        )

    code = str(raw.get("code", "")).strip()
    numero = raw.get("number")
    return ParsedMeasure(
        code=code,
        number=int(numero) if numero not in (None, "") else None,
        official_title=str(raw.get("title", "")).strip(),
        plain_language=str(raw.get("statement", raw.get("plain_language", ""))).strip(),
        level=str(raw.get("level", "")).strip(),
        weight=_float(raw.get("weight"), default=1.0, label=label),
        effort=_choice(
            raw.get("effort"),
            choices=Measure.Effort.values,
            default=DEFAULT_EFFORT,
            label=label,
            champ="effort",
        ),
        impact=_choice(
            raw.get("impact"),
            choices=Measure.Impact.values,
            default=DEFAULT_IMPACT,
            label=label,
            champ="impact",
        ),
        effort_impact_disclaimer=bool(raw.get("effort_impact_disclaimer", True)),
    )


def parse_json(data: dict) -> ParsedReferential:
    for champ in ("slug", "name", "version"):
        if not data.get(champ):
            raise ReferentialImportError(f"Champ obligatoire manquant à la racine : « {champ} ».")
    if not data.get("domains"):
        raise ReferentialImportError("Le référentiel ne contient aucun domaine.")

    parsed = ParsedReferential(
        slug=data["slug"],
        name=data["name"],
        version=str(data["version"]),
        description=data.get("description", ""),
        publisher=data.get("publisher", ""),
        kind=_choice(
            data.get("kind"),
            choices=Referential.Kind.values,
            default=Referential.Kind.OPEN,
            label="Référentiel",
            champ="kind",
        ),
        source_url=data.get("source_url", ""),
        licence_notice=data.get("licence_notice", ""),
    )

    for position, domaine in enumerate(data["domains"], start=1):
        code = str(domaine.get("code", "")).strip()
        if not code:
            raise ReferentialImportError(f"Domaine n°{position} : « code » manquant.")
        parsed_domain = ParsedDomain(
            code=code,
            name=domaine.get("name", code),
            order=int(domaine.get("order", position)),
            description=domaine.get("description", ""),
        )
        for mesure in domaine.get("measures", []):
            label = f"Domaine « {code} »"
            # Contrôle hérité, conservé : une mesure qui déclare un domaine
            # différent de son parent est une erreur de copie, pas un détail.
            declare = mesure.get("official", {}).get("domain") or mesure.get("domain")
            if declare and declare != code:
                raise ReferentialImportError(
                    f"{label} : une mesure déclare le domaine « {declare} », qui n'est pas "
                    "son domaine parent."
                )
            parsed_domain.measures.append(_parse_measure(mesure, label=label))
        parsed.domains.append(parsed_domain)

    return _validate(parsed)


def parse_csv(rows, *, header: dict) -> ParsedReferential:
    """``rows`` : les lignes du tableur. ``header`` : les métadonnées du
    référentiel, passées en options de la commande — un CSV ne sait pas porter
    d'en-tête structuré, et les répéter sur chaque ligne inviterait à les
    contredire."""
    for champ in ("slug", "name", "version"):
        if not header.get(champ):
            raise ReferentialImportError(
                f"Métadonnée obligatoire manquante pour un import CSV : « {champ} » "
                "(option --slug / --name / --ref-version)."
            )

    parsed = ParsedReferential(
        slug=header["slug"],
        name=header["name"],
        version=str(header["version"]),
        description=header.get("description", ""),
        publisher=header.get("publisher", ""),
        kind=header.get("kind", Referential.Kind.OPEN),
        source_url=header.get("source_url", ""),
        licence_notice=header.get("licence_notice", ""),
    )

    par_code: dict[str, ParsedDomain] = {}
    for numero_ligne, row in enumerate(rows, start=2):  # ligne 1 = en-têtes
        manquantes = [c for c in ("domaine_code", "mesure_code") if not (row.get(c) or "").strip()]
        if manquantes:
            raise ReferentialImportError(
                f"Ligne {numero_ligne} : colonne(s) obligatoire(s) vide(s) : "
                f"{', '.join(manquantes)}."
            )
        code_domaine = row["domaine_code"].strip()
        if code_domaine not in par_code:
            par_code[code_domaine] = ParsedDomain(
                code=code_domaine,
                name=(row.get("domaine_nom") or code_domaine).strip(),
                order=int(row.get("domaine_ordre") or len(par_code) + 1),
            )
            parsed.domains.append(par_code[code_domaine])

        label = f"Ligne {numero_ligne}"
        numero = (row.get("mesure_numero") or "").strip()
        par_code[code_domaine].measures.append(
            ParsedMeasure(
                code=row["mesure_code"].strip(),
                number=int(numero) if numero else None,
                official_title=(row.get("intitule_officiel") or "").strip(),
                plain_language=(row.get("enonce_clair") or "").strip(),
                level=(row.get("niveau") or "").strip(),
                weight=_float(row.get("poids"), default=1.0, label=label),
                effort=_choice(
                    row.get("effort"),
                    choices=Measure.Effort.values,
                    default=DEFAULT_EFFORT,
                    label=label,
                    champ="effort",
                ),
                impact=_choice(
                    row.get("impact"),
                    choices=Measure.Impact.values,
                    default=DEFAULT_IMPACT,
                    label=label,
                    champ="impact",
                ),
            )
        )

    return _validate(parsed)


def _validate(parsed: ParsedReferential) -> ParsedReferential:
    if not parsed.domains:
        raise ReferentialImportError("Le référentiel ne contient aucun domaine.")

    codes_domaines = [d.code for d in parsed.domains]
    doublons_domaines = {c for c in codes_domaines if codes_domaines.count(c) > 1}
    if doublons_domaines:
        raise ReferentialImportError(
            f"Codes de domaine en double : {', '.join(sorted(doublons_domaines))}."
        )

    tous_codes: list[str] = []
    for domaine in parsed.domains:
        if not domaine.measures:
            raise ReferentialImportError(
                f"Le domaine « {domaine.code} » ne contient aucune mesure."
            )
        for mesure in domaine.measures:
            if not mesure.code:
                raise ReferentialImportError(
                    f"Domaine « {domaine.code} » : une mesure n'a pas de code."
                )
            if not mesure.official_title:
                raise ReferentialImportError(
                    f"Mesure « {mesure.code} » : intitulé officiel manquant."
                )
            if not mesure.plain_language:
                # L'énoncé en langage clair est ce que le dirigeant LIT. Une
                # mesure sans lui donnerait une question vide à l'écran.
                raise ReferentialImportError(
                    f"Mesure « {mesure.code} » : énoncé en langage clair manquant."
                )
            tous_codes.append(mesure.code)

    doublons = {c for c in tous_codes if tous_codes.count(c) > 1}
    if doublons:
        raise ReferentialImportError(
            f"Codes de mesure en double dans le référentiel : {', '.join(sorted(doublons))}."
        )
    return parsed


def read_file(path: Path, *, fmt: str | None = None, header: dict | None = None):
    """Lit et valide, sans rien écrire."""
    if not path.exists():
        raise ReferentialImportError(f"Fichier introuvable : {path}")

    fmt = fmt or ("csv" if path.suffix.lower() in (".csv", ".tsv") else "json")
    if fmt == "csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            lecteur = csv.DictReader(fh)
            manquantes = [
                c for c in ("domaine_code", "mesure_code") if c not in (lecteur.fieldnames or [])
            ]
            if manquantes:
                raise ReferentialImportError(
                    f"Colonnes manquantes dans le tableur : {', '.join(manquantes)}. "
                    f"Colonnes attendues : {', '.join(CSV_COLUMNS)}."
                )
            return parse_csv(list(lecteur), header=header or {})

    with path.open(encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ReferentialImportError(f"JSON illisible : {exc}") from exc
    return parse_json(data)


@dataclass
class ImportReport:
    referential: Referential
    domains: int
    measures: int
    created: int
    updated: int
    # Mesures présentes en base mais absentes du fichier. Jamais supprimées
    # ici : une réponse de client peut les référencer, et une mise à jour de
    # référentiel n'a pas à effacer un diagnostic.
    orphans: list[str] = field(default_factory=list)


@transaction.atomic
def import_referential(parsed: ParsedReferential, *, activate: bool = True) -> ImportReport:
    """Écrit le référentiel analysé. Idempotent : un second import du même
    fichier ne crée rien et ne casse aucune réponse déjà enregistrée."""
    referential, _ = Referential.objects.update_or_create(
        slug=parsed.slug,
        defaults={
            "name": parsed.name,
            "version": parsed.version,
            "description": parsed.description,
            "publisher": parsed.publisher,
            "kind": parsed.kind,
            "source_url": parsed.source_url,
            "licence_notice": parsed.licence_notice,
            "is_active": activate,
        },
    )

    connus_avant = set(
        Measure.objects.filter(referential=referential).values_list("code", flat=True)
    )
    crees = 0
    mises_a_jour = 0
    vues: set[str] = set()

    for domaine in parsed.domains:
        domain, _ = Domain.objects.update_or_create(
            referential=referential,
            code=domaine.code,
            defaults={
                "name": domaine.name,
                "description": domaine.description,
                "order": domaine.order,
            },
        )
        for position, mesure in enumerate(domaine.measures, start=1):
            _, cree = Measure.objects.update_or_create(
                referential=referential,
                code=mesure.code,
                defaults={
                    "domain": domain,
                    "order": position,
                    "number": mesure.number,
                    "official_title": mesure.official_title,
                    "plain_language": mesure.plain_language,
                    "level": mesure.level,
                    "weight": mesure.weight,
                    "effort": mesure.effort,
                    "impact": mesure.impact,
                    "effort_impact_disclaimer": mesure.effort_impact_disclaimer,
                },
            )
            crees += 1 if cree else 0
            mises_a_jour += 0 if cree else 1
            vues.add(mesure.code)

    return ImportReport(
        referential=referential,
        domains=len(parsed.domains),
        measures=parsed.measure_count,
        created=crees,
        updated=mises_a_jour,
        orphans=sorted(connus_avant - vues),
    )
