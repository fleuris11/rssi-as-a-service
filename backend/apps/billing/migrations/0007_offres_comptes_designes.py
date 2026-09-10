"""V2-6 : la surveillance de comptes désignés entre au catalogue.

Ajoutée aux offres « Pilotage » et « Souverain », pas à « Veille » — comme les
autres fonctionnalités payantes. L'invariant que tient
``test_pilotage_donne_les_huit_fonctionnalites_du_registre`` reste vrai :
Pilotage comprend tout ce que le registre déclare.

Les deux quotas sont posés ici plutôt que laissés à leur défaut (0) : une offre
qui vend la fonctionnalité sans donner d'emplacement afficherait un écran qui
refuse tout, ce qui est pire que de ne pas la vendre.

``update_or_create`` sur les seules colonnes concernées : une offre dont
l'exploitant a modifié le prix ou le libellé depuis la console (ADR-019) ne
doit pas être réécrite par une migration.
"""

from django.db import migrations

CLE = "watched_accounts"

QUOTAS = {
    # code de l'offre : (comptes déclarables, analyses par mois)
    "pilotage": (3, 10),
    "souverain": (10, 40),
}


def ouvrir(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for code, (comptes, analyses) in QUOTAS.items():
        plan = Plan.objects.filter(code=code).first()
        if plan is None:
            # Catalogue modifié depuis la console : on ne recrée pas une offre
            # que quelqu'un a délibérément retirée.
            continue
        if CLE not in plan.features:
            plan.features = [*plan.features, CLE]
        plan.watched_accounts = comptes
        plan.monthly_watched_account_scans = analyses
        plan.save(update_fields=["features", "watched_accounts", "monthly_watched_account_scans"])


def refermer(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for code in QUOTAS:
        plan = Plan.objects.filter(code=code).first()
        if plan is None:
            continue
        plan.features = [cle for cle in plan.features if cle != CLE]
        plan.watched_accounts = 0
        plan.monthly_watched_account_scans = 0
        plan.save(update_fields=["features", "watched_accounts", "monthly_watched_account_scans"])


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0006_comptes_designes"),
    ]

    operations = [migrations.RunPython(ouvrir, refermer)]
