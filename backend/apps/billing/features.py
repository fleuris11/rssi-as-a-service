"""Registre des fonctionnalités activables par offre.

Les fonctionnalités sont **déclarées en code** (ici) mais **activées en base**
(``Plan.features``). La raison de ce partage : le code seul sait quelles
fonctionnalités existent réellement — une clé inventée en base ne
correspondrait à aucune garde et ne ferait rien. À l'inverse, savoir *quelle
offre inclut quoi* est une décision commerciale qui doit changer sans
redéploiement.

Conséquence assumée, et testée : une clé présente en base mais absente de ce
registre est **ignorée**, jamais une erreur. Un plan mal saisi ne doit pas
faire tomber l'application pour tous les clients qui y sont abonnés.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    # Ce que le client voit quand la fonctionnalité ne fait pas partie de son
    # offre. Rédigé comme un argument, pas comme un refus : l'interface
    # affiche l'élément désactivé plutôt que de le masquer (le client doit
    # savoir que le produit sait le faire).
    teaser: str


ASSISTANT = "assistant"
EXPOSURE_SYNTHESIS = "exposure_synthesis"
PDF_EXPORT = "pdf_export"
REUSE_CORRELATION = "reuse_correlation"
SECRET_REVEAL = "secret_reveal"
ANSSI_ASSESSMENT = "anssi_assessment"
CHARTER_GENERATION = "charter_generation"
# « extended_history » a été retirée ici : clé sans référent — aucune
# rétention par client, aucune purge de l'historique métier, aucune fenêtre
# paramétrable. Elle reviendra le jour où une rétention différenciée par
# offre existera, c'est-à-dire quand il y aura quelque chose à étendre.
# Raisonnement complet : docs/adr/025-retrait-de-la-cle-historique-etendu.md
REALTIME_MONITORING = "realtime_monitoring"

REGISTRY: dict[str, Feature] = {
    f.key: f
    for f in [
        Feature(
            ASSISTANT,
            "Assistant conversationnel",
            "Posez vos questions de sécurité et obtenez une réponse adaptée à votre situation.",
        ),
        Feature(
            EXPOSURE_SYNTHESIS,
            "Synthèse d'exposition",
            "Une lecture d'ensemble de votre exposition, avec les corrélations et la priorité "
            "de la semaine.",
        ),
        Feature(
            PDF_EXPORT,
            "Export PDF des documents",
            "Exportez vos documents générés au format PDF, prêts à diffuser.",
        ),
        Feature(
            REUSE_CORRELATION,
            "Corrélation de réutilisation",
            "Repérez qu'un même identifiant revient dans plusieurs fuites, ou qu'une adresse "
            "professionnelle apparaît dans la fuite d'un service externe.",
        ),
        Feature(
            SECRET_REVEAL,
            "Révélation de mot de passe",
            "Consultez la valeur exacte d'un mot de passe fuité, après vérification d'identité "
            "et de façon tracée.",
        ),
        Feature(
            ANSSI_ASSESSMENT,
            "Diagnostic de maturité",
            "Évaluez votre maturité sur les 42 mesures du référentiel et obtenez un plan "
            "d'action priorisé.",
        ),
        Feature(
            CHARTER_GENERATION,
            "Génération de charte informatique",
            "Produisez une charte informatique adaptée à votre entreprise, à relire et valider.",
        ),
        Feature(
            REALTIME_MONITORING,
            "Surveillance en temps réel",
            "Soyez alerté dès qu'une fuite est détectée, sans attendre l'analyse suivante.",
        ),
    ]
}


def is_known(key: str) -> bool:
    return key in REGISTRY


def get(key: str) -> Feature | None:
    return REGISTRY.get(key)


def label(key: str) -> str:
    feature = REGISTRY.get(key)
    return feature.label if feature else key


def all_keys() -> list[str]:
    return list(REGISTRY)


def sanitize(keys) -> list[str]:
    """Ne garde que les clés réellement connues, en préservant l'ordre du
    registre. C'est le point unique qui protège l'application d'une saisie
    erronée en base."""
    provided = set(keys or [])
    return [key for key in REGISTRY if key in provided]
