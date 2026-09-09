"""Textes destinés au client pour la vérification de possession (V2-1).

Regroupés ici, comme ``threat_intelligence.client_messages``, pour la même
raison : un refus ou une consigne que le client lit doit pouvoir être relu et
corrigé sans traverser la logique métier. Et parce que ces phrases-ci sont
lues par quelqu'un qui est en train d'échouer à faire quelque chose — c'est
le pire moment pour tomber sur une formule technique.

Aucun de ces textes ne nomme le fournisseur, la licence ou un détail de notre
infrastructure : ce que le client doit savoir, c'est ce qu'il a à faire.
"""

# --- Déclaration sur l'honneur ---------------------------------------------

# Recopiée telle quelle dans chaque trace (``AssetOwnershipAttestation``) :
# une déclaration doit pouvoir être relue dans les termes où elle a été
# présentée, même après que le formulaire a changé de formulation.
ATTESTATION_STATEMENT = (
    "Je déclare être habilité par l'organisation propriétaire de cet actif à en "
    "demander l'analyse, et j'accepte que cette déclaration soit conservée avec "
    "mon nom, la date et l'actif concerné."
)

# --- Refus ------------------------------------------------------------------

OWNERSHIP_REQUIRED = (
    "La surveillance continue de ce domaine demande d'abord d'en prouver la "
    "possession. Trois méthodes sont proposées : un enregistrement DNS, un "
    "fichier déposé à la racine du site, ou un email envoyé à une adresse "
    "d'administration du domaine. Une analyse ponctuelle reste possible sans "
    "cette preuve."
)

EMAIL_SEND_FAILED = (
    "L'email de vérification n'a pas pu être envoyé. Réessayez, ou choisissez une autre méthode."
)

EMAIL_CODE_MISMATCH = "Le code saisi ne correspond pas à celui envoyé par email."


def email_choices_message(domaine: str) -> str:
    from .services import OWNERSHIP_EMAIL_LOCAL_PARTS

    adresses = ", ".join(f"{partie}@{domaine}" for partie in OWNERSHIP_EMAIL_LOCAL_PARTS)
    return (
        "Choisissez l'une des adresses d'administration du domaine : "
        f"{adresses}. Ces adresses ne sont pas modifiables — c'est ce qui fait "
        "la valeur de la preuve."
    )


# --- Consignes --------------------------------------------------------------

DNS_TXT_HOW_TO = (
    "Ajoutez cet enregistrement TXT à la zone DNS de {domaine}, chez votre "
    "registrar ou votre hébergeur, puis revenez lancer la vérification. La "
    "publication peut prendre de quelques minutes à quelques heures. "
    "L'enregistrement peut être supprimé une fois la vérification faite."
)

HTTP_FILE_HOW_TO = (
    "Déposez un fichier texte à l'adresse https://{domaine}{chemin}, ne "
    "contenant que le jeton ci-dessus, puis revenez lancer la vérification. "
    "Le fichier peut être supprimé une fois la vérification faite."
)

EMAIL_HOW_TO = (
    "Un code a été envoyé à {adresse}. Saisissez-le ci-dessous pour terminer "
    "la vérification. Si personne ne relève cette boîte, choisissez une autre "
    "méthode."
)


# --- Email de vérification --------------------------------------------------


def email_subject(domaine: str) -> str:
    return f"Vérification de possession du domaine {domaine}"


def email_body(*, domaine: str, entreprise: str, jeton: str) -> str:
    """Message envoyé à une adresse d'administration du domaine.

    Écrit pour quelqu'un qui ne nous connaît pas et n'a rien demandé : il dit
    d'emblée qui demande quoi, et quoi faire si la demande est illégitime.
    C'est le sens même de la méthode — sans cette porte de sortie, l'email ne
    serait qu'une formalité de plus.
    """
    return (
        f"Bonjour,\n\n"
        f"L'entreprise « {entreprise} » demande à faire surveiller le domaine "
        f"{domaine} sur la plateforme RSSI as a Service (surveillance de "
        f"compromissions et de fuites de données).\n\n"
        f"Cette surveillance ne sera activée que si le code ci-dessous est "
        f"saisi sur la plateforme par le demandeur :\n\n"
        f"    {jeton}\n\n"
        f"Si cette demande est légitime, transmettez ce code à votre "
        f"interlocuteur.\n\n"
        f"Si vous ne connaissez pas cette entreprise ou si vous ne souhaitez "
        f"pas que ce domaine soit surveillé, ne transmettez pas ce code : sans "
        f"lui, rien ne sera activé. Vous pouvez également nous écrire pour "
        f"signaler la demande.\n\n"
        f"— RSSI as a Service\n"
        f"https://rssiasservice.online\n"
    )
