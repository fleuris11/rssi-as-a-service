"""Corrélation « réutilisation possible » (Phase 8C, ADR-017).

Ce module répond à une question que le dirigeant se pose sans savoir la
formuler : « ce mot de passe qui a fuité, est-ce que je l'utilise ailleurs ? »
La plateforme ne peut pas y répondre — elle ne teste aucun identifiant nulle
part, et ne le fera jamais (ce serait de l'intrusion, ADR-010). Elle peut en
revanche signaler **quand la question se pose**.

D'où une contrainte de vocabulaire absolue, appliquée à chaque chaîne de ce
module et vérifiée par les tests : on écrit « réutilisation possible », « à
vérifier », « pourrait ». Jamais « confirmée », « compromis », « accès
validé », « avéré ». Un produit qui laisserait croire qu'il a testé un
identifiant mentirait à son client sur ce qu'il fait — et le premier
utilisateur qui s'en aperçoit ne fait plus confiance à rien d'autre dans
l'interface.

Le calcul est entièrement déterministe (aucune IA) : c'est un croisement
d'identifiants, pas une inférence.
"""

from urllib.parse import urlparse

from .models import BreachFinding

# Endpoints dont le payload porte un identifiant de compte exploitable pour
# le croisement. Les endpoints pré-incident (radar/darkweb/asm) en sont
# absents : ils décrivent une exposition publique, pas un compte.
IDENTIFIER_BEARING_ENDPOINTS = (
    BreachFinding.SourceEndpoint.STEALER,
    BreachFinding.SourceEndpoint.COMBO,
    BreachFinding.SourceEndpoint.CREDS,
)

SIGNAL_REPEATED_EXPOSURE = "repeated_exposure"
SIGNAL_EXTERNAL_SERVICE = "external_service"

# Formulations — centralisées ici précisément pour que la règle de vocabulaire
# soit vérifiable en un seul endroit (voir tests/test_correlation.py).
SIGNAL_DEFINITIONS = {
    SIGNAL_REPEATED_EXPOSURE: {
        "label": "Réutilisation possible — identifiant vu dans plusieurs fuites",
        "explanation": (
            "Ce même identifiant apparaît dans plusieurs fuites distinctes. Nous ne pouvons "
            "pas savoir si le mot de passe est identique d'une fuite à l'autre : nous ne "
            "testons aucun identifiant. C'est une hypothèse à vérifier de votre côté, en "
            "regardant si ce compte utilise le même mot de passe sur ces différents services."
        ),
    },
    SIGNAL_EXTERNAL_SERVICE: {
        "label": "Réutilisation possible — adresse professionnelle sur un service externe",
        "explanation": (
            "Une adresse professionnelle de votre entreprise apparaît dans la fuite d'un "
            "service qui n'est pas le vôtre. Si la personne y utilisait le même mot de passe "
            "que sur ses accès professionnels, ceux-ci pourraient être atteignables. C'est une "
            "hypothèse à vérifier auprès de la personne concernée."
        ),
    },
}


def normalize_identifier(identifier: str) -> str:
    """Normalisation minimale et volontairement prudente : casse et espaces.

    On ne va PAS plus loin (pas de suppression des points dans la partie
    locale, pas de retrait des suffixes ``+quelquechose``) : ces règles sont
    propres à certains fournisseurs et pas à d'autres, et les appliquer
    partout fusionnerait des comptes réellement distincts. Un faux positif
    ici coûte cher — il ferait dire au produit « réutilisation possible »
    entre deux comptes sans rapport."""
    return (identifier or "").strip().lower()


def _identifier_of(finding: BreachFinding) -> str:
    return normalize_identifier(finding.identifier_plain or finding.identifier_masked)


def _finding_domain(finding: BreachFinding) -> str:
    """Domaine du service d'origine de la fuite, tel qu'annoncé par le
    fournisseur — jamais le domaine de l'actif surveillé."""
    for key in ("dom", "domain_name", "src"):
        value = finding.raw_data.get(key)
        if not value:
            continue
        text = str(value).strip().lower()
        if "://" in text:
            return urlparse(text).hostname or ""
        # ``src`` est souvent un libellé humain ("Fuite plateforme X 2023") :
        # on ne le retient que s'il ressemble à un domaine.
        if "." in text and " " not in text:
            return text
    return ""


