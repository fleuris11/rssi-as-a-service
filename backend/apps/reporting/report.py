"""Le document du comité (V2-3, ADR-028).

Écrit pour être lu par une direction, pas par un RSSI : la personne qui le
reçoit n'a pas le vocabulaire, n'ouvrira pas le produit, et décide quand
même. Chaque chiffre est donc accompagné de ce qu'il veut dire, et aucun terme
technique n'est laissé sans explication.

La construction est séparée en deux : ``build_html`` produit le document
(testable partout, sans dépendance système) et ``render_pdf`` l'imprime via
WeasyPrint (ADR-012), dont le moteur de rendu est installé au niveau du
Dockerfile et de la CI. Cette séparation n'est pas cosmétique : elle permet de
vérifier le FOND du rapport — les chiffres, les phrases, l'absence du nom du
fournisseur — sur n'importe quelle machine, y compris celles où le moteur
n'est pas installé.
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
    if valeur is None:
        return "—"
    jour = valeur.date() if hasattr(valeur, "date") else valeur
    return f"{jour.day} {MOIS_FR[jour.month - 1]} {jour.year}"


def _nombre(valeur, suffixe="") -> str:
    if valeur is None:
        return "non mesuré"
    if isinstance(valeur, float):
        return f"{valeur:.1f}".replace(".", ",") + suffixe
    return f"{valeur}{suffixe}"


def _evolution_phrase(evolution: dict, unite: str = "") -> str:
    """L'écart, dit en français plutôt qu'en flèche.

    Un PDF n'a pas d'infobulle : une flèche verte sans phrase laisse le
    lecteur deviner si monter est une bonne nouvelle.
    """
    if evolution["delta"] is None:
        return "Pas de point de comparaison sur la période précédente."
    if evolution["direction"] == "stable":
        return "Stable par rapport au début de la période."
    sens = "en hausse de" if evolution["direction"] == "hausse" else "en baisse de"
    jugement = ""
    if evolution["is_improvement"] is True:
        jugement = " — c'est une amélioration"
    elif evolution["is_improvement"] is False:
        jugement = " — c'est une dégradation"
    return f"{sens.capitalize()} {_nombre(abs(evolution['delta']))}{unite}{jugement}."


STYLESHEET = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "Helvetica", "Arial", sans-serif; color: #1f2430; font-size: 10.5pt;
       line-height: 1.45; }
h1 { font-size: 20pt; margin: 0 0 2mm; }
h2 { font-size: 13pt; margin: 8mm 0 2mm; border-bottom: 1px solid #d8dce4;
     padding-bottom: 1.5mm; }
h3 { font-size: 11pt; margin: 4mm 0 1mm; }
.chapeau { color: #5a6273; margin: 0 0 6mm; }
.grille { display: flex; flex-wrap: wrap; gap: 4mm; margin-bottom: 3mm; }
.carte { flex: 1 1 45%; border: 1px solid #d8dce4; border-radius: 3mm; padding: 4mm; }
.carte .valeur { font-size: 20pt; font-weight: 600; }
.carte .titre { font-size: 9pt; text-transform: uppercase; letter-spacing: .4pt;
                color: #5a6273; }
.carte .quoi { font-size: 9pt; color: #5a6273; margin-top: 1.5mm; }
table { width: 100%; border-collapse: collapse; margin-top: 2mm; font-size: 9.5pt; }
th, td { text-align: left; padding: 1.6mm 2mm; border-bottom: 1px solid #e8eaef; }
th { color: #5a6273; font-weight: 600; font-size: 8.5pt; text-transform: uppercase; }
.fait { border-left: 3px solid #d8dce4; padding: 1mm 0 1mm 4mm; margin-bottom: 3mm; }
.fait.critical { border-color: #b4232c; }
.fait.warning { border-color: #b8770a; }
.fait.positive { border-color: #1c7a4b; }
.fait .titre { font-weight: 600; }
.fait .detail { color: #5a6273; font-size: 9.5pt; }
.note { color: #5a6273; font-size: 9pt; font-style: italic; }
footer { margin-top: 8mm; padding-top: 3mm; border-top: 1px solid #d8dce4;
         color: #5a6273; font-size: 8.5pt; }
"""


