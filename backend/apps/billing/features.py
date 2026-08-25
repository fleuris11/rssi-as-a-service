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
EXTENDED_HISTORY = "extended_history"
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
        # ---------------------------------------------------------------
        # ATTENTION — clé sans référent, décision en attente (phase 12).
        #
        # Une garde se pose sur une notion vérifiable : « au-delà de la
        # période standard » suppose qu'une période standard existe. Elle
        # n'existe pas. Recherche faite dans tout le dépôt, il n'y a :
        #
        #   - aucune rétention par client. Les trois réglages de rétention
        #     (secrets, audit de révélation, corbeille) sont des réglages
        #     PLATEFORME, identiques pour tous, réglés en console par
        #     l'exploitant — jamais un argument commercial ;
        #   - aucune purge de l'historique métier. La purge de phase 8C
        #     efface le SECRET d'une fuite, jamais la fuite : les
        #     constats, leur statut et leurs dates restent indéfiniment ;
        #   - aucune fenêtre d'historique paramétrable. La seule fenêtre du
        #     produit est le taux de disponibilité sur 24 h, en dur dans
        #     ``monitoring.services.compute_uptime_percentage``, la même
        #     pour toutes les offres ;
        #   - aucun rollup de série temporelle. C'est une cible Green IT,
        #     pas une fonctionnalité livrée.
        #
        # Autrement dit, tout le monde a déjà l'historique complet, pour
        # toujours. « Étendu » ne se distingue de rien.
        #
        # Ce n'est donc PAS le cas de figure redouté (une notion qui croise
        # un quota et qu'on n'arrive pas à en séparer) : ``monthly_scans``
        # compte des analyses consommées dans le mois, il ne coupe aucun
        # historique. C'est un cas plus embarrassant — une promesse vendue
        # publiquement sur la grille tarifaire, sans rien derrière.
        #
        # Et la définir maintenant se heurte à une règle qu'on ne veut pas
        # plier : une garde d'historique consisterait à MASQUER à un client
        # des données que son propre compte détient déjà. La règle posée
        # pour les six gardes — « on ne prend jamais en otage les données
        # existantes, la lecture reste ouverte » — l'interdit. Les deux ne
        # peuvent pas tenir ensemble.
        #
        # Recommandation : RETIRER cette clé du registre (elle disparaîtra
        # alors d'elle-même de « Souverain », ``sanitize`` ignorant les
        # clés inconnues) et la reprendre le jour où une rétention de base
        # existe — c'est-à-dire quand il y aura quelque chose à étendre.
        # Décision commerciale : laissée à l'exploitant, non appliquée ici.
        # ---------------------------------------------------------------
        Feature(
            EXTENDED_HISTORY,
            "Historique étendu",
            "Conservez et consultez l'historique complet de vos analyses au-delà de la période "
            "standard.",
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
