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
WATCHED_ACCOUNTS = "watched_accounts"
TRAINING = "training"
TRAINING_STUDIO = "training_studio"

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
            WATCHED_ACCOUNTS,
            "Surveillance de comptes désignés",
            "Faites surveiller des comptes précis — dirigeants, comptes sensibles — "
            "indépendamment de vos noms de domaine, et lancez l'analyse quand vous le décidez.",
        ),
        Feature(
            REALTIME_MONITORING,
            "Surveillance en temps réel",
            "Soyez alerté dès qu'une fuite est détectée, sans attendre l'analyse suivante.",
        ),
        Feature(
            TRAINING,
            "Formation des salariés",
            "Formez vos salariés en dix minutes par cours, sans leur créer de compte, "
            "et délivrez une attestation de suivi.",
        ),
        Feature(
            TRAINING_STUDIO,
            "Studio de formation",
            "Écrivez vos propres cours, ou partez d'un cours de la bibliothèque pour "
            "l'adapter à votre maison.",
        ),
    ]
}


# --- Ce qu'une fonctionnalité exige pour avoir un sens (V2-8, ADR-038) -------
#
# Composer le menu d'un client, c'est pouvoir produire des combinaisons qui
# n'ont aucun sens. Trois natures de contrainte, et une seule est vide — ce
# vide est un constat vérifié, pas un oubli.

#: Fonctionnalité -> fonctionnalités dont elle a besoin.
#:
#: **Vide aujourd'hui**, et c'est exact : les neuf clés portent des capacités
#: greffées sur des écrans qui, eux, ne sont jamais conditionnés (Exposition,
#: Compromissions, Documents, Veille). Révéler un mot de passe, corréler une
#: réutilisation ou résumer une exposition n'exige aucune autre clé. Déclarer
#: ici une dépendance inventée donnerait l'illusion d'un contrôle.
DEPEND_DE: dict[str, tuple[str, ...]] = {
    # F2 : la première dépendance réelle entre deux clés. Écrire des cours
    # sans pouvoir les faire suivre n'a aucun sens — le studio produit
    # quelque chose dont la formation est le seul débouché.
    TRAINING_STUDIO: (TRAINING,),
}

#: Fonctionnalité -> (quota de l'abonnement, ce que le quota compte).
#:
#: Activer la fonctionnalité sans le quota correspondant produit un écran dont
#: CHAQUE action est refusée — le client voit une promesse que le serveur lui
#: refuse ensuite. C'est la combinaison incohérente la plus facile à produire
#: depuis un écran de composition.
QUOTA_REQUIS: dict[str, tuple[str, str]] = {
    WATCHED_ACCOUNTS: ("watched_accounts_quota", "compte à surveiller"),
    REALTIME_MONITORING: ("monitored_assets_quota", "emplacement de surveillance continue"),
}

#: Fonctionnalité -> écrans qui n'existent QUE par elle.
#:
#: Retirer le diagnostic retire aussi ses résultats et le plan d'action : le
#: plan est *produit* par la clôture d'un diagnostic, et les résultats en sont
#: la lecture. Les laisser au menu afficherait deux écrans vides dont le
#: message invite à faire un diagnostic auquel le client n'a pas droit.
ECRANS_DERIVES: dict[str, tuple[str, ...]] = {
    ANSSI_ASSESSMENT: ("Résultats", "Plan d'action"),
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
