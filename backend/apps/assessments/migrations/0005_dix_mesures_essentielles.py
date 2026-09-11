"""« Les 10 mesures essentielles » : par ou commencer (B19).

Quarante-deux questions decouragent. Un dirigeant de TPE qui ouvre son espace
et voit un questionnaire de 42 mesures le referme — et ne revient pas. Dix
mesures, il les fait.

**Ce n'est pas un referentiel de plus, c'est une COMPOSITION du referentiel
ANSSI existant.** Rien n'est reecrit, rien n'est duplique : les memes mesures,
les memes enonces, le meme score. Un client qui commence par les dix et
poursuit ensuite sur les quarante-deux garde ses reponses.

## Le choix des dix, et pourquoi celles-la

Toutes portent un **impact fort** au sens du registre produit, toutes sont de
niveau **standard** (donc attendues de toute organisation, pas seulement des
plus matures), et la majorite demande un **effort faible**. Le critere n'est
pas « les plus connues » mais « le meilleur rapport entre ce que ca protege et
ce que ca coute a mettre en place ».

Deux mesures a effort moyen y figurent quand meme — la messagerie (24) et les
sauvegardes (37) — parce qu'aucune selection honnete de dix mesures pour une
TPE ne peut les omettre : ce sont les deux qui font la difference entre un
incident et une faillite.

Les quatre mesures a effort eleve (19, 23, 38, 41) sont ecartees malgre leur
impact : segmenter un reseau ou mener une analyse de risques formelle n'est
pas un point de depart, c'est une suite.

## Pourquoi une migration et non un fichier de donnees

La composition vit en base, comme toute ``MeasureSubset`` : l'exploitant doit
pouvoir la modifier depuis la console sans redeploiement. La migration ne fait
que la POSER, et ne la reecrit jamais si elle existe deja.
"""

from django.db import migrations

#: Les codes ANSSI retenus. Ecrits ici et non calcules : une selection
#: editoriale se relit, et un calcul (« impact fort et effort faible ») aurait
#: change silencieusement au premier ajustement du registre produit.
CODES_ESSENTIELS = ["2", "5", "6", "10", "12", "14", "24", "34", "37", "40"]

SLUG = "anssi-10-essentielles"
REFERENTIEL = "anssi-hygiene-informatique"


def poser(apps, schema_editor):
    Referential = apps.get_model("assessments", "Referential")
    Measure = apps.get_model("assessments", "Measure")
    MeasureSubset = apps.get_model("assessments", "MeasureSubset")
    SubsetMeasure = apps.get_model("assessments", "SubsetMeasure")

    referentiel = Referential.objects.filter(slug=REFERENTIEL).first()
    if referentiel is None:
        # Base neuve ou l'ANSSI n'est pas encore chargee : la composition sera
        # posee au prochain passage. On ne cree PAS un sous-ensemble vide, qui
        # afficherait un questionnaire sans question.
        return

    mesures = {m.code: m for m in Measure.objects.filter(referential=referentiel)}
    retenues = [mesures[code] for code in CODES_ESSENTIELS if code in mesures]
    if len(retenues) < len(CODES_ESSENTIELS):
        # Le referentiel en base ne porte pas les codes attendus : on
        # s'abstient plutot que de livrer une selection amputee qu'on
        # presenterait comme « les dix essentielles ».
        return

    subset, _ = MeasureSubset.objects.get_or_create(
        referential=referentiel,
        slug=SLUG,
        defaults={
            "name": "Les 10 mesures essentielles",
            "description": (
                "Par ou commencer. Dix mesures a fort impact, realisables sans "
                "equipe dediee. Vous pourrez passer au questionnaire complet "
                "ensuite : vos reponses sont conservees."
            ),
            "owner_tenant": None,
            "is_active": True,
        },
    )
    if SubsetMeasure.objects.filter(subset=subset).exists():
        # Deja posee, et peut-etre ajustee depuis la console : on n'y touche
        # pas.
        return
    SubsetMeasure.objects.bulk_create(
        [
            SubsetMeasure(subset=subset, measure=mesure, order=position)
            for position, mesure in enumerate(retenues, start=1)
        ]
    )


def retirer(apps, schema_editor):
    """Retour arriere : on retire la composition, jamais les mesures."""
    MeasureSubset = apps.get_model("assessments", "MeasureSubset")
    MeasureSubset.objects.filter(slug=SLUG, owner_tenant__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0004_veille_reglementaire"),
    ]

    operations = [migrations.RunPython(poser, retirer)]
