"""Le rapport de formation en PDF (F3).

Même construction en deux temps que le rapport de comité (ADR-028) :
``build_html`` produit le document et se teste partout, ``render_pdf``
l'imprime via WeasyPrint. La séparation permet de vérifier le FOND — les
chiffres, les phrases, l'absence de toute ligne nominative — sur une machine
sans moteur de rendu.
"""

from html import escape

MOIS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


class PdfUnavailableError(RuntimeError):
    """Le moteur de rendu n'est pas disponible sur cet environnement."""


def _date_fr(valeur) -> str:
    return f"{valeur.day} {MOIS_FR[valeur.month - 1]} {valeur.year}"


STYLESHEET = """
@page { size: A4; margin: 18mm; }
body { font-family: 'Liberation Sans', sans-serif; color: #1f2937; font-size: 10pt; }
h1 { font-size: 18pt; color: #1e3a8a; margin: 0 0 1mm; }
.sous-titre { color: #4b5563; margin: 0 0 8mm; }
h2 { font-size: 12pt; color: #1e3a8a; margin: 8mm 0 2mm; }
table { width: 100%; border-collapse: collapse; margin-top: 2mm; }
th, td { border-bottom: 1px solid #e5e7eb; padding: 2mm; text-align: left; }
th { background: #f3f4f6; }
.nombre { text-align: right; }
.pied { margin-top: 10mm; font-size: 8pt; color: #6b7280; line-height: 1.5; }
"""


def build_html(rapport: dict) -> str:
    resume = rapport["summary"]
    parties = [
        f"<h1>Formation — {escape(rapport['tenant_name'])}</h1>",
        f"<p class='sous-titre'>{escape(rapport['course_title'])} · édité le "
        f"{_date_fr(rapport['generated_at'])}</p>",
        "<h2>Participation</h2>",
        "<table><tbody>"
        f"<tr><th>Salariés inscrits</th><td class='nombre'>{resume['learners_total']}</td></tr>"
        f"<tr><th>N'ont pas commencé</th><td class='nombre'>{resume['not_started']}</td></tr>"
        f"<tr><th>En cours</th><td class='nombre'>{resume['in_progress']}</td></tr>"
        f"<tr><th>Ont terminé</th><td class='nombre'>{resume['completed']}</td></tr>"
        f"<tr><th>Taux de participation</th>"
        f"<td class='nombre'>{resume['participation_rate']} %</td></tr>"
        f"<tr><th>Taux de réussite</th>"
        f"<td class='nombre'>{resume['success_rate']} %</td></tr>"
        f"<tr><th>Score moyen</th><td class='nombre'>"
        f"{resume['average_score'] if resume['average_score'] is not None else '—'} %</td></tr>"
        "</tbody></table>",
    ]

    if rapport["hardest_questions"]:
        parties.append(
            "<h2>Ce que l'entreprise maîtrise le moins</h2>"
            "<p>Les questions les plus souvent ratées. Elles indiquent ce qu'il faut "
            "expliquer autrement, plutôt que répéter.</p>"
            "<table><thead><tr><th>Question</th><th>Écran concerné</th>"
            "<th class='nombre'>Taux d'échec</th></tr></thead><tbody>"
            + "".join(
                f"<tr><td>{escape(q['text'])}</td>"
                f"<td>{q['screen_order']}. {escape(q['screen_title'])}</td>"
                f"<td class='nombre'>{q['failure_rate']} %</td></tr>"
                for q in rapport["hardest_questions"]
            )
            + "</tbody></table>"
        )

    if rapport["campaigns"]:
        parties.append(
            "<h2>Campagne après campagne</h2>"
            "<table><thead><tr><th>Cours</th><th>Échéance</th>"
            "<th class='nombre'>Inscrits</th><th class='nombre'>Participation</th>"
            "<th class='nombre'>Réussite</th></tr></thead><tbody>"
            + "".join(
                f"<tr><td>{escape(c['course_title'])}</td>"
                f"<td>{c['due_date']:%d/%m/%Y}</td>"
                f"<td class='nombre'>{c['learners_total']}</td>"
                f"<td class='nombre'>{c['participation_rate']} %</td>"
                f"<td class='nombre'>{c['success_rate']} %</td></tr>"
                for c in rapport["campaigns"]
            )
            + "</tbody></table>"
        )

    parties.append(
        "<p class='pied'>Ce document ne comporte aucun résultat individuel. "
        "La formation est un dispositif de sensibilisation collective : le suivi par "
        "salarié existe dans l'application, sert uniquement à relancer, et sa "
        "consultation est tracée.</p>"
    )

    corps = "".join(parties)
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<title>Formation — {escape(rapport['tenant_name'])}</title>"
        f"<style>{STYLESHEET}</style></head><body>{corps}</body></html>"
    )


def render_pdf(rapport: dict) -> bytes:
    try:
        import weasyprint
    except (ImportError, OSError) as exc:  # pragma: no cover - dépend du système
        raise PdfUnavailableError(
            "L'impression du rapport n'est pas disponible pour le moment. "
            "Les mêmes chiffres restent exportables en tableur."
        ) from exc

    return weasyprint.HTML(string=build_html(rapport)).write_pdf()
