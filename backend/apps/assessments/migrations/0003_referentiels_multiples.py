"""V2-4 (ADR-029) : le diagnostic cesse de supposer un référentiel unique.

Migration écrite à la main plutôt qu'auto-générée, parce qu'elle porte des
données de production : des diagnostics ANSSI en cours et terminés, avec leurs
réponses et leurs plans d'action. Trois précautions y sont visibles :

1. **expand/contract** sur ``Measure.code`` et ``Measure.referential`` : on
   ajoute le champ permissif, on le remplit, puis on le resserre. Jamais un
   ``NOT NULL`` posé sur une table pleine.
2. **aucune suppression.** ``number`` perd son unicité globale mais reste là,
   avec sa valeur. ``level`` s'élargit sans se vider. Un retour arrière ne
   perdrait aucune donnée métier.
3. **les attributions sont rétro-créées.** Avant cette migration, tout client
   voyait le référentiel actif ; après, il ne voit que ceux qui lui sont
   attribués. Sans la rétro-création, tous les clients existants perdraient
   leur diagnostic au déploiement — y compris ceux qui en ont un en cours.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Poids historiques des niveaux ANSSI. Recopiés ici plutôt qu'importés de
# services.py : une migration doit continuer de rejouer à l'identique même si
# le code applicatif change de table de poids demain.
POIDS_PAR_NIVEAU = {"standard": 1.0, "renforce": 0.5}


def remplir_code_referentiel_et_poids(apps, schema_editor):
    """Le code d'une mesure, son référentiel, son poids — déduits de
    l'existant, sans rien inventer."""
    Measure = apps.get_model("assessments", "Measure")
    for measure in Measure.objects.select_related("domain").iterator():
        measure.code = str(measure.number) if measure.number is not None else str(measure.pk)
        measure.referential_id = measure.domain.referential_id
        measure.weight = POIDS_PAR_NIVEAU.get(measure.level, 1.0)
        measure.save(update_fields=["code", "referential", "weight"])


def annuler_code_referentiel_et_poids(apps, schema_editor):
    # Rien à défaire : les trois champs disparaissent avec le retour arrière
    # du schéma, et aucune donnée d'origine n'a été modifiée.
    pass


def retro_creer_les_attributions(apps, schema_editor):
    """Chaque client existant garde EXACTEMENT ce qu'il voyait hier.

    Hier : le référentiel actif était visible de tous. Aujourd'hui : on ne
    voit que ce qui est attribué. On attribue donc à chaque client tous les
    référentiels actifs, plus tout référentiel sur lequel il a déjà produit
    une évaluation — celui-là même s'il n'est plus actif, sinon un diagnostic
    en cours deviendrait irremplissable du jour au lendemain.
    """
    Tenant = apps.get_model("tenants", "Tenant")
    Referential = apps.get_model("assessments", "Referential")
    Assessment = apps.get_model("assessments", "Assessment")
    ReferentialAssignment = apps.get_model("assessments", "ReferentialAssignment")

    actifs = list(Referential.objects.filter(is_active=True).values_list("id", flat=True))

    a_creer = []
    for tenant in Tenant.objects.all().iterator():
        evalues = set(
            Assessment.objects.filter(tenant_id=tenant.id).values_list(
                "referential_id", flat=True
            )
        )
        for referential_id in set(actifs) | evalues:
            a_creer.append(
                ReferentialAssignment(
                    tenant_id=tenant.id,
                    referential_id=referential_id,
                    note="Attribution rétro-créée à la migration V2-4 (ADR-029).",
                )
            )
    ReferentialAssignment.objects.bulk_create(a_creer, ignore_conflicts=True)