def _carte(titre, valeur, quoi) -> str:
    return (
        f'<div class="carte"><div class="titre">{escape(titre)}</div>'
        f'<div class="valeur">{escape(valeur)}</div>'
        f'<div class="quoi">{escape(quoi)}</div></div>'
    )


def build_html(donnees: dict) -> str:
    """Le rapport, en HTML autonome (styles inclus, aucune ressource externe).

    Aucune image, aucune police téléchargée : un document destiné à circuler
    par email doit s'ouvrir hors ligne, dix ans après, sans rien réclamer.
    """
    periode = donnees["period"]
    exposition = donnees["exposure"]
    plan = donnees["action_plan"]
    maturite = donnees["maturity"]
    surveillance = donnees["monitoring"]

    parties = [
        f"<h1>Rapport de sécurité — {escape(donnees['tenant_name'])}</h1>",
        f'<p class="chapeau">{escape(periode["label"])} : '
        f"du {_date_fr(periode['start'])} au {_date_fr(periode['end'])}.</p>",
        # --- Situation -------------------------------------------------------
        "<h2>1. La situation aujourd'hui</h2>",
        '<div class="grille">',
        _carte(
            "Compromissions ouvertes",
            _nombre(exposition["open_total"]),
            "Données de l'entreprise retrouvées en circulation et non encore traitées.",
        ),
        _carte(
            "Score d'exposition",
            f"{exposition['exposure_score']} / 100",
            "Gravité, fraîcheur et exploitabilité des fuites ouvertes. Plus bas est mieux.",
        ),
        _carte(
            "Score de maturité",
            f"{_nombre(maturite['score'])} / 100"
            if maturite["score"] is not None
            else "non mesuré",
            "Réponses au référentiel d'hygiène de l'ANSSI. Mesure l'organisation, pas les fuites.",
        ),
        _carte(
            "Disponibilité des sites",
            _nombre(surveillance["uptime_percentage"], " %"),
            "Part du temps où les sites surveillés ont répondu normalement.",
        ),
        "</div>",
        '<p class="note">Ces deux scores ne s\'additionnent pas et ne se moyennent pas : '
        "la maturité mesure ce que l'entreprise a mis en place, l'exposition mesure ce qui "
        "circule à son sujet. Une bonne organisation ne protège pas d'une fuite chez un "
        "fournisseur, et l'inverse est vrai aussi.</p>",
        # --- Évolution -------------------------------------------------------
        "<h2>2. L'évolution sur la période</h2>",
        "<table><tr><th>Indicateur</th><th>Début de période</th><th>Aujourd'hui</th>"
        "<th>Lecture</th></tr>",
        f"<tr><td>Compromissions ouvertes</td><td>{exposition['open_at_period_start']}</td>"
        f"<td>{exposition['open_total']}</td>"
        f"<td>{escape(_evolution_phrase(exposition['open_evolution']))}</td></tr>",
        f"<tr><td>Score d'exposition</td>"
        f"<td>{exposition['exposure_score_at_period_start']}</td>"
        f"<td>{exposition['exposure_score']}</td>"
        f"<td>{escape(_evolution_phrase(exposition['evolution']))}</td></tr>",
        f"<tr><td>Score de maturité</td><td>{_nombre(maturite['previous_score'])}</td>"
        f"<td>{_nombre(maturite['score'])}</td>"
        f"<td>{escape(_evolution_phrase(maturite['evolution'], ' points'))}</td></tr>",
        f"<tr><td>Disponibilité</td><td>—</td>"
        f"<td>{_nombre(surveillance['uptime_percentage'], ' %')}</td>"
        f"<td>{escape(_evolution_phrase(surveillance['uptime_evolution'], ' points'))}</td></tr>",
        "</table>",
    ]

    if exposition["by_asset"]:
        parties.append("<h3>Exposition par actif</h3>")
        parties.append(
            "<table><tr><th>Actif</th><th>Score</th><th>Compromissions ouvertes</th></tr>"
        )
        for actif in exposition["by_asset"]:
            parties.append(
                f"<tr><td>{escape(actif['asset_value'])}</td><td>{actif['score']}</td>"
                f"<td>{actif['findings_count']}</td></tr>"
            )
        parties.append("</table>")

    # --- Faits marquants -----------------------------------------------------
    parties.append("<h2>3. Les faits marquants</h2>")
    if donnees["highlights"]:
        for fait in donnees["highlights"]:
            parties.append(
                f'<div class="fait {escape(fait["tone"])}">'
                f'<div class="titre">{escape(fait["title"])}</div>'
                f'<div class="detail">{escape(fait["detail"])}</div></div>'
            )
    else:
        parties.append(
            '<p class="note">Aucun fait marquant sur la période : ni nouvelle '
            "compromission, ni changement de score, ni action terminée.</p>"
        )

    # --- Actions menées ------------------------------------------------------
    parties.extend(
        [
            "<h2>4. Les actions menées</h2>",
            "<table><tr><th>Indicateur</th><th>Sur la période</th><th>Au total</th></tr>",
            f"<tr><td>Compromissions traitées</td><td>{exposition['treated_in_period']}</td>"
            f"<td>—</td></tr>",
            f"<tr><td>Compromissions écartées</td><td>{exposition['ignored_in_period']}</td>"
            f"<td>—</td></tr>",
            f"<tr><td>Actions du plan terminées</td><td>{plan['completed_in_period']}</td>"
            f"<td>{plan['done']} sur {plan['total']}</td></tr>",
            f"<tr><td>Diagnostics terminés</td><td>{maturite['completed_in_period']}</td>"
            f"<td>—</td></tr>",
            "</table>",
        ]
    )
    if exposition["average_treatment_days"] is not None:
        parties.append(
            f'<p class="note">Délai moyen entre la détection d\'une compromission et son '
            f"traitement : {_nombre(exposition['average_treatment_days'])} jours.</p>"
        )

    # --- Reste à faire -------------------------------------------------------
    parties.append("<h2>5. Ce qui reste à faire</h2>")
    if donnees["remaining"]:
        for point in donnees["remaining"]:
            parties.append(
                f'<div class="fait"><div class="titre">{escape(point["title"])}</div>'
                f'<div class="detail">{escape(point["detail"])}</div></div>'
            )
    else:
        parties.append(
            '<p class="note">Rien en attente : aucune compromission ouverte, aucune '
            "action en retard.</p>"
        )

    if surveillance["certificates"]:
        parties.append("<h3>Certificats à renouveler</h3>")
        parties.append("<table><tr><th>Actif</th><th>Jours restants</th></tr>")
        for cert in surveillance["certificates"]:
            parties.append(
                f"<tr><td>{escape(cert['asset_value'])}</td><td>{cert['days_left']}</td></tr>"
            )
        parties.append("</table>")
        parties.append(
            '<p class="note">Un certificat expiré rend le site inaccessible et affiche '
            "un avertissement de sécurité aux visiteurs.</p>"
        )

    parties.append(
        "<footer>Document produit automatiquement à partir des données de surveillance "
        f"de l'entreprise, arrêtées au {_date_fr(periode['end'])}. Les chiffres sont "
        "reproductibles : deux générations sur la même période donnent le même "
        "document.</footer>"
    )

    corps = "".join(parties)
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<title>Rapport de sécurité — {escape(donnees['tenant_name'])}</title>"
        f"<style>{STYLESHEET}</style></head><body>{corps}</body></html>"
    )


def render_pdf(donnees: dict) -> bytes:
    """Imprime le rapport. Même moteur que l'export documentaire (ADR-012)."""
    try:
        import weasyprint
    except (ImportError, OSError) as exc:  # pragma: no cover - dépend du système
        raise PdfUnavailableError(
            "La génération du document n'est pas disponible pour le moment. "
            "Les mêmes chiffres restent exportables en tableur."
        ) from exc

    return weasyprint.HTML(string=build_html(donnees)).write_pdf()
