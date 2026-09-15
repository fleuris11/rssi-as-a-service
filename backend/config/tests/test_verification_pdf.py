"""La génération PDF fonctionne-t-elle vraiment ici ?

Ces tests tentent une génération réelle (``config/verification_pdf.py``). Ils
ne listent aucun nom de bibliothèque : ils constatent le résultat. La même
vérification tourne DANS l'image construite (job CI ``container-scan``) —
c'est elle qui aurait signalé l'oubli de ``libharfbuzz-subset``.

Sous Windows, les bibliothèques GTK ne sont pas installées sur les postes de
développement : les tests de génération y sont ignorés, et le disent. Ils
tournent en CI et dans l'image, là où l'absence d'une bibliothèque compte.
"""

import sys

import pytest

from config import verification_pdf

sans_gtk = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Bibliothèques GTK absentes des postes Windows ; vérifié en CI et dans l'image.",
)


@sans_gtk
def test_un_pdf_sort_avec_des_polices_reduites_par_harfbuzz():
    constat = verification_pdf.verifier_generation_pdf()

    assert constat["octets"] > 0
    assert constat["polices_reduites_par_harfbuzz"] >= 1


@sans_gtk
def test_sans_harfbuzz_subset_la_verification_echoue(monkeypatch):
    """Simule l'image d'avant le correctif : la bibliothèque n'a pas pu être
    ouverte, WeasyPrint se rabat sur fontTools — et la vérification refuse."""
    from weasyprint.pdf import fonts

    monkeypatch.setattr(fonts, "harfbuzz_subset", None)

    with pytest.raises(verification_pdf.GenerationPdfImpossible, match="libharfbuzz-subset"):
        verification_pdf.verifier_generation_pdf()


@sans_gtk
def test_la_verification_rend_weasyprint_intact():
    """La vérification observe la réduction des polices en remplaçant deux
    méthodes internes ; elle doit les restituer, sans quoi elle altérerait
    les exports réels du même processus."""
    from weasyprint.pdf.fonts import Font

    avant = (Font._harfbuzz_subset, Font._fonttools_subset)
    verification_pdf.verifier_generation_pdf()

    assert (Font._harfbuzz_subset, Font._fonttools_subset) == avant


def test_une_bibliotheque_obligatoire_absente_est_nommee(monkeypatch):
    """Au chargement, une bibliothèque obligatoire absente fait lever OSError
    à WeasyPrint. Simulé ici sans dépendre du poste."""
    import builtins

    importer = builtins.__import__

    def import_sans_pango(nom, *args, **kwargs):
        if nom == "weasyprint" or nom.startswith("weasyprint."):
            raise OSError("cannot load library 'libpango-1.0-0'")
        return importer(nom, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_sans_pango)

    with pytest.raises(verification_pdf.GenerationPdfImpossible, match="libpango-1.0-0"):
        verification_pdf.verifier_generation_pdf()


def test_le_point_d_entree_renvoie_un_code_d_echec(monkeypatch, capsys):
    """La CI lit le code de retour : un échec doit sortir en 1, message compris."""

    def echoue():
        raise verification_pdf.GenerationPdfImpossible("bibliothèque absente")

    monkeypatch.setattr(verification_pdf, "verifier_generation_pdf", echoue)

    assert verification_pdf.main() == 1
    assert "bibliothèque absente" in capsys.readouterr().err
