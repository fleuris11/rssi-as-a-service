"""Le délai entre deux analyses passe des heures aux minutes.

L'exploitant a besoin de régler des délais courts — quelques minutes pendant
une démonstration ou un accompagnement — que l'heure ne sait pas exprimer :
en heures, le plus petit délai non nul est une heure entière.

La minute devient l'unité **canonique de bout en bout** (modèle, réglage de
plateforme, API, cache). L'heure ne subsiste qu'à la saisie, comme commodité
d'affichage. Un système qui stocke des heures ici et des minutes là finit par
diviser ou multiplier par 60 au mauvais endroit — et cette erreur-là ne se
voit pas, parce qu'elle produit un délai plausible.

Migration de DONNÉES autant que de schéma : les surcharges déjà saisies sont
converties (× 60), pas perdues ni réinterprétées. Sans cette conversion, un
client réglé à « 2 » passerait silencieusement de deux heures à deux minutes.

Réversible : la migration inverse divise par 60. Une valeur non multiple de 60
(par exemple 90 minutes) est arrondie à l'heure inférieure, ce qui est la
seule chose honnête à faire — l'heure ne peut pas représenter 90 minutes, et
arrondir au-dessus allongerait un délai commercial sans que personne ne l'ait
décidé.
"""

from django.db import migrations, models


def heures_vers_minutes(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    for tenant in Tenant.objects.exclude(scan_cooldown_minutes=None):
        # Le champ porte encore, à cet instant, la valeur en HEURES : le
        # renommage a eu lieu juste avant dans la même migration.
        tenant.scan_cooldown_minutes = tenant.scan_cooldown_minutes * 60
        tenant.save(update_fields=["scan_cooldown_minutes"])


def minutes_vers_heures(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    for tenant in Tenant.objects.exclude(scan_cooldown_minutes=None):
        tenant.scan_cooldown_minutes = tenant.scan_cooldown_minutes // 60
        tenant.save(update_fields=["scan_cooldown_minutes"])


class Migration(migrations.Migration):
    dependencies = [("tenants", "0004_tenant_scan_cooldown_hours")]

    operations = [
        migrations.RenameField(
            model_name="tenant",
            old_name="scan_cooldown_hours",
            new_name="scan_cooldown_minutes",
        ),
        # L'élargissement précède la conversion : 8760 heures tenaient dans un
        # SmallInt, 525 600 minutes n'y tiendraient pas.
        migrations.AlterField(
            model_name="tenant",
            name="scan_cooldown_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(heures_vers_minutes, minutes_vers_heures),
    ]
