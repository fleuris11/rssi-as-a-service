"""Couche de vulgarisation déterministe (Phase 8B, étendue V2-2).

Pour chaque type de fuite, **trois** phrases et non deux :

    meaning : ce que c'est ;
    impact  : ce que ça implique concrètement pour l'entreprise ;
    action  : ce qu'il faut faire.

La troisième a été ajoutée en V2-2 parce que les deux premières se
tuilaient : « ce que ça veut dire » finissait toujours par déborder sur les
conséquences, et l'action arrivait sans que le dirigeant ait mesuré ce qu'il
risquait. Séparer les trois oblige à écrire chacune, et un test échoue si
l'une manque — un endpoint ajouté sans impact ne peut pas passer.

Aucun appel IA : ces phrases s'affichent immédiatement, sans latence, sans
quota, sans dépendre de la disponibilité d'un fournisseur — la synthèse IA
est une couche *au-dessus*, jamais un prérequis pour comprendre une fuite.

Volontairement un module Python et non des templates ni des lignes en base :
- ce sont des constantes produit, pas des données de tenant (rien à
  personnaliser, rien à migrer) ;
- elles doivent être relues, corrigées et versionnées comme du texte
  éditorial — un diff Git est le bon outil pour ça ;
- les tests peuvent assertir dessus directement.

Règles de ton (appliquées à chaque entrée, vérifiées par les tests) :
vouvoiement, factuel, jamais anxiogène, aucun terme technique laissé sans
explication (« cookie de session » est explicité, pas supposé connu), et
**jamais le nom de la source de renseignement** — c'est un actif commercial
(ADR-027).
"""

from .models import BreachFinding

# Sous-type ASM correspondant au typosquatting/phishing (cf. normalizer).
ASM_PHISHING_TYPE = "pphish"

# Clé de repli quand un endpoint futur n'a pas encore d'entrée dédiée :
# mieux vaut une phrase générique correcte qu'une clé manquante à l'écran.
FALLBACK_KEY = "_default"

# Les trois clés que TOUTE entrée doit porter. Le test de couverture
# éditoriale s'appuie dessus.
REQUIRED_KEYS = ("meaning", "impact", "action")


