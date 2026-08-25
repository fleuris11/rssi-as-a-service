"""Rejoue la bascule des essais vers l'offre d'essai dédiée (ADR-024).

La migration 0004 fait ce travail au déploiement. Cette commande existe pour
deux besoins que la migration ne couvre pas :

- **vérifier** sur un environnement réel — la sortie de `migrate` défile
  pendant un déploiement et n'est pas relue ;
- **rattraper** un essai ouvert entre le moment où la migration s'est
  appliquée et celui où le catalogue a été corrigé, cas qui ne peut pas
  déclencher une seconde exécution de la migration.

Sans risque à rejouer : la règle est idempotente et une seconde passe ne
trouve plus rien.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.billing.models import Plan, Subscription, SubscriptionEvent
from apps.billing.trial_migration import CODE_ESSAI_PAR_DEFAUT, basculer_essais


class Command(BaseCommand):
    help = "Bascule les essais en cours vers l'offre d'essai dédiée (ADR-024)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Montre ce qui serait basculé, sans rien écrire. À utiliser avant "
                "toute exécution sur une base de production."
            ),
        )

    def handle(self, *args, **options):
        code = getattr(settings, "BILLING_DEFAULT_TRIAL_PLAN_CODE", "") or CODE_ESSAI_PAR_DEFAUT

        if options["dry_run"]:
            # Une transaction annulée plutôt qu'un second chemin de code qui
            # « simulerait » : deux chemins finiraient par diverger, et c'est
            # justement le chemin non simulé qu'on cherche à éprouver.
            from django.db import transaction

            with transaction.atomic():
                rapport = basculer_essais(Plan, Subscription, SubscriptionEvent, code_essai=code)
                lignes = rapport.lignes()
                transaction.set_rollback(True)
            self.stdout.write("(simulation — aucune écriture conservée)")
        else:
            rapport = basculer_essais(Plan, Subscription, SubscriptionEvent, code_essai=code)
            lignes = rapport.lignes()

        for ligne in lignes:
            self.stdout.write(ligne)

        if rapport.empechement:
            self.stdout.write(self.style.WARNING("Rien n'a été modifié."))
        elif rapport.a_agi and options["dry_run"]:
            # Ne jamais annoncer « terminée » après une simulation : c'est la
            # phrase que l'exploitant retient, et il repartirait convaincu
            # d'avoir fait le travail.
            self.stdout.write(
                self.style.WARNING("Simulation seulement — relancer sans --dry-run pour appliquer.")
            )
        elif rapport.a_agi:
            self.stdout.write(self.style.SUCCESS("Bascule terminée."))