def tenant_domains(assets) -> set[str]:
    """Domaines « de l'entreprise » : ceux de ses actifs déclarés. Sert à
    distinguer une fuite chez le tenant d'une fuite chez un tiers."""
    domains = set()
    for asset in assets:
        value = (asset.value or "").strip().lower()
        hostname = urlparse(value).hostname if "://" in value else value
        if hostname:
            domains.add(hostname)
            # www.exemple.fr et exemple.fr désignent la même entreprise.
            domains.add(hostname.removeprefix("www."))
    return domains


def correlate(findings: list[BreachFinding], *, tenant_emails: set[str], assets) -> dict[int, list]:
    """``{finding_id: [signaux]}`` pour un ensemble de fuites d'un même tenant.

    Déterministe et sans effet de bord : appelée à l'ingestion, au traitement
    d'une fuite, et à la construction du fil d'exposition — trois moments qui
    doivent donner exactement le même résultat sur les mêmes données.
    """
    normalized_emails = {normalize_identifier(email) for email in tenant_emails}
    domains = tenant_domains(assets)

    relevant = [f for f in findings if f.source_endpoint in IDENTIFIER_BEARING_ENDPOINTS]

    # Un identifiant masqué ("j.••••@ex••••.com") ne peut pas servir de clé de
    # croisement : plusieurs comptes distincts produisent le même masque. On
    # ne croise donc que sur des identifiants en clair — c'est-à-dire, par
    # construction (ADR-014 §4), ceux des membres du tenant.
    by_identifier: dict[str, list[BreachFinding]] = {}
    for finding in relevant:
        if not finding.identifier_plain:
            continue
        by_identifier.setdefault(_identifier_of(finding), []).append(finding)

    signals: dict[int, list] = {}
    for finding in relevant:
        identifier = _identifier_of(finding)
        if not finding.identifier_plain or not identifier:
            continue
        found: list[dict] = []

        siblings = [f for f in by_identifier.get(identifier, []) if f.id != finding.id]
        if siblings:
            found.append(
                {
                    "signal_type": SIGNAL_REPEATED_EXPOSURE,
                    **SIGNAL_DEFINITIONS[SIGNAL_REPEATED_EXPOSURE],
                    "identifier": finding.identifier_plain,
                    "related_finding_ids": sorted(f.id for f in siblings),
                    "occurrences": len(siblings) + 1,
                }
            )

        source_domain = _finding_domain(finding)
        is_external = bool(source_domain) and not any(
            source_domain == d or source_domain.endswith(f".{d}") for d in domains
        )
        if identifier in normalized_emails and is_external:
            found.append(
                {
                    "signal_type": SIGNAL_EXTERNAL_SERVICE,
                    **SIGNAL_DEFINITIONS[SIGNAL_EXTERNAL_SERVICE],
                    "identifier": finding.identifier_plain,
                    "related_finding_ids": [],
                    "external_service": source_domain,
                }
            )

        if found:
            signals[finding.id] = found

    return signals


def recommended_verification(finding: BreachFinding) -> str:
    """Phrase d'action ajoutée quand une réutilisation possible est détectée
    sur une fuite dont le mot de passe est récupérable — c'est là que la
    révélation prend son sens : elle permet de LEVER l'hypothèse."""
    if finding.has_secret and bytes(finding.secret_encrypted):
        return (
            "Pour lever le doute, vous pouvez révéler le mot de passe de cette fuite et "
            "vérifier s'il correspond à celui d'un accès professionnel. Cet accès est tracé "
            "dans le journal des révélations."
        )
    return (
        "Le mot de passe de cette fuite n'est pas disponible : vérifiez directement auprès "
        "de la personne concernée si elle réutilisait ce mot de passe ailleurs."
    )