_EXPLANATIONS: dict[str, dict[str, str]] = {
    BreachFinding.SourceEndpoint.STEALER: {
        "meaning": (
            "L'ordinateur de cette personne a été infecté par un logiciel qui recopie les mots "
            "de passe enregistrés dans le navigateur. Les identifiants récupérés circulent "
            "ensuite entre attaquants."
        ),
        "impact": (
            "Tout ce que ce poste avait mémorisé est à considérer comme connu : messagerie, "
            "outils métier, banque en ligne. Et tant que la machine n'est pas nettoyée, un "
            "nouveau mot de passe saisi dessus repartira de la même façon."
        ),
        "action": (
            "Changez ce mot de passe partout où il est réutilisé, et faites vérifier "
            "l'ordinateur concerné avant de le réutiliser pour des accès sensibles."
        ),
    },
    BreachFinding.SourceEndpoint.SESSIONS: {
        "meaning": (
            "Un « cookie de session » a été volé : c'est le jeton que votre navigateur garde "
            "après une connexion réussie, pour ne pas redemander le mot de passe à chaque page."
        ),
        "impact": (
            "Avec ce jeton, un attaquant entre dans le compte sans avoir besoin du mot de passe "
            "ni du code de double authentification. Changer le mot de passe ne suffit donc "
            "pas : le jeton reste valable tant que la session n'est pas fermée."
        ),
        "action": (
            "Déconnectez toutes les sessions actives de ce compte (option « se déconnecter "
            "partout » dans les paramètres du service), puis changez le mot de passe."
        ),
    },
    BreachFinding.SourceEndpoint.NHI: {
        "meaning": (
            "Une clé technique a été exposée. Ce n'est pas le compte d'une personne mais celui "
            "d'un programme : un logiciel qui se connecte à un service pour votre compte."
        ),
        "impact": (
            "Elle donne un accès permanent, le plus souvent sans double authentification, et "
            "son usage ne se remarque pas puisqu'aucun humain ne s'en sert au quotidien. Une "
            "clé exposée reste utilisable tant qu'elle n'est pas révoquée — changer les mots "
            "de passe des personnes n'y change rien."
        ),
        "action": (
            "Faites révoquer cette clé et en générer une nouvelle par votre prestataire "
            "informatique. Une clé exposée reste utilisable tant qu'elle n'est pas révoquée."
        ),
    },
    BreachFinding.SourceEndpoint.CREDS: {
        "meaning": (
            "Un identifiant lié à votre entreprise s'est retrouvé dans une fuite de données "
            "d'un site tiers."
        ),
        "impact": (
            "Le risque principal est la réutilisation : si le même mot de passe sert ailleurs, "
            "ces autres comptes sont exposés aussi. Les attaquants essaient automatiquement "
            "les couples récupérés sur les services les plus courants."
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
        "impact": (
            "Ces listes sont rejouées en continu et sur des milliers de services à la fois. Ce "
            "n'est pas une hypothèse : le couple est déjà entre les mains de plusieurs "
            "personnes, et il sera essayé."
        ),
        "action": (
            "Changez ce mot de passe dès que possible et activez la double authentification "
            "sur le compte concerné."
        ),
    },
    BreachFinding.SourceEndpoint.DOCS: {
        "meaning": (
            "Un document lié à votre entreprise a été publié sur un espace de fuite. Les "
            "informations ci-dessous le décrivent ; le document lui-même n'est pas accessible "
            "depuis cet espace, et c'est volontaire."
        ),
        "impact": (
            "Selon son contenu, il peut concerner vos clients autant que vous. Si des données "
            "personnelles s'y trouvent, l'obligation de notification vous incombe, et le délai "
            "court à partir du moment où vous en avez connaissance — c'est-à-dire maintenant."
        ),
        "action": (
            "Identifiez ce document à partir de son nom et de son type, et déterminez ce qu'il "
            "contient à partir de votre propre copie. S'il contient des données personnelles "
            "de clients, une notification à la CNIL peut être obligatoire sous 72 heures. Ne "
            "cherchez pas à télécharger la version publiée."
        ),
    },
    BreachFinding.SourceEndpoint.DARKWEB: {
        "meaning": (
            "Le nom de votre entreprise a été repéré dans un espace fréquenté par des "
            "attaquants. Rien n'indique qu'une donnée ait fuité : c'est un signal d'intérêt "
            "porté à votre entreprise."
        ),
        "impact": (
            "Une mention précède souvent une tentative, sans la garantir. Elle vaut surtout "
            "comme fenêtre de préparation : c'est le moment de vérifier ce qui vous ferait le "
            "plus mal si une attaque aboutissait."
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
        "impact": (
            "Prise isolément, elle ne change rien à votre exposition. Elle ne devient un signal "
            "que si d'autres éléments s'accumulent sur le même sujet."
        ),
        "action": (
            "Aucune action urgente. Gardez ce signal en tête si d'autres éléments "
            "s'accumulent sur le même sujet."
        ),
    },
    BreachFinding.SourceEndpoint.ASM: {
        "meaning": (
            "Un élément de votre présence sur internet a été inventorié : une adresse, un "
            "service accessible publiquement."
        ),
        "impact": (
            "C'est ce qu'un attaquant regarde en premier pour préparer une tentative. En "
            "soi, l'inventaire n'est pas une faiblesse — il le devient si l'un de ces "
            "services n'est plus tenu à jour."
        ),
        "action": (
            "Aucune action urgente. Assurez-vous simplement que les services exposés sont "
            "tenus à jour par votre prestataire."
        ),
    },
    BreachFinding.SourceEndpoint.WEBHOOK: {
        "meaning": ("Une compromission a été signalée en temps réel par la surveillance continue."),
        "impact": (
            "Le signalement est arrivé sans attendre l'analyse suivante : la donnée vient "
            "d'apparaître en circulation, elle est donc récente et exploitable en l'état."
        ),
        "action": (
            "Ouvrez le détail pour identifier le compte concerné, puis changez son mot de passe."
        ),
    },
    FALLBACK_KEY: {
        "meaning": (
            "Un élément lié à votre entreprise a été détecté par la surveillance des fuites "
            "de données."
        ),
        "impact": (
            "Le type exact n'a pas encore de description dédiée. Traitez-le comme une donnée "
            "de votre entreprise qui circule sans votre accord."
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
            "classique d'un faux email."
        ),
        "impact": (
            "Vos clients ou vos équipes recevront un message qui semble venir de vous, avec "
            "une adresse presque identique. La cible habituelle est la comptabilité, et la "
            "demande habituelle un changement de coordonnées bancaires."
        ),
        "action": (
            "Prévenez vos équipes, en particulier la comptabilité, de vérifier l'adresse "
            "exacte de l'expéditeur avant tout virement ou envoi d'information."
        ),
    },
}


def explain(finding: BreachFinding) -> dict[str, str]:
    """« Ce que c'est » + « ce que ça implique » + « ce qu'il faut faire » —
    déterministe, immédiat, sans appel IA."""
    subtype_key = (finding.source_endpoint, finding.finding_type)
    if subtype_key in _SUBTYPE_EXPLANATIONS:
        return dict(_SUBTYPE_EXPLANATIONS[subtype_key])
    return dict(_EXPLANATIONS.get(finding.source_endpoint, _EXPLANATIONS[FALLBACK_KEY]))


def all_explanations() -> dict[str, dict[str, str]]:
    """Exposé pour les tests de couverture éditoriale (chaque endpoint a bien
    son entrée) — pas utilisé par le code applicatif."""
    return dict(_EXPLANATIONS)


def all_subtype_explanations() -> dict[tuple[str, str], dict[str, str]]:
    """Idem, pour les sous-types : ils doivent tenir la même exigence."""
    return dict(_SUBTYPE_EXPLANATIONS)
