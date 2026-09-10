"""Export en format éditable (.docx).

Pourquoi pas le Markdown, qui existait déjà : parce qu'une PME n'édite pas du
Markdown. Le fichier `.md` reste exporté — c'est le format qui garantit au
client de récupérer son contenu quoi qu'il arrive — mais « éditable », pour le
dirigeant qui doit ajouter le nom de son référent sécurité et signer, veut dire
« qui s'ouvre dans Word ou LibreOffice ».

Le rendu est volontairement sobre : titres, paragraphes, listes, tableaux et
citations. On ne cherche pas à reproduire une maquette, on cherche un document
qu'on peut modifier sans se battre avec la mise en forme.

``python-docx`` est une dépendance pure Python, sans bibliothèque système —
contrairement à WeasyPrint (ADR-012), dont l'installation impose Pango et
Cairo au Dockerfile comme à la CI. C'est ce qui permet à cet export de
fonctionner partout, y compris là où le PDF échoue.
"""

import re

# Un tableau Markdown : la ligne de séparation « |---|---| » est ce qui
# distingue un vrai tableau d'une suite de lignes commençant par une barre.
_SEPARATEUR_TABLEAU = re.compile(r"^\|[\s:|-]+\|$")
#: Gras et italique, retirés du texte des cellules et des puces : Word affiche
#: sinon les astérisques tels quels.
_EMPHASE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`")


def _texte_simple(ligne: str) -> str:
    return _EMPHASE.sub(lambda m: m.group(1) or m.group(2) or m.group(3), ligne).strip()


def _cellules(ligne: str) -> list[str]:
    return [_texte_simple(cellule) for cellule in ligne.strip().strip("|").split("|")]


def render_docx(document) -> bytes:
    """Le document, en .docx. Prend le Markdown tel qu'il est stocké : ce que
    le client a relu et modifié dans l'éditeur est exactement ce qu'il
    exporte."""
    import io

    from docx import Document as DocxDocument
    from docx.shared import Pt

    docx = DocxDocument()
    style = docx.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    lignes = document.content_markdown.splitlines()
    index = 0
    while index < len(lignes):
        ligne = lignes[index]
        nue = ligne.strip()

        if not nue:
            index += 1
            continue

        # Tableau : la ligne courante et la suivante décrivent un en-tête.
        if (
            nue.startswith("|")
            and index + 1 < len(lignes)
            and _SEPARATEUR_TABLEAU.match(lignes[index + 1].strip())
        ):
            entetes = _cellules(nue)
            index += 2
            corps = []
            while index < len(lignes) and lignes[index].strip().startswith("|"):
                corps.append(_cellules(lignes[index].strip()))
                index += 1
            table = docx.add_table(rows=1, cols=len(entetes))
            table.style = "Table Grid"
            for colonne, entete in enumerate(entetes):
                table.rows[0].cells[colonne].text = entete
            for ligne_corps in corps:
                cellules = table.add_row().cells
                for colonne, valeur in enumerate(ligne_corps[: len(entetes)]):
                    cellules[colonne].text = valeur
            docx.add_paragraph()
            continue

        if nue.startswith("#"):
            niveau = len(nue) - len(nue.lstrip("#"))
            docx.add_heading(_texte_simple(nue.lstrip("#")), level=min(niveau, 4))
        elif nue.startswith(("- ", "* ")):
            docx.add_paragraph(_texte_simple(nue[2:]), style="List Bullet")
        elif re.match(r"^\d+\.\s", nue):
            docx.add_paragraph(_texte_simple(re.sub(r"^\d+\.\s", "", nue)), style="List Number")
        elif nue.startswith("> "):
            paragraphe = docx.add_paragraph(_texte_simple(nue[2:]))
            paragraphe.style = (
                docx.styles["Quote"] if "Quote" in [s.name for s in docx.styles] else style
            )
        elif nue.startswith("---"):
            docx.add_paragraph()
        else:
            docx.add_paragraph(_texte_simple(nue))
        index += 1

    tampon = io.BytesIO()
    docx.save(tampon)
    return tampon.getvalue()
