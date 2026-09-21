"""Le rapport de formation, à plat (F3).

Un fichier pour un comité ou pour un auditeur : une ligne par indicateur, les
questions les plus ratées, puis l'évolution campagne après campagne.

**Aucune ligne nominative.** Ce n'est pas un oubli : un export se transfère, se
reçoit par courriel et finit dans un dossier partagé. Y mettre le résultat de
chaque salarié reviendrait à diffuser dans l'entreprise ce que le module
s'attache à ne pas produire — un classement.
"""

from datetime import date


def _fr(valeur) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    return str(valeur)


def _jour(valeur) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, date):
        return valeur.strftime("%d/%m/%Y")
    return valeur.strftime("%d/%m/%Y") if hasattr(valeur, "strftime") else str(valeur)


def csv_rows(rapport: dict) -> list[list]:
    resume = rapport["summary"]
    lignes = [
        [f"Formation — {rapport['tenant_name']}"],
        [f"Périmètre : {rapport['course_title']}"],
        [f"Édité le {_jour(rapport['generated_at'])}"],
        [],
        ["Indicateur", "Valeur"],
        ["Salariés inscrits", _fr(resume["learners_total"])],
        ["N'ont pas commencé", _fr(resume["not_started"])],
        ["En cours", _fr(resume["in_progress"])],
        ["Ont terminé", _fr(resume["completed"])],
        ["Taux de participation (%)", _fr(resume["participation_rate"])],
        ["Taux de réussite (%)", _fr(resume["success_rate"])],
        ["Score moyen (%)", _fr(resume["average_score"])],
        ["Tentatives enregistrées", _fr(resume["attempts_total"])],
    ]

    if rapport["hardest_questions"]:
        lignes += [
            [],
            ["— Questions les plus ratées —"],
            ["Question", "Cours", "Écran", "Réponses", "Ratées", "Taux d'échec (%)"],
        ]
        for question in rapport["hardest_questions"]:
            lignes.append(
                [
                    question["text"],
                    question["course_title"],
                    f"{question['screen_order']}. {question['screen_title']}",
                    _fr(question["answers"]),
                    _fr(question["failed"]),
                    _fr(question["failure_rate"]),
                ]
            )

    if rapport["campaigns"]:
        lignes += [
            [],
            ["— Campagne après campagne —"],
            ["Cours", "Échéance", "Inscrits", "Participation (%)", "Réussite (%)"],
        ]
        for campagne in rapport["campaigns"]:
            lignes.append(
                [
                    campagne["course_title"],
                    _jour(campagne["due_date"]),
                    _fr(campagne["learners_total"]),
                    _fr(campagne["participation_rate"]),
                    _fr(campagne["success_rate"]),
                ]
            )

    return lignes


def filename(rapport: dict, extension: str) -> str:
    nom = "".join(
        c if c.isalnum() or c in "-_" else "-" for c in rapport["tenant_name"].lower()
    ).strip("-")
    jour = _jour(rapport["generated_at"]).replace("/", "-")
    return f"formation-{nom or 'entreprise'}-{jour}.{extension}"
