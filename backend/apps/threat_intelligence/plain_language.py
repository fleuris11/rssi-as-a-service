"""Couche de vulgarisation déterministe (Phase 8B).

Pour chaque type de fuite : ce que ça veut dire, en une ou deux phrases
qu'un dirigeant de TPE/PME comprend sans être technicien, et **l'action
concrète** à faire. Aucun appel IA : ces phrases s'affichent immédiatement,
sans latence, sans quota, sans dépendre de la disponibilité d'un
fournisseur — la synthèse IA (Tâche 4) est une couche *au-dessus*, jamais
un prérequis pour comprendre une fuite.

Volontairement un module Python et non des templates ni des lignes en base :
- ce sont des constantes produit, pas des données de tenant (rien à
  personnaliser, rien à migrer) ;
- elles doivent être relues, corrigées et versionnées comme du texte
  éditorial — un diff Git est le bon outil pour ça ;
- les tests peuvent assertir dessus directement.

Règles de ton (appliquées à chaque entrée, vérifiées par les tests) :
vouvoiement, factuel, jamais anxiogène, aucun terme technique laissé sans
explication (« cookie de session » est explicité, pas supposé connu).
"""

from .models import BreachFinding

# Sous-type ASM correspondant au typosquatting/phishing (cf. normalizer).
ASM_PHISHING_TYPE = "pphish"

# Clé de repli quand un endpoint futur n'a pas encore d'entrée dédiée :
# mieux vaut une phrase générique correcte qu'une clé manquante à l'écran.
FALLBACK_KEY = "_default"


_EXPLANATIONS: dict[str, dict[str, str]] = {
    BreachFinding.SourceEndpoint.STEALER: {
        "meaning": (
            "L'ordinateur de cette personne a été infecté par un logiciel qui recopie les mots "
            "de passe enregistrés dans le navigateur. Les identifiants récupérés circulent "
            "ensuite entre attaquants."
        ),
        "action": (
            "Changez ce mot de passe partout où il est réutilisé, et faites vérifier "
            "l'ordinateur concerné avant de le réutiliser pour des accès sensibles."
        ),
    },
    BreachFinding.SourceEndpoint.SESSIONS: {
        "meaning": (
            "Un « cookie de session » a été volé : c'est le jeton que votre navigateur garde "
            "après une connexion réussie, pour ne pas redemander le mot de passe à chaque page. "
            "Avec ce jeton, un attaquant entre dans le compte sans avoir besoin du mot de passe "
            "ni du code de double authentification."
        ),
        "action": (
            "Déconnectez toutes les sessions actives de ce compte (option « se déconnecter "
            "partout » dans les paramètres du service), puis changez le mot de passe."
        ),
    },
    BreachFinding.SourceEndpoint.NHI: {
        "meaning": (
            "Une clé technique a été exposée. Ce n'est pas le compte d'une personne mais celui "
            "d'un programme : elle donne un accès permanent, souvent sans double "
            "authentification, et personne ne remarque son utilisation puisqu'aucun humain ne "
            "s'en sert au quotidien."
        ),
        "action": (
            "Faites révoquer cette clé et en générer une nouvelle par votre prestataire "
            "informatique. Une clé exposée reste utilisable tant qu'elle n'est pas révoquée."
        ),
    },
    BreachFinding.SourceEndpoint.CREDS: {
        "meaning": (
            "Un identifiant lié à votre entreprise s'est retrouvé dans une fuite de données "
            "d'un site tiers. Le risque principal est la réutilisation : si le même mot de "
            "passe sert ailleurs, ces autres comptes sont exposés aussi."
        ),
        "action": (
            "Changez ce mot de passe, et vérifiez qu'il n'est pas réutilisé sur vos outils "
            "professionnels (messagerie, banque, logiciel de comptabilité)."
        ),
    },
    BreachFinding.SourceEndpoint.COMBO: {
        "meaning": (
            "Cet identifiant circule dans une liste de couples « adresse + mot de passe » que "
            "les attaquants testent automatiquement sur de nombreux sites."
        ),
        "action": (
            "Changez ce mot de passe dès que possible et activez la double authentification "
            "sur le compte concerné."
        ),
    },
    BreachFinding.SourceEndpoint.DOCS: {
        "meaning": (
            "Un document lié à votre entreprise a été publié sur un espace de fuite. Selon son "
            "contenu, il peut concerner vos clients autant que vous."
        ),
        "action": (
            "Identifiez ce document et son contenu. S'il contient des données personnelles de "
            "clients, une notification à la CNIL peut être obligatoire sous 72 heures."
        ),
    },
    BreachFinding.SourceEndpoint.DARKWEB: {
        "meaning": (
            "Le nom de votre entreprise a été repéré dans un espace fréquenté par des "
            "attaquants. Rien n'indique qu'une donnée ait fuité : c'est un signal d'intérêt "
            "porté à votre entreprise."
        ),
        "action": (
            "Profitez-en pour vérifier deux points : vos sauvegardes fonctionnent, et la "
            "double authentification est active sur vos comptes importants."
        ),
    },
    BreachFinding.SourceEndpoint.RADAR: {
        "meaning": (
            "Une mention publique liée à votre entreprise a été repérée par la veille. C'est "
            "une information de suivi, pas une fuite."
        ),
        "action": (
            "Aucune action urgente. Gardez ce signal en tête si d'autres éléments "
            "s'accumulent sur le même sujet."
        ),
    },
    BreachFinding.SourceEndpoint.ASM: {
        "meaning": (
            "Un élément de votre présence sur internet a été inventorié. C'est ce qu'un "
            "attaquant regarde en premier pour préparer une tentative."
        ),
        "action": (
            "Aucune action urgente. Assurez-vous simplement que les services exposés sont "
            "tenus à jour par votre prestataire."
        ),
    },
    BreachFinding.SourceEndpoint.WEBHOOK: {
        "meaning": (
            "Une compromission a été signalée en temps réel par la surveillance continue."
        ),
        "action": (
            "Ouvrez le détail pour identifier le compte concerné, puis changez son mot de "
            "passe."
        ),
    },
    FALLBACK_KEY: {
        "meaning": (
            "Un élément lié à votre entreprise a été détecté par la surveillance des fuites "
            "de données."
        ),
        "action": (
            "Ouvrez le détail pour identifier le compte concerné et changez son mot de passe "
            "par précaution."
        ),
    },
}

