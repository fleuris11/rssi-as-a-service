"""Ce que veut dire une alerte de surveillance, et ce qu'il faut faire.

Pendant écrit du module homonyme d'``apps.threat_intelligence`` (Phase 8B),
qui rendait déjà ce service pour les fuites. Les alertes de surveillance, elles,
n'avaient aucune vulgarisation : l'email d'alerte se contentait d'un tableau
« Actif / Type / Sévérité », c'est-à-dire d'un constat sans explication ni
action. Un dirigeant y lisait « Certificat SSL bientôt expiré » et devait
deviner seul si c'était grave, ce que ça impliquait, et qui devait faire quoi.

Mêmes règles de ton que côté fuites : vouvoiement, factuel, jamais anxiogène,
aucun terme technique laissé sans explication. Un dirigeant de TPE/PME doit
pouvoir transmettre l'action telle quelle à son prestataire informatique.

Volontairement un module Python, pas des templates : ce sont des constantes
produit, relues et versionnées comme du texte éditorial — un diff Git est le
bon outil pour ça, et les tests peuvent assertir dessus.
"""

from .models import Alert

FALLBACK_KEY = "_default"

_EXPLANATIONS: dict[str, dict[str, str]] = {
    Alert.AlertType.DOWN: {
        "meaning": (
            "Votre site ne répond plus. Nous l'avons vérifié trois fois de suite avant de "
            "vous prévenir, il ne s'agit donc pas d'un ralentissement passager. Vos visiteurs "
            "et vos clients voient probablement une page d'erreur."
        ),
        "action": (
            "Prévenez votre prestataire informatique ou votre hébergeur en leur indiquant "
            "l'heure de début de la panne. Si vous avez une boutique en ligne ou un "
            "formulaire de contact, considérez qu'ils sont inutilisables pendant ce temps."
        ),
    },
    Alert.AlertType.SSL_EXPIRING: {
        "meaning": (
            "Le certificat qui sécurise votre site arrive à expiration. C'est lui qui affiche "
            "le cadenas dans le navigateur. Une fois expiré, les visiteurs verront un "
            "avertissement de sécurité bien visible, et beaucoup rebrousseront chemin."
        ),
        "action": (
            "Demandez à votre prestataire de renouveler le certificat avant la date "
            "d'expiration. Le renouvellement est le plus souvent automatisable, et gratuit."
        ),
    },
    Alert.AlertType.SECURITY_HEADERS: {
        "meaning": (
            "Votre site n'envoie pas certaines consignes de sécurité que les navigateurs "
            "savent appliquer. Ce ne sont pas des failles ouvertes, mais des protections "
            "gratuites que vous n'utilisez pas — elles limitent l'impact d'une attaque si "
            "elle survient."
        ),
        "action": (
            "Transmettez ce constat à votre prestataire : la correction se fait dans la "
            "configuration du serveur web, sans toucher au site lui-même."
        ),
    },
    Alert.AlertType.EMAIL_MISCONFIGURED: {
        "meaning": (
            "La configuration qui prouve l'authenticité de vos emails est incomplète. "
            "Concrètement, il est plus facile pour un escroc d'envoyer un message qui semble "
            "venir de votre entreprise — c'est le montage classique de la fausse facture ou "
            "de la demande de virement urgente."
        ),
        "action": (
            "Faites compléter les enregistrements SPF et DMARC de votre nom de domaine par "
            "la personne qui gère votre messagerie. C'est une modification de configuration, "
            "sans interruption de service."
        ),
    },
    Alert.AlertType.BREACH_COMPROMISE: {
        "meaning": (
            "Des identifiants liés à cet actif ont été retrouvés dans une fuite de données. "
            "Le détail de chaque élément trouvé est dans votre espace."
        ),
        "action": (
            "Ouvrez la page « Compromissions » : chaque élément y est expliqué, avec "
            "l'action correspondante."
        ),
    },
    FALLBACK_KEY: {
        "meaning": ("Un contrôle de surveillance a signalé une anomalie sur cet actif."),
        "action": (
            "Ouvrez votre espace pour en voir le détail, ou répondez à cet email si "
            "quelque chose n'est pas clair."
        ),
    },
}


def explain(alert_type: str) -> dict[str, str]:
    """« Ce que ça veut dire » + « ce qu'il faut faire » pour un type d'alerte.

    Un type inconnu retombe sur une phrase générique correcte plutôt que sur
    une clé manquante : un email d'alerte à trous serait pire qu'un email
    générique.
    """
    return dict(_EXPLANATIONS.get(alert_type, _EXPLANATIONS[FALLBACK_KEY]))


def all_explanations() -> dict[str, dict[str, str]]:
    """Exposé pour le test de couverture éditoriale (chaque type d'alerte a
    bien son entrée) — pas utilisé par le code applicatif."""
    return dict(_EXPLANATIONS)
