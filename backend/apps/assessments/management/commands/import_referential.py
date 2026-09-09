"""Importe un référentiel depuis un fichier JSON ou un tableur CSV.

    python manage.py import_referential --file data/anssi_hygiene.json
    python manage.py import_referential --file iso27001.csv --slug iso-27001-annexe-a \\
        --name "ISO/IEC 27001:2022 — Annexe A" --ref-version 2022 --kind licensed \\
        --licence-notice "Reproduit sous licence ISO n°XXXX — usage interne."

Le format est documenté dans ``docs/format_import_referentiel.md``.

**Contenu sous droits** : le dépôt n'embarque que l'ANSSI (Licence Ouverte).
ISO 27001, le NIST CSF et les CIS Controls s'importent avec cette commande,
depuis un fichier que l'exploitant ou le client fournit — nous livrons la
structure d'accueil, pas le contenu.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.assessments import importers
from apps.assessments.models import Referential


class Command(BaseCommand):
    help = "Importe un référentiel (JSON ou CSV) dans le catalogue."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=Path, required=True, help="Chemin du fichier.")
        parser.add_argument(
            "--format",
            choices=["json", "csv"],
            default=None,
            help="Forcé si l'extension ne suffit pas (défaut : déduit du suffixe).",
        )
        # Métadonnées : indispensables en CSV (un tableur ne porte pas
        # d'en-tête structuré), facultatives en JSON où elles surchargent le
        # fichier.
        parser.add_argument("--slug")
        parser.add_argument("--name")
        # « --ref-version » et non « --version » : Django réserve ce dernier
        # pour afficher sa propre version, et le redéfinir fait échouer la
        # commande au chargement.
        parser.add_argument("--ref-version", dest="ref_version")
        parser.add_argument("--publisher", default="")
        parser.add_argument("--description", default="")
        parser.add_argument("--source-url", default="")
        parser.add_argument(
            "--kind",
            choices=Referential.Kind.values,
            default=None,
            help="open (libre de droits), licensed (soumis à droits), custom (propre à un client).",
        )
        parser.add_argument(
            "--licence-notice",
            default="",
            help="Mention de droits affichée avec le référentiel.",
        )
        parser.add_argument(
            "--inactive",
            action="store_true",
            help="Importe sans rendre le référentiel attribuable.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyse et valide le fichier sans rien écrire.",
        )

    def handle(self, *args, **options):
        header = {
            "slug": options.get("slug"),
            "name": options.get("name"),
            "version": options.get("ref_version"),
            "publisher": options.get("publisher") or "",
            "description": options.get("description") or "",
            "source_url": options.get("source_url") or "",
            "licence_notice": options.get("licence_notice") or "",
        }
        if options.get("kind"):
            header["kind"] = options["kind"]

        try:
            parsed = importers.read_file(options["file"], fmt=options.get("format"), header=header)
        except importers.ReferentialImportError as exc:
            raise CommandError(str(exc)) from exc

        # En JSON, les options passées en ligne de commande l'emportent sur le
        # fichier : c'est ce qui permet d'importer une coquille livrée avec le
        # produit en y ajoutant SA propre mention de licence.
        for champ in ("publisher", "description", "source_url", "licence_notice"):
            if header.get(champ):
                setattr(parsed, champ, header[champ])
        if options.get("kind"):
            parsed.kind = options["kind"]

        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Fichier valide : « {parsed.name} » ({parsed.slug}, v{parsed.version}) — "
                    f"{len(parsed.domains)} domaines, {parsed.measure_count} mesures. "
                    "Rien n'a été écrit (--dry-run)."
                )
            )
            return

        try:
            report = importers.import_referential(parsed, activate=not options["inactive"])
        except importers.ReferentialImportError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Référentiel « {report.referential.name} » importé : "
                f"{report.domains} domaines, {report.measures} mesures "
                f"({report.created} créées, {report.updated} mises à jour)."
            )
        )
        if report.orphans:
            # Averti, jamais supprimé : une réponse de client peut référencer
            # ces mesures, et un import n'a pas à effacer un diagnostic.
            self.stdout.write(
                self.style.WARNING(
                    f"{len(report.orphans)} mesure(s) en base ne figurent plus dans le "
                    f"fichier et ont été CONSERVÉES : {', '.join(report.orphans)}."
                )
            )
