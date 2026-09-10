"""Vérification de possession d'un domaine (V2-1, ADR-026).

Deux des trois méthodes se vérifient par le réseau et vivent ici, à côté des
autres contrôles passifs : publier un enregistrement DNS TXT, ou déposer un
fichier à la racine du site. La troisième — l'email de validation — ne
demande aucun accès réseau au domaine du client : elle se joue entre l'envoi
et la saisie d'un code, et vit donc dans ``services.py``.

Les deux vérifications ici sont **passives**, au sens de l'ADR-010 : une
requête DNS publique et un GET HTTP. Le GET passe par ``safe_get``, donc par
la validation SSRF de chaque saut de redirection — un domaine dont on ne sait
pas encore s'il appartient au client est précisément le genre de cible qu'il
ne faut pas suivre les yeux fermés vers une adresse interne.
"""

import dns.exception
import dns.resolver

from .http_client import CheckNetworkError, safe_get
from .ssrf import SSRFError

LOOKUP_TIMEOUT_SECONDS = 10

# Préfixe de l'enregistrement TXT. Nommé plutôt qu'un jeton nu : un
# administrateur système qui relit la zone DNS de son entreprise doit pouvoir
# comprendre à quoi sert cette ligne sans nous appeler, et pouvoir la
# supprimer en connaissance de cause.
DNS_TXT_PREFIX = "rssi-verification="

# Chemin fixe plutôt qu'un nom de fichier contenant le jeton : plus simple à
# dicter au téléphone, et il se supprime sans avoir à retrouver le jeton.
HTTP_FILE_PATH = "/.well-known/rssi-verification.txt"

# Le fichier ne doit contenir qu'un jeton. Un plafond évite de télécharger
# une page d'erreur de plusieurs mégaoctets servie à la place.
MAX_FILE_BYTES = 4096


class OwnershipCheckError(Exception):
    """La vérification n'a pas pu aboutir — distinct d'une vérification qui
    aboutit et conclut « la preuve n'est pas là »."""


def expected_dns_record(token: str) -> str:
    return f"{DNS_TXT_PREFIX}{token}"


def _txt_records(domain: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, "TXT", lifetime=LOOKUP_TIMEOUT_SECONDS)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except dns.exception.DNSException as exc:
        raise OwnershipCheckError(f"Requête DNS TXT impossible pour {domain!r} : {exc}") from exc

    records = []
    for answer in answers:
        # dnspython découpe les longues chaînes TXT en morceaux ; on les
        # recolle avant de comparer, sinon un jeton long ne correspondrait
        # jamais.
        records.append(b"".join(answer.strings).decode(errors="replace"))
    return records


def verify_dns_txt(domain: str, token: str) -> tuple[bool, str]:
    """Cherche ``rssi-verification=<jeton>`` parmi les TXT du domaine.

    Renvoie ``(trouvé, détail)``. Le détail est destiné au client : il doit
    lui dire quoi corriger, pas seulement que ça a échoué.
    """
    attendu = expected_dns_record(token)
    records = _txt_records(domain)
    if attendu in (r.strip() for r in records):
        return True, "Enregistrement TXT trouvé."

    nos_records = [r for r in records if r.startswith(DNS_TXT_PREFIX)]
    if nos_records:
        # Cas fréquent et déroutant : une vérification précédente a laissé son
        # enregistrement, le client croit avoir publié le bon.
        return False, (
            "Un enregistrement de vérification est présent, mais il ne porte pas "
            "le jeton attendu. Remplacez-le par celui indiqué ci-dessus — un "
            "jeton d'une tentative précédente ne vaut plus."
        )
    if not records:
        return False, (
            "Aucun enregistrement TXT n'a été trouvé sur ce domaine. La "
            "publication DNS peut demander quelques minutes à quelques heures "
            "avant d'être visible."
        )
    return False, (
        "Le domaine a des enregistrements TXT, mais aucun ne correspond. "
        "Vérifiez que la valeur a été copiée en entier."
    )


def verify_http_file(domain: str, token: str) -> tuple[bool, str]:
    """Cherche le jeton dans ``/.well-known/rssi-verification.txt``."""
    url = f"https://{domain}{HTTP_FILE_PATH}"
    try:
        response = safe_get(url)
    except SSRFError as exc:
        # Refus délibéré, pas une panne : le domaine résout vers une adresse
        # qu'on ne va pas interroger depuis ce serveur.
        raise OwnershipCheckError(f"Domaine non joignable en toute sécurité : {exc}") from exc
    except CheckNetworkError as exc:
        raise OwnershipCheckError(
            f"Le fichier n'a pas pu être récupéré sur {domain} : {exc}"
        ) from exc

    if response.status_code == 404:
        return False, (
            f"Aucun fichier à l'adresse https://{domain}{HTTP_FILE_PATH}. "
            "Vérifiez qu'il est bien accessible publiquement."
        )
    if response.status_code != 200:
        return False, (
            f"Le serveur a répondu {response.status_code} pour https://{domain}{HTTP_FILE_PATH}."
        )

    contenu = response.content[:MAX_FILE_BYTES].decode(errors="replace").strip()
    if contenu == token:
        return True, "Fichier trouvé et jeton correct."
    if token in contenu:
        # Toléré : un fichier créé depuis un éditeur qui y ajoute une ligne.
        # Exiger l'égalité stricte ferait échouer une preuve valable pour une
        # raison que le client ne peut pas voir.
        return True, "Fichier trouvé, jeton reconnu."
    return False, (
        "Le fichier existe mais ne contient pas le jeton attendu. Il doit "
        "contenir le jeton seul, sans autre texte."
    )


__all__ = [
    "DNS_TXT_PREFIX",
    "HTTP_FILE_PATH",
    "OwnershipCheckError",
    "expected_dns_record",
    "verify_dns_txt",
    "verify_http_file",
]
