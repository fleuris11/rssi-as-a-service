"""Vérifie que l'environnement sait réellement produire un PDF.

WeasyPrint ouvre ses bibliothèques système (Pango, HarfBuzz, fontconfig…) à
l'exécution : aucune n'est déclarée à pip. Une bibliothèque absente de l'image
ne casse donc ni la construction, ni le démarrage, ni les tests lancés sur un
poste qui l'a — elle casse le premier PDF demandé en production. C'est ainsi
que ``libharfbuzz-subset`` a manqué à l'image sans que rien ne le signale.

La vérification ne compare pas une liste de noms : elle produit un PDF et
constate le résultat. Elle échoue si :

- WeasyPrint ne se charge pas (bibliothèque obligatoire absente) ;
- le document ne sort pas, ou ne commence pas par ``%PDF-`` ;
- aucune police n'a été intégrée (image sans police : PDF sans texte) ;
- les polices ont été réduites par le repli fontTools au lieu de HarfBuzz —
  le signe que ``libharfbuzz-subset`` manque. WeasyPrint 70 le tolère en
  prévenant qu'elle « sera requise par les versions futures » : on refuse
  dès aujourd'hui ce que la prochaine montée de version rendra fatal.

Deux usages :

- ``pytest`` (``config/tests/test_verification_pdf.py``), sur le poste et en CI ;
- dans l'image construite, par la CI : ``python -m config.verification_pdf``.

Aucun import de Django : l'image se vérifie sans base, sans secret, sans
réglage.
"""

from __future__ import annotations

import sys

#: Du texte accentué et typographique : c'est lui qui fait intervenir la mise
#: en forme des glyphes et l'intégration d'une police réelle.
HTML_MINIMAL = (
    "<!doctype html><html lang='fr'><head><meta charset='utf-8'></head><body>"
    "<h1>Vérification de l’export</h1>"
    "<p>Évaluation : contrôle d’accès, 42 mesures — « déjà » traité.</p>"
    "</body></html>"
)


class GenerationPdfImpossible(RuntimeError):
    """L'environnement ne sait pas produire un PDF correct."""


def verifier_generation_pdf() -> dict:
    """Produit un PDF minimal et renvoie ce qui a été constaté.

    Lève ``GenerationPdfImpossible`` avec la cause, formulée pour qu'on sache
    quoi installer sans relire ce module.
    """
    try:
        import weasyprint
        from weasyprint.pdf import fonts as polices
    except (OSError, ImportError) as exc:
        raise GenerationPdfImpossible(
            f"WeasyPrint ne se charge pas — une bibliothèque système obligatoire manque : {exc}"
        ) from exc

    # On observe le chemin réellement pris pour réduire les polices. Ces deux
    # méthodes sont internes à WeasyPrint : si une version future les renomme,
    # la vérification échoue en le disant, plutôt que de passer sans rien voir.
    try:
        par_harfbuzz = polices.Font._harfbuzz_subset
        par_fonttools = polices.Font._fonttools_subset
    except AttributeError as exc:
        raise GenerationPdfImpossible(
            f"WeasyPrint {weasyprint.__version__} a changé son code de réduction des polices : "
            "revoir config/verification_pdf.py avant de conclure."
        ) from exc

    constats = {"harfbuzz": 0}

    def compter_harfbuzz(self, *args, **kwargs):
        constats["harfbuzz"] += 1
        return par_harfbuzz(self, *args, **kwargs)

    def refuser_le_repli(self, *args, **kwargs):
        raise GenerationPdfImpossible(
            "Les polices ont été réduites par le repli fontTools : libharfbuzz-subset est "
            "absente (paquet Debian libharfbuzz-subset0). WeasyPrint annonce qu'elle sera "
            "requise par ses versions futures."
        )

    polices.Font._harfbuzz_subset = compter_harfbuzz
    polices.Font._fonttools_subset = refuser_le_repli
    try:
        pdf = weasyprint.HTML(string=HTML_MINIMAL).write_pdf()
    finally:
        polices.Font._harfbuzz_subset = par_harfbuzz
        polices.Font._fonttools_subset = par_fonttools

    if not pdf or not pdf.startswith(b"%PDF-"):
        raise GenerationPdfImpossible("WeasyPrint n'a pas produit de document PDF.")
    if constats["harfbuzz"] == 0:
        raise GenerationPdfImpossible(
            "Aucune police n'a été intégrée au PDF : l'image ne contient pas de police "
            "utilisable (paquet fonts-liberation) ou fontconfig ne la trouve pas."
        )
    return {
        "weasyprint": weasyprint.__version__,
        "octets": len(pdf),
        "polices_reduites_par_harfbuzz": constats["harfbuzz"],
    }


def main() -> int:
    try:
        constat = verifier_generation_pdf()
    except GenerationPdfImpossible as exc:
        print(f"ÉCHEC — génération PDF : {exc}", file=sys.stderr)
        return 1
    print(
        f"OK — WeasyPrint {constat['weasyprint']} : PDF de {constat['octets']} octets, "
        f"{constat['polices_reduites_par_harfbuzz']} police(s) réduite(s) par HarfBuzz."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