# Sous-type : le phishing/typosquatting d'ASM n'est pas de l'inventaire, il
# appelle une action immédiate et une explication différente.
_SUBTYPE_EXPLANATIONS: dict[tuple[str, str], dict[str, str]] = {
    (BreachFinding.SourceEndpoint.ASM, ASM_PHISHING_TYPE): {
        "meaning": (
            "Une adresse internet très proche de la vôtre a été déposée. C'est le préparatif "
            "classique d'un faux email : vos clients ou vos équipes reçoivent un message qui "
            "semble venir de vous, avec une adresse presque identique."
        ),
        "action": (
            "Prévenez vos équipes, en particulier la comptabilité, de vérifier l'adresse "
            "exacte de l'expéditeur avant tout virement ou envoi d'information."
        ),
    },
}


def explain(finding: BreachFinding) -> dict[str, str]:
    """« Ce que ça veut dire » + « ce qu'il faut faire » pour une fuite —
    déterministe, immédiat, sans appel IA."""
    subtype_key = (finding.source_endpoint, finding.finding_type)
    if subtype_key in _SUBTYPE_EXPLANATIONS:
        return dict(_SUBTYPE_EXPLANATIONS[subtype_key])
    return dict(_EXPLANATIONS.get(finding.source_endpoint, _EXPLANATIONS[FALLBACK_KEY]))


def all_explanations() -> dict[str, dict[str, str]]:
    """Exposé pour les tests de couverture éditoriale (chaque endpoint a bien
    son entrée) — pas utilisé par le code applicatif."""
    return dict(_EXPLANATIONS)
