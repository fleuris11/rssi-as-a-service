"""« Les 10 mesures essentielles » : la composition de départ, posée partout.

**Pourquoi ce module, en plus de la migration 0005.** Les conteneurs
``migrate`` lancent ``migrate`` PUIS ``load_anssi_referential``. Sur une base
neuve — intégration continue, nouvel environnement, ``docker compose up`` d'un
poste de développement — la migration s'exécute avant que le référentiel ANSSI
existe, et ne pose rien. La composition n'existait donc qu'en production, où
l'ANSSI était déjà chargée : toute installation neuve en était privée, et
aucun test ne le voyait.

Le chargeur appelle désormais :func:`ensure_essential_subset` après chaque
import de l'ANSSI. La migration garde sa propre copie FIGÉE des codes (leçon
D5 de la V2-7 : une migration ne lit pas le code vivant) ; un test vérifie que
les deux listes n'ont pas divergé.

Deux règles, les mêmes que la migration :

- une composition déjà posée, et peut-être ajustée depuis la console, n'est
  jamais réécrite ;
- une composition portant cet identifiant mais appartenant à un client n'est
  jamais reprise par la plateforme (ADR-035).
"""

from .models import Measure, MeasureSubset, SubsetMeasure

REFERENTIEL = "anssi-hygiene-informatique"
SLUG = "anssi-10-essentielles"
NOM = "Les 10 mesures essentielles"
DESCRIPTION = (
    "Par où commencer. Dix mesures à fort impact, réalisables sans équipe dédiée. "
    "Vous pourrez passer au questionnaire complet ensuite : vos réponses sont conservées."
)

#: Le texte posé par la migration 0005, SANS accents. Il est affiché au
#: client : on le remplace par la version correcte, mais seulement s'il est
#: resté tel quel — une description retouchée depuis la console est conservée.
DESCRIPTION_SANS_ACCENTS = (
    "Par ou commencer. Dix mesures a fort impact, realisables sans "
    "equipe dediee. Vous pourrez passer au questionnaire complet "
    "ensuite : vos reponses sont conservees."
)

#: Mêmes codes que ``CODES_ESSENTIELS`` dans la migration 0005 — voir la
#: docstring de la migration pour le raisonnement du choix.
CODES = ["2", "5", "6", "10", "12", "14", "24", "34", "37", "40"]


def ensure_essential_subset(referential) -> MeasureSubset | None:
    """Pose la composition si elle manque. Ne réécrit jamais l'existant.

    Renvoie la composition, ou ``None`` quand elle ne peut pas être posée
    honnêtement : autre référentiel, codes absents (on ne livre pas une
    sélection amputée sous le nom « les dix essentielles »), ou identifiant
    déjà pris par un client.
    """
    if referential.slug != REFERENTIEL:
        return None

    mesures = {mesure.code: mesure for mesure in Measure.objects.filter(referential=referential)}
    if any(code not in mesures for code in CODES):
        return None

    composition, creee = MeasureSubset.objects.get_or_create(
        referential=referential,
        slug=SLUG,
        defaults={
            "name": NOM,
            "description": DESCRIPTION,
            "owner_tenant": None,
            "is_active": True,
        },
    )
    if composition.owner_tenant_id is not None:
        return None

    if composition.description == DESCRIPTION_SANS_ACCENTS:
        composition.description = DESCRIPTION
        composition.save(update_fields=["description"])

    if not creee and SubsetMeasure.objects.filter(subset=composition).exists():
        return composition

    SubsetMeasure.objects.bulk_create(
        [
            SubsetMeasure(subset=composition, measure=mesures[code], order=position)
            for position, code in enumerate(CODES, start=1)
        ]
    )
    return composition
