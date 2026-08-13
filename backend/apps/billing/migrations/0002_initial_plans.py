"""Catalogue initial (ADR-019).

Migration de **données** et non de configuration : les trois offres doivent
exister dès le premier démarrage pour qu'un essai puisse s'ouvrir et que la
vitrine affiche des tarifs. Elles restent modifiables ensuite depuis le
back-office, sans redéploiement — c'est tout l'objet du modèle ``Plan``.

Réversible : la migration inverse supprime uniquement les trois codes créés
ici, jamais les offres saisies depuis l'administration.
"""

from decimal import Decimal

from django.db import migrations

# Tarif annuel = 10 mois payés pour 12 (deux mois offerts).
YEARLY_MONTHS = 10

PLANS = [
    {
        "code": "veille",
        "name": "Veille",
        "tagline": "Savoir ce qui circule sur votre entreprise.",
        "description": (
            "L'essentiel : la surveillance de vos identifiants exposés, les alertes "
            "expliquées en langage clair, et le suivi de votre exposition dans le temps."
        ),
        "price_monthly": Decimal("89"),
        "display_order": 10,
        "is_highlighted": False,
        "monitored_assets": 1,
        "monthly_scans": 20,
        "max_users": 3,
        "features": ["realtime_monitoring"],
    },
    {
        "code": "pilotage",
        "name": "Pilotage",
        "tagline": "Comprendre, prioriser et agir.",
        "description": (
            "Toute la surveillance, plus les outils pour décider : corrélation de "
            "réutilisation, synthèse d'exposition, diagnostic de maturité et génération "
            "documentaire."
        ),
        "price_monthly": Decimal("249"),
        "display_order": 20,
        "is_highlighted": True,
        "monitored_assets": 3,
        "monthly_scans": 60,
        "max_users": 10,
        "features": [
            "realtime_monitoring",
            "assistant",
            "exposure_synthesis",
            "pdf_export",
            "reuse_correlation",
            "secret_reveal",
            "anssi_assessment",
            "charter_generation",
        ],
    },
    {
        "code": "souverain",
        "name": "Souverain",
        "tagline": "Sur mesure, pour les structures aux contraintes particulières.",
        "description": (
            "Quotas paramétrables, utilisateurs illimités, historique étendu et "
            "accompagnement à la mise en conformité."
        ),
        "price_monthly": Decimal("0"),
        "is_quote_only": True,
        "display_order": 30,
        "is_highlighted": False,
        "monitored_assets": 5,
        "monthly_scans": 120,
        "max_users": 0,  # 0 = illimité
        "features": [
            "realtime_monitoring",
            "assistant",
            "exposure_synthesis",
            "pdf_export",
            "reuse_correlation",
            "secret_reveal",
            "anssi_assessment",
            "charter_generation",
            "extended_history",
        ],
    },
]


def create_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for spec in PLANS:
        spec = dict(spec)
        monthly = spec["price_monthly"]
        spec["price_yearly"] = monthly * YEARLY_MONTHS
        spec["status"] = "published"
        Plan.objects.update_or_create(code=spec.pop("code"), defaults=spec)


def remove_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Plan.objects.filter(code__in=[spec["code"] for spec in PLANS]).delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]
    operations = [migrations.RunPython(create_plans, remove_plans)]
