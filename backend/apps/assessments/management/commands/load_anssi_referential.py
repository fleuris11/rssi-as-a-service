"""Charge le référentiel ANSSI livré avec le produit.

Depuis V2-4 ce n'est plus qu'un raccourci vers ``import_referential`` sur le
fichier embarqué : l'ANSSI n'est plus « le » référentiel, seulement le seul
que nous ayons le droit d'embarquer (Licence Ouverte / Etalab).

La commande est conservée sous ce nom parce que les deux docker-compose
l'appellent au démarrage : la renommer aurait cassé le déploiement pour
gagner un nom plus juste.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.assessments import importers
from apps.assessments.models import Referential

DEFAULT_FIXTURE = Path(settings.BASE_DIR) / "data" / "anssi_hygiene.json"


class Command(BaseCommand):
    help = "Charge (ou met à jour) le référentiel ANSSI depuis backend/data/anssi_hygiene.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            default=DEFAULT_FIXTURE,
            help="Chemin du fichier JSON du référentiel (défaut : data/anssi_hygiene.json).",
        )

    def handle(self, *args, **options):
        try:
            parsed = importers.read_file(options["file"], fmt="json")
        except importers.ReferentialImportError as exc:
            raise CommandError(str(exc)) from exc

        parsed.kind = Referential.Kind.OPEN
        parsed.publisher = parsed.publisher or "ANSSI"
        parsed.licence_notice = (
            parsed.licence_notice or "Licence Ouverte / Open Licence (Etalab, version 1)"
        )

        report = importers.import_referential(parsed)
        self.stdout.write(
            self.style.SUCCESS(
                f"Référentiel « {report.referential.name} » chargé : "
                f"{report.domains} domaines, {report.measures} mesures."
            )
        )
