"""Vérifie que le mode « live » fonctionne réellement contre l'API Breachsense.

Cette commande existe à cause d'une panne réelle. Le client HTTP avait été
écrit sur un contrat *supposé* (`?domain=`), la suite de tests vérifiait ce
même contrat supposé — donc restait verte — et personne n'a rien vu jusqu'à ce
qu'un vrai client bascule en « live » et reçoive un ``400 Request missing the
appropriate parameters`` sur chaque analyse. Le paramètre réel est ``s``.

La leçon, et la raison d'être de ce fichier : **une suite de tests ne peut pas
valider un contrat externe.** Elle valide qu'on s'appelle soi-même comme on
croit devoir le faire. Seul un appel réel tranche — il ne peut pas vivre dans
la CI (pas de licence, et le quota est partagé), il doit donc être une
commande qu'un exploitant lance délibérément.

Coût : **zéro requête** du budget mensuel par défaut (les appels ``/account``
ne sont pas des requêtes de recherche). Avec ``--domaine``, une recherche est
consommée par endpoint testé.

    python manage.py verifier_breachsense
    python manage.py verifier_breachsense --domaine exemple.fr
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.threat_intelligence.providers import MODE_LIVE, resolve_mode
from apps.threat_intelligence.providers.breachsense.client import (
    QUERY_ENDPOINTS,
    BreachsenseClient,
    BreachsenseError,
)

# Un seul endpoint suffit à valider le contrat de requête : tous partagent le
# même paramètre `s`. On ne dépense pas neuf requêtes pour prouver une fois.
ENDPOINT_TEMOIN = "creds"


class Command(BaseCommand):
    help = "Vérifie que la licence Breachsense répond et que le contrat de requête est le bon."

    def add_arguments(self, parser):
        parser.add_argument(
            "--domaine",
            help=(
                "Domaine à interroger pour valider le contrat de recherche. "
                "Consomme 1 requête du budget mensuel partagé. Sans ce drapeau, "
                "seuls les appels de compte (gratuits) sont effectués."
            ),
        )
        parser.add_argument(
            "--tous-les-endpoints",
            action="store_true",
            help=(
                "Interroge les neuf endpoints au lieu du seul témoin. "
                "Consomme 9 requêtes — à réserver à une vérification de schéma."
            ),
        )

    def handle(self, *args, **options):
        ok = self.style.SUCCESS
        ko = self.style.ERROR
        warn = self.style.WARNING

        mode = resolve_mode()
        self.stdout.write(f"Mode CTI résolu : {mode}")
        if mode != MODE_LIVE:
            self.stdout.write(
                warn(
                    "Le mode actif n'est pas « live » : cette commande teste la licence réelle, "
                    "elle ne dit donc rien de ce que voient vos clients aujourd'hui. "
                    "Le test se poursuit quand même — c'est précisément ce qu'on veut vérifier "
                    "AVANT de basculer en live."
                )
            )

        client = BreachsenseClient()
        if not client.license_key:
            self.stdout.write(ko("BREACHSENSE_LICENSE_KEY est absente : rien à tester."))
            return

        echecs = 0

        # 1. Budget restant — gratuit, et c'est le test d'authentification.
        try:
            reponse = client.account_remaining()
            restant = reponse.get("Remaining", reponse.get("remaining"))
            if restant is None:
                self.stdout.write(
                    ko(
                        f"Budget : réponse sans champ « Remaining » ({reponse!r}). "
                        "La licence répond mais le contrat a changé."
                    )
                )
                echecs += 1
            else:
                self.stdout.write(ok(f"Budget : {restant} requêtes restantes ce mois."))
        except BreachsenseError as exc:
            self.stdout.write(ko(f"Budget : échec — {exc}"))
            echecs += 1

        # 2. Pool d'actifs surveillés — gratuit.
        try:
            actifs = client.account_list()
            valeurs = [item.get("ast") for item in actifs if item.get("ast")]
            if actifs and not valeurs:
                self.stdout.write(
                    ko(f"Pool : {len(actifs)} entrée(s) mais aucun champ « ast » — contrat changé.")
                )
                echecs += 1
            else:
                liste = ", ".join(valeurs) or "—"
                self.stdout.write(ok(f"Pool : {len(valeurs)} actif(s) enregistré(s) — {liste}"))
        except BreachsenseError as exc:
            self.stdout.write(ko(f"Pool : échec — {exc}"))
            echecs += 1

        # 3. Webhook — gratuit, et c'est ce qui manquait sans que rien ne le
        # dise : la surveillance continue refusait de s'activer, et seule une
        # lecture des journaux permettait de comprendre pourquoi.
        webhook = {
            nom: bool(getattr(settings, nom, ""))
            for nom in (
                "BREACHSENSE_WEBHOOK_CALLBACK_URL",
                "BREACHSENSE_WEBHOOK_USERNAME",
                "BREACHSENSE_WEBHOOK_PASSWORD",
            )
        }
        absents = [nom for nom, present in webhook.items() if not present]
        if absents:
            self.stdout.write(
                ko(
                    "Webhook : non configuré — "
                    + ", ".join(nom.replace("BREACHSENSE_WEBHOOK_", "") for nom in absents)
                    + " manquant(s). La surveillance continue ne peut pas être activée "
                    "(voir « configurer_webhook_breachsense »)."
                )
            )
            echecs += 1
        else:
            self.stdout.write(ok("Webhook : les trois valeurs sont renseignées."))

        # 4. Contrat de recherche — payant, donc explicitement demandé.
        domaine = options.get("domaine")
        if not domaine:
            self.stdout.write(
                "Recherche : non testée (relancez avec --domaine <votre-domaine> pour la valider)."
            )
        else:
            endpoints = QUERY_ENDPOINTS if options["tous_les_endpoints"] else (ENDPOINT_TEMOIN,)
            for endpoint in endpoints:
                try:
                    items, consommees = getattr(client, endpoint)(s=domaine)
                    self.stdout.write(
                        ok(
                            f"Recherche /{endpoint} : {len(items)} résultat(s), "
                            f"{consommees} requête(s) consommée(s)."
                        )
                    )
                except BreachsenseError as exc:
                    self.stdout.write(ko(f"Recherche /{endpoint} : échec — {exc}"))
                    echecs += 1

        self.stdout.write("")
        if echecs:
            self.stdout.write(
                ko(f"{echecs} vérification(s) en échec : le mode « live » n'est pas exploitable.")
            )
        else:
            self.stdout.write(ok("Toutes les vérifications passent."))
