"""L'attestation de suivi, en PDF (F1, ADR-039).

Deux principes, et ils sont juridiques avant d'être techniques.

**Elle est signée du nom de l'entreprise cliente, pas du nôtre.** C'est elle
qui forme ses salariés ; nous fournissons l'outil. Faire figurer le nom du
fournisseur en bas d'une attestation laisserait entendre qu'un tiers certifie
quelque chose — ce qui est faux, et ce que personne ne nous a demandé.

**Elle dit « attestation de suivi », jamais « certification » ni
« habilitation ».** Ces deux mots ont un sens juridique que ce document n'a
pas. Un client pourrait, de parfaite bonne foi, produire une « certification »
devant un assureur ou un donneur d'ordre en croyant qu'elle vaut plus qu'elle
ne vaut. Le document porte donc, en toutes lettres, ce qu'il atteste et ce
qu'il n'atteste pas.

Construction séparée en deux, comme le rapport de comité (ADR-028) :
``build_html`` produit le document et se teste partout, ``render_pdf``
l'imprime via WeasyPrint dont le moteur est installé au Dockerfile (ADR-012).
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
@page { size: A4 landscape; margin: 18mm 20mm; }
body { font-family: 'Liberation Sans', sans-serif; color: #1f2937; }
.cadre { border: 2px solid #1e3a8a; padding: 14mm 16mm; height: 100%; }
h1 { font-size: 26pt; color: #1e3a8a; margin: 0 0 2mm; letter-spacing: .5px; }
.sous-titre { font-size: 11pt; color: #4b5563; margin: 0 0 12mm; }
.nom { font-size: 22pt; font-weight: bold; margin: 6mm 0 2mm; }
.cours { font-size: 15pt; margin: 0 0 8mm; }
.ligne { font-size: 11pt; margin: 1mm 0; }
.pied { margin-top: 12mm; font-size: 9pt; color: #6b7280; line-height: 1.5; }
.serie { font-family: monospace; font-size: 9pt; color: #6b7280; }
"""


def build_html(attestation) -> str:
    """Le document. Prend les champs FIGÉS de l'attestation, jamais les objets
    vivants : un cours renommé depuis ne doit rien changer ici."""
    nom = escape(attestation.learner_name)
    cours = escape(attestation.course_title)
    entreprise = escape(attestation.company_name)
    corps = (
        "<div class='cadre'>"
        "<h1>Attestation de suivi</h1>"
        "<p class='sous-titre'>Formation à la sécurité des systèmes d'information</p>"
        f"<p class='ligne'>{entreprise} atteste que&nbsp;:</p>"
        f"<p class='nom'>{nom}</p>"
        f"<p class='cours'>a suivi le cours «&nbsp;{cours}&nbsp;» "
        f"(version {attestation.course_version})</p>"
        f"<p class='ligne'>Résultat au questionnaire&nbsp;: "
        f"<strong>{attestation.score} %</strong></p>"
        f"<p class='ligne'>Date&nbsp;: {_date_fr(attestation.issued_at)}</p>"
        f"<p class='ligne'>Délivrée par&nbsp;: {entreprise}</p>"
        "<p class='pied'>"
        "Ce document atteste du <strong>suivi d'un cours</strong> et de la réussite de son "
        "questionnaire. Il ne constitue ni une certification, ni une habilitation, ni une "
        "qualification professionnelle.<br>"
        # La limite du lien nominatif, écrite sur le document lui-même et pas
        # seulement dans l'ADR : c'est ici qu'elle sera lue par celui qui
        # reçoit l'attestation et se demande ce qu'elle prouve.
        "Le suivi a été réalisé au moyen d'un lien personnel transmis au salarié&nbsp;; "
        "l'identité de la personne ayant réalisé le parcours n'a pas fait l'objet d'une "
        "vérification.<br>"
        f"<span class='serie'>Référence&nbsp;: {escape(attestation.serial)}</span>"
        "</p>"
        "</div>"
    )
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<title>Attestation de suivi — {nom}</title>"
        f"<style>{STYLESHEET}</style></head><body>{corps}</body></html>"
    )


def filename(attestation) -> str:
    nom = "".join(
        c if c.isalnum() or c in "-_" else "-" for c in attestation.learner_name.lower()
    ).strip("-")
    return f"attestation-{nom or 'salarie'}-{attestation.serial}.pdf"


def render_pdf(attestation) -> bytes:
    try:
        import weasyprint
    except (ImportError, OSError) as exc:  # pragma: no cover - dépend du système
        raise PdfUnavailableError(
            "L'impression de l'attestation n'est pas disponible pour le moment. "
            "Votre réussite est enregistrée : réessayez plus tard."
        ) from exc

    return weasyprint.HTML(string=build_html(attestation)).write_pdf()
