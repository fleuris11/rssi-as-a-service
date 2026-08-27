"""Retrait de la clé « historique étendu » du catalogue (ADR-025).

La clé promettait « l'historique complet au-delà de la période standard ».
Il n'y a aucune période standard : pas de rétention par client, pas de purge
de l'historique métier, pas de fenêtre paramétrable. Tout le monde a déjà
l'historique complet, pour toujours — « étendu » ne se distingue de rien.

Le retrait du registre suffit à la neutraliser (``features.sanitize`` ignore
les clés inconnues). Cette migration nettoie quand même la donnée : une
lecture directe de la table ne doit pas laisser croire que la fonctionnalité
existe, et le jour où la clé reviendrait avec un vrai référent, elle ne doit
pas se retrouver activée par un reliquat que personne n'a décidé.
"""

from django.db import migrations

CLE = "extended_history"

ANCIENNE_DESCRIPTION = (
    "Quotas paramétrables, utilisateurs illimités, historique étendu et "
    "accompagnement à la mise en conformité."
)
NOUVELLE_DESCRIPTION = (
    "Quotas paramétrables, utilisateurs illimités et accompagnement à la mise "
    "en conformité."
)


def retirer(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Subscription = apps.get_model("billing", "Subscription")

    for plan in Plan.objects.all():
        if CLE in (plan.features or []):
            plan.features = [k for k in plan.features if k != CLE]
            if plan.description == ANCIENNE_DESCRIPTION:
                plan.description = NOUVELLE_DESCRIPTION
                plan.save(update_fields=["features", "description"])
            else:
                # Description retouchée depuis la console : on ne l'écrase pas.
                # Retirer la clé sans toucher au texte laisse un décalage
                # visible, ce qui vaut mieux qu'un texte réécrit sous les pieds
                # de l'exploitant.
                plan.save(update_fields=["features"])

    # Les surcharges par abonnement portent la même clé (offre négociée).
    for subscription in Subscription.objects.exclude(override_features=None):
        if CLE in (subscription.override_features or []):
            subscription.override_features = [
                k for k in subscription.override_features if k != CLE
            ]
            subscription.save(update_fields=["override_features"])


def remettre(apps, schema_editor):
    """Retour arrière volontairement partiel.

    On ne réactive la clé que là où elle était : « Souverain ». La rétablir
    partout serait inventer un état qui n'a jamais existé. Les surcharges
    d'abonnement, elles, ne sont pas restaurées — on ne sait pas lesquelles la
    portaient, et l'historique de ces surcharges n'est pas tracé.
    """
    Plan = apps.get_model("billing", "Plan")
    souverain = Plan.objects.filter(code="souverain").first()
    if souverain and CLE not in (souverain.features or []):
        souverain.features = list(souverain.features or []) + [CLE]
        if souverain.description == NOUVELLE_DESCRIPTION:
            souverain.description = ANCIENNE_DESCRIPTION
        souverain.save(update_fields=["features", "description"])


class Migration(migrations.Migration):
    dependencies = [("billing", "0004_switch_trials_to_dedicated_plan")]

    operations = [migrations.RunPython(retirer, remettre)]
