"""Composition des indicateurs de comité (V2-3, ADR-028).

Cette app ne possède aucun modèle. Elle **compose** : chaque app calcule ses
propres indicateurs, sur ses propres tables, par son `services.py` ; celle-ci
les rassemble, y ajoute la période et la comparaison, et rend un objet unique.

C'est ce qui permet de tenir la règle d'architecture (une app n'atteint jamais
les modèles d'une autre) tout en gardant les agrégats **en base** : le SQL est
écrit là où vivent les tables, et non ici sur des listes déjà chargées.

Ce qu'on ne fait pas, et c'est une décision (ADR-028) : **aucun score global
de sécurité**. Maturité et exposition mesurent deux choses sans rapport —
l'organisation d'un côté, ce qui circule de l'autre. Une moyenne des deux
monterait quand l'entreprise remplit un questionnaire et descendrait quand un
fournisseur se fait pirater, sans qu'aucune des deux variations ne soit
imputable à la même action. Elle rendrait les deux mesures injustifiables.
"""

from apps.actions import services as actions_services
from apps.assessments import services as assessments_services
from apps.monitoring import services as monitoring_services
from apps.threat_intelligence import services as ti_services

from . import periods


def _evolution(courant, precedent, *, sens: str = "hausse_positive") -> dict:
    """Écart entre deux valeurs, et ce qu'il vaut.

    ``sens`` dit si monter est une bonne nouvelle. Sans lui, l'écran devrait
    le savoir pour chaque indicateur — et une flèche verte sur « fuites en
    hausse » est le genre d'erreur qu'on ne voit qu'en comité.
    """
    if courant is None or precedent is None:
        return {"delta": None, "direction": "inconnue", "is_improvement": None}

    delta = round(courant - precedent, 1)
    if delta == 0:
        return {"delta": 0, "direction": "stable", "is_improvement": None}

    monte = delta > 0
    return {
        "delta": delta,
        "direction": "hausse" if monte else "baisse",
        "is_improvement": monte if sens == "hausse_positive" else not monte,
    }


def build_dashboard(tenant, period: periods.Period) -> dict:
    """Tous les indicateurs de la période, avec leur comparaison.

    Chaque bloc est daté (``measured_at`` ou les bornes de la période) : c'est
    ce qui permet au RSSI de dire « nous étions à X en juin, nous sommes à Y
    aujourd'hui » plutôt que de présenter un instantané sans repère.
    """
    exposition = ti_services.breach_indicators(tenant, start=period.start, end=period.end)
    plan = actions_services.action_plan_indicators(tenant, start=period.start, end=period.end)
    maturite = assessments_services.maturity_indicators(tenant, start=period.start, end=period.end)
    surveillance = monitoring_services.monitoring_indicators(
        tenant, start=period.start, end=period.end
    )

    # Comparaison à la période précédente, sur les deux mesures qui ont un
    # sens dans le temps. Le reste (certificats, alertes ouvertes) est un état
    # instantané : le comparer à « il y a trois mois » n'apprendrait rien.
    surveillance_precedente = monitoring_services.monitoring_indicators(
        tenant, start=period.previous_start, end=period.previous_end
    )

    return {
        "period": period.as_dict(),
        "exposure": {
            **exposition,
            # Une baisse du score est une bonne nouvelle : le sens est porté
            # ici, une fois, plutôt que dans chaque composant d'affichage.
            "evolution": _evolution(
                exposition["exposure_score"],
                exposition["exposure_score_at_period_start"],
                sens="baisse_positive",
            ),
            "open_evolution": _evolution(
                exposition["open_total"],
                exposition["open_at_period_start"],
                sens="baisse_positive",
            ),
            "by_asset": ti_services.exposure_by_asset(tenant, at=period.end),
        },
        "action_plan": plan,
        "maturity": {
            **maturite,
            "evolution": _evolution(maturite["score"], maturite["previous_score"]),
        },
        "monitoring": {
            **surveillance,
            "uptime_evolution": _evolution(
                surveillance["uptime_percentage"],
                surveillance_precedente["uptime_percentage"],
            ),
        },
    }


def build_report(tenant, period: periods.Period) -> dict:
    """Le tableau de bord, plus ce qu'un comité attend en plus : des faits
    marquants et une lecture de ce qui reste à faire.

    Ces deux listes sont **déterministes** — des règles, pas une IA. Un
    document présenté à une direction doit être reproductible : deux
    générations sur les mêmes données donnent le même texte, et chaque phrase
    peut être justifiée par un chiffre du tableau.
    """
    tableau = build_dashboard(tenant, period)
    return {
        **tableau,
        "tenant_name": tenant.name,
        "highlights": highlights(tableau),
        "remaining": remaining(tableau),
    }


