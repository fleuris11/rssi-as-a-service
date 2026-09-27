"""Charge la bibliothèque de cours (``apps.training.catalogue``).

Pourquoi une commande et non une migration de données : le contenu d'un cours
se corrige. Une migration ne se rejoue pas, et corriger une faute
d'orthographe dans un écran demanderait d'écrire une migration de plus à
chaque fois. Une commande idempotente se relance autant qu'on veut.

Ce qui est garanti :

- **idempotent** : un cours déjà chargé n'est pas retouché sans ``--reset`` ;
- **aucune inscription cassée** : ``--reset`` vide le CONTENU de la version
  courante, jamais la version — une inscription pointe dessus (ADR-039) ;
- **publié par le chemin normal** : la publication passe par
  ``studio.publier``, qui refuse un cours sans écran ou sans bonne réponse. La
  commande n'a pas le droit de publier ce que le studio refuserait.

Attribution : ``--tenant`` propose les cours à un client. Sans lui, les cours
entrent au catalogue sans être visibles de personne — ce qui est le bon défaut
pour une bibliothèque.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.tenants.models import Tenant
from apps.training import catalogue, services, studio
from apps.training.models import (
    SEUIL_REUSSITE_DEFAUT,
    Choice,
    Course,
    CourseVersion,
    Question,
    Screen,
)


class Command(BaseCommand):
    help = "Charge la bibliothèque de cours livrée avec le produit."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reprend le contenu des cours à zéro. Les inscriptions ne sont pas "
            "touchées : elles pointent vers une version, qui est conservée.",
        )
        parser.add_argument(
            "--tenant",
            default="",
            help="Propose tous les cours de la bibliothèque à ce client (slug).",
        )
        parser.add_argument(
            "--slug",
            default="",
            help="Ne traiter qu'un seul cours, par son slug. Utile pour corriger un cours "
            "sans relire les autres.",
        )

    def handle(self, *args, **options):
        demandes = catalogue.COURS
        if options["slug"]:
            demandes = [c for c in demandes if c["slug"] == options["slug"]]
            if not demandes:
                self.stderr.write(f"Aucun cours « {options['slug']} » dans le catalogue.")
                return

        client = None
        if options["tenant"]:
            client = Tenant.objects.filter(slug=options["tenant"]).first()
            if client is None:
                self.stderr.write(f"Client « {options['tenant']} » introuvable.")
                return

        for donnees in demandes:
            self._un_cours(donnees, reset=options["reset"], client=client)

        total = Course.objects.filter(owner_tenant__isnull=True).count()
        self.stdout.write(
            self.style.SUCCESS(f"Bibliothèque : {total} cours, dont {len(demandes)} traités.")
        )

    # --- Un cours ----------------------------------------------------------

    @transaction.atomic
    def _un_cours(self, donnees, *, reset, client):
        cours, cree = Course.objects.get_or_create(
            slug=donnees["slug"],
            defaults={"title": donnees["title"], "summary": donnees["summary"]},
        )
        if not cree:
            # Le titre et le résumé, eux, se corrigent sans reset : ils ne sont
            # pas du contenu d'écran, et une inscription n'en dépend pas.
            cours.title = donnees["title"]
            cours.summary = donnees["summary"]
            cours.save(update_fields=["title", "summary"])

        version = cours.versions.order_by("-number").first()
        if version is None:
            version = CourseVersion.objects.create(
                course=cours,
                number=1,
                pass_threshold=donnees.get("seuil", SEUIL_REUSSITE_DEFAUT),
                change_note="Version initiale — bibliothèque.",
            )
        elif reset:
            version.screens.all().delete()
            version.questions.all().delete()

        if version.screens.exists():
            self.stdout.write(f"  {cours.slug} : déjà chargé (--reset pour reprendre).")
        else:
            self._charger(version, donnees)
            if not version.is_published:
                studio.publier(version)
            for avertissement in services.avertissements_de_quiz(version):
                self.stdout.write(self.style.WARNING(f"  {cours.slug} : {avertissement}"))
            self.stdout.write(
                f"  {cours.slug} : {version.screens.count()} écrans, "
                f"{version.questions.count()} questions, "
                f"{version.estimated_minutes} min, seuil {version.pass_threshold} %."
            )

        if client is not None:
            # Le contexte de cloisonnement n'est pas décoratif : ``CourseAssignment``
            # est un modèle cloisonné, son manager par défaut échoue en fermeture
            # hors contexte. Une commande n'en reçoit pas du middleware.
            with services.contexte_du_client(client):
                services.attribuer_cours(tenant=client, course=cours)

    def _charger(self, version, donnees):
        ecrans = [
            Screen.objects.create(
                version=version,
                order=rang,
                title=ecran["title"],
                content=ecran["content"],
                estimated_seconds=ecran["seconds"],
            )
            for rang, ecran in enumerate(donnees["ecrans"], start=1)
        ]

        for rang, vise, enonce, genre, explication, choix in donnees["questions"]:
            question = Question.objects.create(
                version=version,
                order=rang,
                text=enonce,
                kind=genre,
                explanation=explication,
                screen=ecrans[vise - 1],
            )
            for position, (texte, correct) in enumerate(choix, start=1):
                Choice.objects.create(
                    question=question, order=position, text=texte, is_correct=correct
                )
