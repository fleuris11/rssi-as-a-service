"""F2 : le studio de formation entre au catalogue.

Ajouté à « Pilotage » et « Souverain », comme la formation elle-même. L'offre
« Veille » ne le reçoit pas : écrire ses propres cours suppose déjà de former
ses salariés, et la formation n'y figure pas.

Pas de quota, pour la même raison qu'en F1 : écrire un cours ne consomme
aucune ressource rare. La voix de synthèse est celle du navigateur de
l'apprenant (ADR-040), donc rien n'est généré ni stocké côté serveur.
"""

from django.db import migrations

CLE = "training_studio"
OFFRES = ("pilotage", "souverain")


def ouvrir(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for code in OFFRES:
        plan = Plan.objects.filter(code=code).first()
        if plan is None:
            continue
        if CLE not in plan.features:
            plan.features = [*plan.features, CLE]
            plan.save(update_fields=["features"])


def refermer(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for code in OFFRES:
        plan = Plan.objects.filter(code=code).first()
        if plan is None:
            continue
        plan.features = [cle for cle in plan.features if cle != CLE]
        plan.save(update_fields=["features"])


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0008_offres_formation"),
    ]

    operations = [migrations.RunPython(ouvrir, refermer)]
