"""F1 : la formation des salariés entre au catalogue.

Ajoutée à « Pilotage » et « Souverain », pas à « Veille » — comme les autres
fonctionnalités payantes. C'est ce qui maintient vrai l'invariant que tient
``test_pilotage_donne_toutes_les_fonctionnalites_du_registre`` : Pilotage
comprend tout ce que le registre déclare.

Pas de quota associé, et c'est un choix. Les autres fonctionnalités à forte
consommation en ont un parce qu'elles prennent sur une ressource rare : un
emplacement de surveillance pris sur un pool de quinze, une analyse qui appelle
un service payant. Suivre un cours ne consomme rien de rare — pas d'appel
externe, pas d'IA, pas de stockage (l'attestation est réimprimée à la demande).
Poser un compteur ici aurait créé une rareté artificielle, et un client qui
compte ses salariés avant de les former forme moins de salariés.

``update_or_create`` sur la seule colonne concernée : une offre dont
l'exploitant a modifié le prix ou le libellé depuis la console (ADR-019) ne
doit pas être réécrite par une migration.
"""

from django.db import migrations

CLE = "training"
OFFRES = ("pilotage", "souverain")


def ouvrir(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for code in OFFRES:
        plan = Plan.objects.filter(code=code).first()
        if plan is None:
            # Catalogue modifié depuis la console : on ne recrée pas une offre
            # que quelqu'un a délibérément retirée.
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
        ("billing", "0007_offres_comptes_designes"),
    ]

    operations = [migrations.RunPython(ouvrir, refermer)]
