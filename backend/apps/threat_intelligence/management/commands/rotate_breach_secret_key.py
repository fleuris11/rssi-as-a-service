"""Re-chiffre les secrets de fuite avec la clé courante (Phase 8C, ADR-014).

Procédure sans coupure (détaillée dans le README de l'app) :
1. générer une nouvelle clé Fernet ;
2. la placer **en tête** de ``BREACH_SECRET_ENCRYPTION_KEYS``, en gardant
   l'ancienne derrière — à ce stade tout continue de fonctionner : la
   nouvelle chiffre, l'ancienne déchiffre encore l'existant ;
3. lancer cette commande, qui re-chiffre les secrets existants ;
4. retirer l'ancienne clé de la liste.

La commande est idempotente (relancer ne fait que re-chiffrer avec la même
clé courante, sans perte) et sûre à interrompre : chaque secret est traité
et enregistré individuellement, donc une exécution coupée à mi-parcours
laisse une base cohérente — le reste sera repris au prochain passage, les
deux clés étant encore acceptées en déchiffrement.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.threat_intelligence import services
from apps.threat_intelligence.models import BreachFinding


class Command(BaseCommand):
    help = "Re-chiffre les secrets de fuite existants avec la clé de chiffrement courante."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="Nombre de secrets traités par lot (défaut : 200).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compte ce qui serait re-chiffré, sans rien écrire.",
        )

    def handle(self, *, batch_size, dry_run, **options):
        if not services._encryption_keys():
            raise CommandError(
                "Aucune clé de chiffrement configurée "
                "(BREACH_SECRET_ENCRYPTION_KEYS ou BREACH_SECRET_ENCRYPTION_KEY)."
            )

        queryset = BreachFinding.all_objects.filter(has_secret=True).exclude(secret_encrypted=b"")
        total = queryset.count()

        if dry_run:
            self.stdout.write(f"{total} secret(s) seraient re-chiffrés (essai à blanc).")
            return

        rotated = 0
        failed = 0
        for finding in queryset.iterator(chunk_size=batch_size):
            try:
                new_blob = services.rotate_secret_ciphertext(bytes(finding.secret_encrypted))
            except services.ThreatIntelligenceError:
                # Un secret illisible avec AUCUNE des clés configurées : on ne
                # l'efface surtout pas (ce serait détruire une donnée qu'une
                # clé oubliée pourrait encore ouvrir) et on ne fait pas
                # échouer toute la rotation pour autant. On le signale.
                failed += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"Fuite {finding.id} : secret illisible avec les clés actuelles, ignoré."
                    )
                )
                continue
            BreachFinding.all_objects.filter(pk=finding.pk).update(secret_encrypted=new_blob)
            rotated += 1

        message = f"Rotation terminée : {rotated}/{total} secret(s) re-chiffré(s)."
        if failed:
            message += f" {failed} illisible(s) avec les clés actuelles — clé manquante ?"
            self.stdout.write(self.style.WARNING(message))
        else:
            self.stdout.write(self.style.SUCCESS(message))
