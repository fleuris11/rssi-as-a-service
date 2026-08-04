import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assessments.models import Domain, Measure, Referential

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
        path: Path = options["file"]
        if not path.exists():
            raise CommandError(f"Fichier introuvable : {path}")

        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)

        with transaction.atomic():
            referential, _ = Referential.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "version": data["version"],
                    "description": data.get("description", ""),
                    "is_active": True,
                },
            )

            domain_count = 0
            measure_count = 0
            for domain_data in data["domains"]:
                domain, _ = Domain.objects.update_or_create(
                    referential=referential,
                    code=domain_data["code"],
                    defaults={
                        "name": domain_data["name"],
                        "description": domain_data.get("description", ""),
                        "order": domain_data["order"],
                    },
                )
                domain_count += 1

                for measure_data in domain_data["measures"]:
                    Measure.objects.update_or_create(
                        code=measure_data["code"],
                        defaults={
                            "domain": domain,
                            "order": measure_data["order"],
                            "official_title": measure_data["official_title"],
                            "plain_language": measure_data["plain_language"],
                            "level": measure_data["level"],
                            "effort": measure_data["effort"],
                            "impact": measure_data["impact"],
                        },
                    )
                    measure_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Référentiel « {referential.name} » chargé : "
                f"{domain_count} domaines, {measure_count} mesures."
            )
        )
