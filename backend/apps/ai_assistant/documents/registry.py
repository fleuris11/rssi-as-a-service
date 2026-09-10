"""Le catalogue documentaire : ce que la plateforme sait produire, et à
quelles conditions ce sera utile.

Déclaré en code, comme ``billing/features.py`` et
``access_requests/subjects.py``, et pour la même raison : seul le code sait ce
qui existe réellement. Une entrée en base qui ne correspondrait à aucun
composeur ne produirait rien.

``readiness`` est la partie qui compte pour la consigne de vérification
(« un document qu'il faut réécrire entièrement ne sert à rien ») : elle dit,
AVANT la génération, ce que la plateforme ne pourra pas remplir. Un plan de
continuité produit sans aucun actif déclaré n'est pas faux, il est vide — et
le client doit l'apprendre du bouton, pas du document.
"""

from collections.abc import Callable
from dataclasses import dataclass

from ..models import GeneratedDocument
from . import composers

#: Un document COMPOSÉ est assemblé par du code, à partir des données de la
#: plateforme : deux générations le même jour donnent le même texte. Un
#: document RÉDIGÉ passe par l'API Claude et son pipeline de pseudonymisation.
SOURCE_COMPOSED = "composed"
SOURCE_AI = "ai"


@dataclass(frozen=True)
class DocumentSpec:
    type: str
    label: str
    #: Ce que le document sert à faire, écrit pour le client — pas une
    #: définition, une raison de cliquer.
    purpose: str
    source: str
    #: ``None`` pour les documents rédigés par l'IA : leur génération suit le
    #: chemin asynchrone existant (job Celery), pas un appel de fonction.
    build: Callable | None = None
    #: Ce que la plateforme doit connaître pour que le document soit
    #: réellement personnalisé.
    needs_assessment: bool = False
    needs_assets: bool = False


REGISTRY: dict[str, DocumentSpec] = {
    spec.type: spec
    for spec in [
        DocumentSpec(
            type=GeneratedDocument.DocumentType.SECURITY_POLICY,
            label="Politique de sécurité du système d'information",
            purpose=(
                "Le document de référence : ce que l'entreprise s'engage à faire, domaine "
                "par domaine, avec l'état constaté et ce qu'il reste à mettre en place."
            ),
            source=SOURCE_COMPOSED,
            build=composers.politique_de_securite,
            needs_assessment=True,
            needs_assets=True,
        ),
        DocumentSpec(
            type=GeneratedDocument.DocumentType.IT_CHARTER,
            label="Charte informatique",
            purpose=(
                "Les règles d'usage opposables aux utilisateurs : matériel, mots de passe, "
                "messagerie, télétravail. À annexer au règlement intérieur."
            ),
            source=SOURCE_AI,
            needs_assessment=True,
        ),
        DocumentSpec(
            type=GeneratedDocument.DocumentType.INCIDENT_PROCEDURE,
            label="Procédure de gestion des incidents",
            purpose=(
                "Qui prévenir, dans quel ordre, et quoi faire dans la première heure. "
                "Contient une fiche réflexe à imprimer."
            ),
            source=SOURCE_COMPOSED,
            build=composers.procedure_incidents,
        ),
        DocumentSpec(
            type=GeneratedDocument.DocumentType.INCIDENT_REGISTER,
            label="Registre des incidents",
            purpose=(
                "La trace exigée par l'article 33.5 du RGPD, pré-remplie avec les alertes "
                "et les fuites que la plateforme a détectées."
            ),
            source=SOURCE_COMPOSED,
            build=composers.registre_incidents,
        ),
        DocumentSpec(
            type=GeneratedDocument.DocumentType.CONTINUITY_PLAN,
            label="Plan de continuité simplifié",
            purpose=(
                "Comment continuer à travailler si l'informatique s'arrête : scénarios, "
                "sauvegardes, délais visés, contacts d'urgence."
            ),
            source=SOURCE_COMPOSED,
            build=composers.plan_de_continuite,
            needs_assets=True,
        ),
        DocumentSpec(
            type=GeneratedDocument.DocumentType.AWARENESS_SHEET,
            label="Fiche de sensibilisation",
            purpose=(
                "Une page à diffuser aux collaborateurs, avec les points d'attention "
                "réellement observés dans l'entreprise."
            ),
            source=SOURCE_COMPOSED,
            build=composers.fiche_sensibilisation,
            needs_assessment=True,
        ),
        DocumentSpec(
            type=GeneratedDocument.DocumentType.COMMITTEE_REPORT,
            label="Rapport de comité de sécurité",
            purpose=(
                "Les indicateurs du trimestre, les faits marquants et ce qui reste à "
                "arbitrer — archivé et versionné."
            ),
            source=SOURCE_COMPOSED,
            build=composers.rapport_comite,
        ),
    ]
}


def get(document_type: str) -> DocumentSpec | None:
    return REGISTRY.get(document_type)


def all_specs() -> list[DocumentSpec]:
    return list(REGISTRY.values())


def is_composed(document_type: str) -> bool:
    spec = REGISTRY.get(document_type)
    return spec is not None and spec.source == SOURCE_COMPOSED


def readiness(tenant, spec: DocumentSpec) -> dict:
    """Ce qui manque pour que CE document soit personnalisé, pour CE client.

    Ne bloque rien : un document générique reste un point de départ utile, et
    refuser de le produire enverrait le client le chercher ailleurs. On le
    prévient, c'est tout — et le document lui-même porte le même avertissement
    en tête, pour celui qui le recevra sans avoir vu l'écran.
    """
    from apps.assessments import services as assessments_services
    from apps.monitoring import services as monitoring_services

    manques = []
    if spec.needs_assessment:
        if assessments_services.get_latest_completed_assessment(tenant) is None:
            manques.append(
                "aucun diagnostic terminé : les sections qui décrivent votre situation "
                "resteront génériques"
            )
    if spec.needs_assets and not monitoring_services.list_assets(tenant).exists():
        manques.append("aucun actif déclaré : l'inventaire du document restera à remplir à la main")
    return {"ready": not manques, "missing": manques}
