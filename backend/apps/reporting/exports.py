"""Export tableur (V2-3, ADR-028).

Pour ceux qui veulent retravailler les chiffres : un fichier plat, une ligne
par indicateur, avec sa valeur, la valeur de comparaison et la date. Pas un
export de la base — un export du **tableau de bord**, c'est-à-dire exactement
ce que le RSSI a sous les yeux.

C'est ce point qui compte : si le tableur et l'écran divergeaient, le RSSI
recommencerait à tout recalculer à la main, et cette version n'aurait servi à
rien. Les deux lisent donc la même structure, produite une fois.
"""

from datetime import date

#: Ligne d'en-tête, en français : le fichier est ouvert par un humain, pas
#: consommé par un programme.
HEADERS = ["Indicateur", "Valeur", "Comparaison", "Écart", "Mesuré le"]


def _fr(valeur) -> str:
    """Nombre à la française — la virgule décimale. Un tableur français lit
    « 12.4 » comme du texte et refuse de l'additionner."""
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, float):
        return f"{valeur:.1f}".replace(".", ",")
    return str(valeur)


def _jour(valeur) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, date):
        return valeur.isoformat()
    return valeur.date().isoformat() if hasattr(valeur, "date") else str(valeur)


def csv_rows(donnees: dict) -> list[list]:
    """Le tableau de bord, à plat. Ordre = ordre de lecture en comité."""
    periode = donnees["period"]
    exposition = donnees["exposure"]
    plan = donnees["action_plan"]
    maturite = donnees["maturity"]
    surveillance = donnees["monitoring"]
    fin = _jour(periode["end"])
    debut = _jour(periode["start"])

    lignes = [
        [f"Rapport — {donnees['tenant_name']}"],
        [f"Période : {periode['label']} — du {debut} au {fin}"],
        [],
        HEADERS,
        ["— Exposition —"],
        [
            "Score d'exposition",
            _fr(exposition["exposure_score"]),
            _fr(exposition["exposure_score_at_period_start"]),
            _fr(exposition["evolution"]["delta"]),
            fin,
        ],
        [
            "Compromissions ouvertes",
            _fr(exposition["open_total"]),
            _fr(exposition["open_at_period_start"]),
            _fr(exposition["open_evolution"]["delta"]),
            fin,
        ],
        ["dont critiques", _fr(exposition["open_by_severity"]["critical"]), "", "", fin],
        ["dont élevées", _fr(exposition["open_by_severity"]["high"]), "", "", fin],
        ["dont attention", _fr(exposition["open_by_severity"]["attention"]), "", "", fin],
        ["Nouvelles sur la période", _fr(exposition["new_in_period"]), "", "", fin],
        ["Traitées sur la période", _fr(exposition["treated_in_period"]), "", "", fin],
        ["Ignorées sur la période", _fr(exposition["ignored_in_period"]), "", "", fin],
        [
            "Délai moyen de traitement (jours)",
            _fr(exposition["average_treatment_days"]),
            "",
            "",
            fin,
        ],
        ["— Maturité —"],
        [
            "Score de maturité",
            _fr(maturite["score"]),
            _fr(maturite["previous_score"]),
            _fr(maturite["delta"]),
            _jour(maturite["measured_at"]),
        ],
        ["Diagnostics terminés sur la période", _fr(maturite["completed_in_period"]), "", "", fin],
        ["— Plan d'action —"],
        ["Actions ouvertes", _fr(plan["open"]), "", "", fin],
        ["Actions terminées (total)", _fr(plan["done"]), "", "", fin],
        ["Actions terminées sur la période", _fr(plan["completed_in_period"]), "", "", fin],
        ["Actions en retard", _fr(plan["overdue"]), "", "", fin],
        ["Actions ouvertes sans échéance", _fr(plan["without_due_date"]), "", "", fin],
        ["Taux d'avancement (%)", _fr(plan["completion_rate"]), "", "", fin],
        ["— Surveillance —"],
        [
            "Disponibilité (%)",
            _fr(surveillance["uptime_percentage"]),
            "",
            _fr(surveillance["uptime_evolution"]["delta"]),
            fin,
        ],
        ["Contrôles sur la période", _fr(surveillance["checks_in_period"]), "", "", fin],
        ["Contrôles en échec", _fr(surveillance["failed_checks_in_period"]), "", "", fin],
        ["Alertes ouvertes", _fr(surveillance["open_alerts"]), "", "", fin],
        ["Actifs déclarés", _fr(surveillance["assets_total"]), "", "", fin],
        ["Certificats à échéance (< 60 j)", _fr(len(surveillance["certificates"])), "", "", fin],
    ]

    if exposition["by_asset"]:
        lignes.append([])
        lignes.append(["— Exposition par actif —"])
        lignes.append(["Actif", "Score", "Compromissions ouvertes", "", fin])
        for actif in exposition["by_asset"]:
            lignes.append(
                [
                    actif["asset_value"],
                    _fr(actif["score"]),
                    _fr(actif["findings_count"]),
                    "",
                    fin,
                ]
            )

    if exposition["series"]:
        lignes.append([])
        lignes.append(["— Compromissions ouvertes, jour par jour —"])
        lignes.append(["Date", "Ouvertes"])
        for point in exposition["series"]:
            lignes.append([_jour(point["date"]), _fr(point["open"])])

    return lignes


def filename(donnees: dict, extension: str) -> str:
    """Nom de fichier lisible et triable : le nom du client, puis la date de
    fin. Deux exports du même client se rangent dans l'ordre chronologique."""
    nom = "".join(
        c if c.isalnum() or c in "-_" else "-" for c in donnees["tenant_name"].lower()
    ).strip("-")
    return f"rapport-{nom or 'entreprise'}-{_jour(donnees['period']['end'])}.{extension}"
