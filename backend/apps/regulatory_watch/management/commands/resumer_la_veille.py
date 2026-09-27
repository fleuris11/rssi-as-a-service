"""Demande à l'IA un résumé des publications de veille qui n'en ont pas.

Pourquoi une commande alors que la console a déjà un bouton : parce qu'au
démarrage la file en contient plusieurs dizaines, et qu'ouvrir chacune pour
cliquer n'apporte rien de plus que cette boucle. Le geste reste **déclenché à
la main** — la collecte ne résume rien d'elle-même (sobriété) — et il reste
borné : ``--limite`` existe pour qu'une erreur de manipulation ne lance pas
deux cents appels.

Ce que la commande ne change pas :

- **le texte source reste la référence.** Le résumé vient à côté, daté et
  identifié comme produit par une machine (consigne V2-7 §7) ;
- **aucune qualification, aucun changement de statut.** Résumer n'est pas
  décider. Retenir ou écarter une publication reste un geste humain, posé
  depuis la console, avec un relecteur nommé ;
- **aucun référentiel touché.**

``--acteur`` est obligatoire : ``summarize_update`` refuse un résumé qui ne
serait demandé par personne, et c'est voulu — un résumé coûte, et on doit
savoir qui l'a demandé.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.regulatory_watch import services
from apps.regulatory_watch.models import WatchUpdate

#: Une borne haute par défaut, plutôt que « tout » : la file de départ compte
#: une vingtaine d'entrées, et un appel par entrée est un coût réel.
LIMITE = 25


class Command(BaseCommand):
    help = "Résume par l'IA les publications de veille encore sans résumé."

    def add_arguments(self, parser):
        parser.add_argument(
            "--acteur", required=True, help="Adresse du compte qui demande les résumés."
        )
        parser.add_argument("--limite", type=int, default=LIMITE)
        parser.add_argument(
            "--statut",
            default="",
            help="Ne traiter qu'un statut. Par défaut : les publications ouvertes "
            "(à examiner et retenues).",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        User = get_user_model()
        acteur = User.objects.filter(email__iexact=options["acteur"].strip()).first()
        if acteur is None:
            raise CommandError(f"Aucun compte « {options['acteur']} ».")
        if not acteur.is_staff:
            # La veille est un objet d'exploitation, pas de client : la
            # demander suppose d'être du côté de la plateforme.
            raise CommandError("Ce compte n'est pas un compte d'exploitation.")

        statuts = (
            [options["statut"]]
            if options["statut"]
            else [WatchUpdate.Status.NEW, WatchUpdate.Status.KEPT]
        )
        inconnus = [s for s in statuts if s not in WatchUpdate.Status.values]
        if inconnus:
            raise CommandError(f"Statut inconnu : {', '.join(inconnus)}.")

        candidates = [
            maj
            for maj in WatchUpdate.objects.filter(status__in=statuts)
            .exclude(source_excerpt="")
            .select_related("source")
            .order_by("-detected_at")
            if not maj.ai_summary.strip()
        ][: options["limite"]]

        if not candidates:
            self.stdout.write("Aucune publication à résumer.")
            return

        self.stdout.write(f"{len(candidates)} publication(s) à résumer.")
        if options["dry_run"]:
            for maj in candidates:
                self.stdout.write(f"  — {maj.source.slug} : {maj.title[:90]}")
            return

        jetons_entree = jetons_sortie = 0
        echecs = 0
        for maj in candidates:
            try:
                resume = services.summarize_update(maj, reviewer=acteur)
            except Exception as erreur:  # noqa: BLE001 - une source ne doit pas arrêter la boucle
                echecs += 1
                self.stderr.write(f"  échec sur « {maj.title[:70]} » : {erreur}")
                continue
            jetons_entree += resume.ai_tokens_input
            jetons_sortie += resume.ai_tokens_output
            self.stdout.write(f"  + {maj.title[:80]}")

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(candidates) - echecs} résumé(s), {echecs} échec(s) — "
                f"{jetons_entree} jetons en entrée, {jetons_sortie} en sortie."
            )
        )
