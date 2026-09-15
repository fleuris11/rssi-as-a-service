"""Ce qui entoure l'assistant, sans jamais appeler l'IA (lot C, C4).

Deux services, tous deux DÉTERMINISTES :

- ``suggestions`` : les questions de départ, tirées de la situation réelle du
  client. « Une zone de saisie vide devant un dirigeant reste vide » — et une
  suggestion générique (« Suis-je en conformité RGPD ? ») ne lui dit pas que
  la plateforme connaît déjà ses deux compromissions critiques.
- ``related_links`` : les écrans vers lesquels une réponse renvoie. Déduits
  du texte par une table FERMÉE de routes : on ne demande pas au modèle
  d'écrire des liens, il en inventerait.

Rien ici ne passe par l'API Anthropic (règle d'architecture n°3) : ce sont
des règles, testables et gratuites. Les chiffres cités viennent des services
des autres apps (règle n°1), jamais de leurs modèles.
"""

import re

from django.utils import timezone

from apps.actions import services as actions_services
from apps.assessments import services as assessments_services
from apps.monitoring import services as monitoring_services
from apps.threat_intelligence import services as ti_services

LIMITE_SUGGESTIONS = 4


def _pluriel(n: int, singulier: str, pluriel: str) -> str:
    return singulier if n == 1 else pluriel


def suggestions(tenant) -> list[dict]:
    """Les questions de départ, de la plus urgente à la moins urgente.

    Chaque suggestion porte la question telle qu'elle sera envoyée, la raison
    pour laquelle elle est proposée, et l'écran où l'on agit. Aucune donnée
    personnelle : des comptes et des scores, jamais une adresse ni un nom.
    """
    propositions = []

    critiques = ti_services.count_critical_open_findings(tenant)
    if critiques:
        propositions.append(
            {
                "question": (
                    f"Que faire de mes {critiques} "
                    f"{_pluriel(critiques, 'compromission critique', 'compromissions critiques')} ?"
                ),
                "reason": "Des accès sont en circulation et exploitables immédiatement.",
                "link": {"to": "/compromissions", "label": "Voir les compromissions"},
            }
        )

    alertes = monitoring_services.list_open_alerts(tenant).count()
    if alertes:
        propositions.append(
            {
                "question": (
                    f"J'ai {alertes} {_pluriel(alertes, 'alerte ouverte', 'alertes ouvertes')} "
                    "sur mes sites : est-ce grave ?"
                ),
                "reason": "La surveillance a relevé un problème qui n'est pas résolu.",
                "link": {"to": "/surveillance", "label": "Voir la surveillance"},
            }
        )

    evaluation = assessments_services.get_latest_completed_assessment(tenant)
    if evaluation is None:
        propositions.append(
            {
                "question": "Par où commencer pour évaluer la sécurité de mon entreprise ?",
                "reason": "Aucun diagnostic n'est encore terminé.",
                "link": {"to": "/diagnostic", "label": "Faire le diagnostic"},
            }
        )
    else:
        aujourd_hui = timezone.localdate()
        ouvertes = [
            item
            for item in actions_services.list_action_items(tenant)
            if item.status in actions_services.OPEN_STATUSES
        ]
        en_retard = [i for i in ouvertes if i.due_date and i.due_date < aujourd_hui]
        if en_retard:
            propositions.append(
                {
                    "question": (
                        f"{len(en_retard)} "
                        + _pluriel(len(en_retard), "action est en retard", "actions sont en retard")
                        + " : lesquelles prioriser ?"
                    ),
                    "reason": "Des échéances du plan d'action sont dépassées.",
                    "link": {"to": "/plan-action", "label": "Ouvrir le plan d’action"},
                }
            )
        if ouvertes:
            propositions.append(
                {
                    "question": "Par quoi commencer dans mon plan d'action ?",
                    "reason": (
                        f"{len(ouvertes)} "
                        f"{_pluriel(len(ouvertes), 'action reste', 'actions restent')} à mener."
                    ),
                    "link": {"to": "/plan-action", "label": "Ouvrir le plan d’action"},
                }
            )
        if evaluation.score_global is not None:
            score = round(evaluation.score_global)
            propositions.append(
                {
                    "question": f"Que veut dire mon score de maturité de {score} sur 100 ?",
                    "reason": "C'est le résultat de votre dernier diagnostic.",
                    "link": {"to": "/resultats", "label": "Voir les résultats"},
                }
            )

    if not propositions:
        propositions.append(
            {
                "question": (
                    "Quelles sont les trois mesures les plus utiles pour une entreprise "
                    "comme la mienne ?"
                ),
                "reason": "Rien d'urgent n'est ouvert : c'est le moment de prendre de l'avance.",
                "link": None,
            }
        )

    return propositions[:LIMITE_SUGGESTIONS]


#: Les écrans vers lesquels une réponse peut renvoyer, et ce qui les appelle.
#: Liste FERMÉE : un lien absent de cette table n'existe pas pour l'assistant.
LIENS = (
    ("/compromissions", "Voir les compromissions", r"compromission|fuite|mots? de passe"),
    ("/exposition", "Voir l’exposition", r"exposition"),
    ("/plan-action", "Ouvrir le plan d’action", r"plan d.action|actions? prioritaires?"),
    ("/resultats", "Voir les résultats du diagnostic", r"score de maturit|maturité"),
    ("/diagnostic", "Faire le diagnostic", r"diagnostic"),
    (
        "/surveillance",
        "Voir la surveillance",
        r"certificat|\bspf\b|dmarc|en-t[êe]tes? de s[ée]curit|disponibilit|surveillance",
    ),
    (
        "/documents",
        "Ouvrir les documents",
        r"charte|politique de s[ée]curit|proc[ée]dure|plan de continuit|registre des incidents",
    ),
    ("/comptes-surveilles", "Voir les comptes surveillés", r"comptes? surveill"),
    ("/veille", "Voir la veille réglementaire", r"veille|r[ée]glementation|nis ?2"),
)

LIMITE_LIENS = 3


def related_links(texte: str) -> list[dict]:
    """Les écrans dont parle une réponse, dans l'ordre où elle en parle."""
    if not texte:
        return []
    # Une entrée par route dans LIENS et une seule correspondance par motif :
    # un doublon est impossible par construction, sans garde à maintenir.
    trouves = []
    for route, libelle, motif in LIENS:
        correspondance = re.search(motif, texte, flags=re.IGNORECASE)
        if correspondance:
            trouves.append((correspondance.start(), route, libelle))
    trouves.sort()
    return [{"to": route, "label": libelle} for _position, route, libelle in trouves][:LIMITE_LIENS]
