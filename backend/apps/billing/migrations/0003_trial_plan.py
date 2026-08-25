"""Offre d'essai dédiée (ADR-024).

Contexte : l'essai démarrait sur une offre du catalogue. Aucune ne convient.

- « Pilotage » engage 3 des 15 emplacements de surveillance de la licence
  plateforme (ADR-013) : cinq essais simultanés au maximum, zéro une fois le
  jeu de démonstration chargé.
- « Veille » n'engage qu'un emplacement, mais ne contient pas le diagnostic
  ANSSI — c'est-à-dire l'entrée du produit. Un prospect s'inscrivait donc pour
  ne pas pouvoir faire la première chose qu'on lui a promise.

La ressource rare, ce sont les emplacements de surveillance ; les
fonctionnalités, elles, ne coûtent rien. Les deux contraintes se résolvent
donc séparément : un emplacement, et les fonctionnalités qui donnent envie de
payer.
"""

from decimal import Decimal

from django.db import migrations, models

CODE = "essai"

FONCTIONNALITES = [
    "realtime_monitoring",
    "assistant",
    "exposure_synthesis",
    "pdf_export",
    "reuse_correlation",
    "anssi_assessment",
    "charter_generation",
    # « secret_reveal » volontairement absent : afficher en clair un mot de
    # passe réellement fuité est l'action la plus sensible du produit
    # (ADR-014). Elle reste derrière l'offre payante — le refus est explicite
    # et nomme l'offre qui la débloque, ce qui en fait un argument de vente
    # plutôt qu'une porte fermée sans explication.
]


def creer_offre_essai(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Plan.objects.update_or_create(
        code=CODE,
        defaults={
            "name": "Essai",
            "tagline": "Quatorze jours pour voir ce que ça donne chez vous.",
            "description": (
                "L'essai donne accès au diagnostic de maturité, au plan d'action, "
                "à la génération documentaire et à la surveillance d'un actif. "
                "Il n'est pas vendu : il est attribué à l'ouverture d'un compte."
            ),
            "price_monthly": Decimal("0"),
            "price_yearly": Decimal("0"),
            "is_quote_only": False,
            "status": "internal",
            "display_order": 0,
            "is_highlighted": False,
            "monitored_assets": 1,
            "monthly_scans": 20,
            "max_users": 3,
            "features": FONCTIONNALITES,
        },
    )


def supprimer_offre_essai(apps, schema_editor):
    # Uniquement si personne n'y est abonné : effacer une offre sous les pieds
    # d'un abonnement en cours transformerait un retour en arrière technique en
    # perte de données.
    Plan = apps.get_model("billing", "Plan")
    Subscription = apps.get_model("billing", "Subscription")
    if not Subscription.objects.filter(plan__code=CODE).exists():
        Plan.objects.filter(code=CODE).delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_initial_plans")]

    operations = [
        migrations.AlterField(
            model_name="plan",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Brouillon"),
                    ("published", "Publiée"),
                    ("retired", "Retirée"),
                    ("internal", "Interne (non affichée)"),
                ],
                default="draft",
                max_length=10,
            ),
        ),
        migrations.RunPython(creer_offre_essai, supprimer_offre_essai),
    ]