def supprimer_les_attributions(apps, schema_editor):
    ReferentialAssignment = apps.get_model("assessments", "ReferentialAssignment")
    ReferentialAssignment.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0002_remove_measure_code_measure_effort_impact_disclaimer_and_more"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # --- Le catalogue s'enrichit -------------------------------------
        migrations.AddField(
            model_name="referential",
            name="publisher",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="referential",
            name="kind",
            field=models.CharField(
                choices=[
                    ("open", "Libre de droits"),
                    ("licensed", "Soumis à droits (importé par l'exploitant)"),
                    ("custom", "Propre à un client"),
                ],
                default="open",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="referential",
            name="source_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="referential",
            name="licence_notice",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="referential",
            name="owner_tenant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="tenants.tenant",
            ),
        ),
        # --- Une mesure cesse d'être « un entier unique » (expand) --------
        migrations.AddField(
            model_name="measure",
            name="code",
            field=models.CharField(default="", max_length=40),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="measure",
            name="referential",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="measures",
                to="assessments.referential",
            ),
        ),
        migrations.AddField(
            model_name="measure",
            name="weight",
            field=models.FloatField(default=1.0),
        ),
        migrations.RunPython(
            remplir_code_referentiel_et_poids, annuler_code_referentiel_et_poids
        ),
        # --- ... puis on resserre (contract) ------------------------------
        migrations.AlterField(
            model_name="measure",
            name="referential",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="measures",
                to="assessments.referential",
            ),
        ),
        migrations.AlterField(
            model_name="measure",
            name="number",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="measure",
            name="level",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddConstraint(
            model_name="measure",
            constraint=models.UniqueConstraint(
                fields=("referential", "code"), name="unique_measure_code_per_referential"
            ),
        ),
        # --- Sous-ensembles ------------------------------------------------
        migrations.CreateModel(
            name="MeasureSubset",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("slug", models.SlugField(max_length=100)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "owner_tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="tenants.tenant",
                    ),
                ),
                (
                    "referential",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subsets",
                        to="assessments.referential",
                    ),
                ),
            ],
            options={"ordering": ["referential_id", "name"]},
        ),
        migrations.CreateModel(
            name="SubsetMeasure",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("order", models.PositiveSmallIntegerField(default=0)),
                (
                    "measure",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="assessments.measure",
                    ),
                ),
                (
                    "subset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="assessments.measuresubset",
                    ),
                ),
            ],
            options={"ordering": ["subset_id", "order"]},
        ),
        migrations.AddField(
            model_name="assessment",
            name="subset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="assessments.measuresubset",
            ),
        ),
        # --- Surcharges d'énoncé -------------------------------------------
        migrations.CreateModel(
            name="MeasureStatementOverride",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("plain_language", models.TextField(blank=True)),
                ("context_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "measure",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="overrides",
                        to="assessments.measure",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={"ordering": ["measure__order"]},
        ),
        # --- Attributions ---------------------------------------------------
        migrations.CreateModel(
            name="ReferentialAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.CharField(blank=True, max_length=300)),
                (
                    "granted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "referential",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="assessments.referential",
                    ),
                ),
                (
                    "revoked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={"ordering": ["tenant_id", "referential__name"]},
        ),
        migrations.AddConstraint(
            model_name="measuresubset",
            constraint=models.UniqueConstraint(
                fields=("referential", "slug"), name="unique_subset_slug"
            ),
        ),
        migrations.AddConstraint(
            model_name="subsetmeasure",
            constraint=models.UniqueConstraint(
                fields=("subset", "measure"), name="unique_subset_measure"
            ),
        ),
        migrations.AddConstraint(
            model_name="measurestatementoverride",
            constraint=models.UniqueConstraint(
                fields=("tenant", "measure"), name="unique_override_per_measure"
            ),
        ),
        migrations.AddConstraint(
            model_name="referentialassignment",
            constraint=models.UniqueConstraint(
                fields=("tenant", "referential"), name="unique_assignment_per_referential"
            ),
        ),
        # --- Personne ne perd son diagnostic au déploiement ------------------
        migrations.RunPython(retro_creer_les_attributions, supprimer_les_attributions),
    ]
