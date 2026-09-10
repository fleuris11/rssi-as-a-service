"""Installe la liste de sources de depart (V2-7, cadrage).

Les sources vivent en base et non en dur : l'exploitant doit pouvoir en
ajouter une, corriger une adresse ou en desactiver une sans redeploiement.
Cette migration ne fait que POSER le point de depart.

Idempotente et non destructrice : une source deja presente n'est pas
reecrite. Une adresse corrigee depuis la console ne doit pas etre defaite par
un redeploiement.
"""

from django.db import migrations

from apps.regulatory_watch.sources import seed_sources


def installer(apps, schema_editor):
    seed_sources(model=apps.get_model("regulatory_watch", "WatchSource"))


def retirer(apps, schema_editor):
    from apps.regulatory_watch.sources import SOURCES

    WatchSource = apps.get_model("regulatory_watch", "WatchSource")
    # Seules les sources de depart, et seulement si elles n'ont rien collecte :
    # une source qui porte des suggestions deja triees par un humain ne se
    # supprime pas au retour arriere d'une migration.
    WatchSource.objects.filter(
        slug__in=[spec["slug"] for spec in SOURCES], updates__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("regulatory_watch", "0001_veille_reglementaire"),
    ]

    operations = [migrations.RunPython(installer, retirer)]