def highlights(tableau: dict) -> list[dict]:
    """Les faits marquants de la période, du plus important au moins.

    Chaque entrée répond à une question qu'un dirigeant pose réellement. Une
    règle qui ne trouve rien à dire ne dit rien : mieux vaut trois faits que
    dix lignes de remplissage dont personne ne lit la moitié.
    """
    faits = []
    exposition = tableau["exposure"]
    plan = tableau["action_plan"]
    maturite = tableau["maturity"]
    surveillance = tableau["monitoring"]

    critiques = exposition["open_by_severity"]["critical"]
    if critiques:
        faits.append(
            {
                "tone": "critical",
                "title": f"{critiques} compromission(s) critique(s) encore ouverte(s)",
                "detail": (
                    "Ce sont les fuites qui donnent un accès immédiat : mot de passe en "
                    "circulation, jeton de connexion volé ou clé technique exposée."
                ),
            }
        )

    if exposition["closed_in_period"]:
        faits.append(
            {
                "tone": "positive",
                "title": f"{exposition['closed_in_period']} compromission(s) traitée(s)",
                "detail": (
                    "Fuites fermées sur la période"
                    + (
                        f", en {exposition['average_treatment_days']} jours en moyenne."
                        if exposition["average_treatment_days"] is not None
                        else "."
                    )
                ),
            }
        )

    if exposition["new_in_period"]:
        faits.append(
            {
                "tone": "neutral",
                "title": f"{exposition['new_in_period']} nouvelle(s) compromission(s) détectée(s)",
                "detail": (
                    "Détections de la période. Une détection n'est pas un incident : "
                    "c'est une donnée retrouvée en circulation, souvent ancienne."
                ),
            }
        )

    if maturite["delta"] is not None and maturite["delta"] != 0:
        sens = "progressé" if maturite["delta"] > 0 else "reculé"
        faits.append(
            {
                "tone": "positive" if maturite["delta"] > 0 else "warning",
                "title": f"Maturité : {sens} de {abs(maturite['delta'])} points",
                "detail": (
                    f"Score de {maturite['previous_score']} à {maturite['score']} sur 100, "
                    "mesuré sur le référentiel d'hygiène de l'ANSSI."
                ),
            }
        )

    if plan["completed_in_period"]:
        faits.append(
            {
                "tone": "positive",
                "title": f"{plan['completed_in_period']} action(s) du plan terminée(s)",
                "detail": (f"{plan['done']} action(s) terminée(s) au total sur {plan['total']}."),
            }
        )

    if surveillance["certificates"]:
        premier = surveillance["certificates"][0]
        faits.append(
            {
                "tone": "warning",
                "title": f"Certificat à renouveler sous {premier['days_left']} jours",
                "detail": (
                    f"{premier['asset_value']}. Un certificat expiré rend le site "
                    "inaccessible et affiche un avertissement de sécurité aux visiteurs."
                ),
            }
        )

    return faits


def remaining(tableau: dict) -> list[dict]:
    """Ce qui reste à faire, formulé comme une décision à prendre.

    Un comité ne vote pas sur des constats : il arbitre. Chaque entrée dit
    donc ce qui est en jeu, pas seulement ce qui manque.
    """
    reste = []
    exposition = tableau["exposure"]
    plan = tableau["action_plan"]
    maturite = tableau["maturity"]

    if exposition["open_total"]:
        reste.append(
            {
                "title": f"{exposition['open_total']} compromission(s) à traiter",
                "detail": (
                    f"Dont {exposition['open_by_severity']['critical']} critique(s) et "
                    f"{exposition['open_by_severity']['high']} élevée(s)."
                ),
            }
        )

    if plan["overdue"]:
        detail = f"{plan['overdue']} action(s) dont l'échéance est dépassée."
        if plan["without_due_date"]:
            # Sans cette phrase, « 2 actions en retard » sur quarante sans
            # échéance se lirait comme une bonne nouvelle.
            detail += (
                f" {plan['without_due_date']} autre(s) action(s) ouverte(s) n'ont pas "
                "d'échéance : elles ne peuvent pas être en retard."
            )
        reste.append({"title": "Actions en retard", "detail": detail})
    elif plan["without_due_date"]:
        reste.append(
            {
                "title": "Actions sans échéance",
                "detail": (
                    f"{plan['without_due_date']} action(s) ouverte(s) n'ont pas de date "
                    "cible. Sans échéance, aucune ne peut être signalée en retard."
                ),
            }
        )

    if plan["open"]:
        reste.append(
            {
                "title": f"{plan['open']} action(s) du plan encore ouverte(s)",
                "detail": (
                    f"Taux d'avancement : {plan['completion_rate']} %."
                    if plan["completion_rate"] is not None
                    else "Plan d'action en cours."
                ),
            }
        )

    if maturite["score"] is None:
        reste.append(
            {
                "title": "Aucun diagnostic de maturité terminé",
                "detail": (
                    "Le diagnostic est l'entrée du produit : sans lui, ni score, ni plan "
                    "d'action priorisé."
                ),
            }
        )

    return reste
