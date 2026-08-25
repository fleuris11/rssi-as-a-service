"""Bascule des essais déjà ouverts vers l'offre d'essai dédiée (ADR-024).

La migration 0003 crée l'offre `essai` et la désigne comme offre d'essai par
défaut. Cela ne vaut que pour les inscriptions **à venir** : un essai déjà
ouvert reste sur l'offre du catalogue qui le portait.

Ce n'est visible aujourd'hui par personne, puisque six des neuf gardes de
fonctionnalité ne sont appliquées nulle part. Le jour où elles le seront, ces
essais-là perdraient le diagnostic, l'assistant, l'export PDF, la corrélation
et la génération de charte, sans qu'une ligne de code les concernant ait
changé. C'est la panne qu'ADR-024 annonce, et 0003 seule ne la couvre pas.

La règle vit dans ``apps.billing.trial_migration`` : une règle écrite ici ne
serait testable qu'en rejouant l'historique des migrations.
"""

from django.conf import settings
from django.db import migrations

from apps.billing.trial_migration import CODE_ESSAI_PAR_DEFAUT, basculer_essais


def _code_essai() -> str:
    return getattr(settings, "BILLING_DEFAULT_TRIAL_PLAN_CODE", "") or CODE_ESSAI_PAR_DEFAUT


def basculer(apps, schema_editor):
    rapport = basculer_essais(
        apps.get_model("billing", "Plan"),
        apps.get_model("billing", "Subscription"),
        apps.get_model("billing", "SubscriptionEvent"),
        code_essai=_code_essai(),
    )
    # `print` plutôt que `logging` : la sortie attendue est celle de
    # `manage.py migrate`, lue par l'exploitant pendant le déploiement. Un log
    # partirait dans un fichier que personne ne regarde à cet instant.
    for ligne in rapport.lignes():
        print(ligne)


def annuler(apps, schema_editor):
    """Aucune restauration automatique, et c'est délibéré.

    L'inverse — « remettre chaque essai sur l'offre qu'il avait » — demanderait
    de savoir laquelle, or plusieurs offres sources sont possibles. La reprise
    se lit dans ``SubscriptionEvent`` (``from_plan`` / ``to_plan``), qui trace
    chaque bascule nommément ; la refaire à l'envers est une décision
    d'exploitant, pas un effet de bord d'un retour arrière technique.

    Un `noop` plutôt qu'un `RunPython.noop` nu, pour porter cette explication.
    """


class Migration(migrations.Migration):
    dependencies = [("billing", "0003_trial_plan")]

    operations = [migrations.RunPython(basculer, annuler)]
