"""Déclare auprès de Breachsense les identifiants qui protègent NOTRE webhook.

Point à comprendre avant tout, parce qu'il est contre-intuitif et qu'il a
coûté une fonctionnalité invendable pendant deux semaines :

    Ces identifiants ne sont PAS fournis par Breachsense. C'est nous qui les
    choisissons.

Le webhook est un endpoint de *notre* plateforme
(``POST /api/v1/webhooks/breachsense``). Breachsense y pousse les fuites dès
qu'il en détecte une. Comme cet endpoint n'a ni JWT ni session — l'appelant
est une machine tierce — il est protégé par une authentification HTTP Basic
dont **nous fixons le couple identifiant/mot de passe** (ADR-013 §7), puis que
nous **déclarons** à Breachsense pour qu'il les présente à chaque envoi.

D'où trois valeurs, et une seule vient du fournisseur :

======================================  ==========================
``BREACHSENSE_LICENSE_KEY``             fournie par Breachsense
``BREACHSENSE_WEBHOOK_USERNAME``        **choisie par nous**
``BREACHSENSE_WEBHOOK_PASSWORD``        **choisie par nous**
``BREACHSENSE_WEBHOOK_CALLBACK_URL``    **la nôtre** (notre domaine)
======================================  ==========================

``BreachsenseProvider.configure_webhook_credentials`` existait déjà, avec une
docstring renvoyant à « la commande de déploiement » — commande qui n'avait
jamais été écrite. La méthode n'était donc appelée de nulle part, et la
surveillance continue refusait de s'activer sans que rien n'explique pourquoi.

Marche à suivre complète :

    # 1. Générer un couple (sur le serveur, jamais transmis)
    python manage.py configurer_webhook_breachsense --generer

    # 2. Le renseigner en frappe masquée
    ./deploy/configurer-secret.sh BREACHSENSE_WEBHOOK_USERNAME
    ./deploy/configurer-secret.sh BREACHSENSE_WEBHOOK_PASSWORD
    #    et l'URL, qui n'est pas un secret :
    #    BREACHSENSE_WEBHOOK_CALLBACK_URL=https://<domaine>/api/v1/webhooks/breachsense

    # 3. Redémarrer, puis déclarer le couple côté Breachsense
    docker compose -f docker-compose.prod.yml restart web worker beat
    python manage.py configurer_webhook_breachsense
"""

import secrets

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.threat_intelligence.providers import MODE_LIVE, resolve_mode
from apps.threat_intelligence.providers.breachsense.client import BreachsenseError
from apps.threat_intelligence.providers.breachsense.provider import BreachsenseProvider

CHEMIN_WEBHOOK = "/api/v1/webhooks/breachsense"


class Command(BaseCommand):
    help = "Déclare à Breachsense les identifiants HTTP Basic de notre webhook."

    def add_arguments(self, parser):
        parser.add_argument(
            "--generer",
            action="store_true",
            help=(
                "Propose un couple identifiant/mot de passe solide et s'arrête. "
                "Ne déclare rien et n'écrit nulle part : à reporter dans "
                "backend/.env via deploy/configurer-secret.sh."
            ),
        )

    def handle(self, *args, **options):
        ok, ko, warn = self.style.SUCCESS, self.style.ERROR, self.style.WARNING

        if options["generer"]:
            # `token_urlsafe` : aléatoire cryptographique, pas `random`. Ces
            # identifiants gardent l'unique porte d'entrée non authentifiée
            # par JWT de la plateforme.
            self.stdout.write("Couple proposé — à reporter dans backend/.env, puis à oublier :")
            self.stdout.write("")
            self.stdout.write(f"  BREACHSENSE_WEBHOOK_USERNAME={secrets.token_urlsafe(12)}")
            self.stdout.write(f"  BREACHSENSE_WEBHOOK_PASSWORD={secrets.token_urlsafe(32)}")
            self.stdout.write("")
            self.stdout.write(
                warn(
                    "Ces valeurs viennent de s'afficher : ne les laissez pas dans "
                    "l'historique de votre terminal, et renseignez-les en frappe "
                    "masquée avec deploy/configurer-secret.sh."
                )
            )
            return

        manquants = [
            nom
            for nom in (
                "BREACHSENSE_WEBHOOK_USERNAME",
                "BREACHSENSE_WEBHOOK_PASSWORD",
                "BREACHSENSE_WEBHOOK_CALLBACK_URL",
            )
            if not getattr(settings, nom, "")
        ]
        if manquants:
            self.stdout.write(ko("Configuration incomplète : " + ", ".join(manquants)))
            self.stdout.write(
                "Générez un couple avec --generer, renseignez-le, redémarrez, puis relancez."
            )
            return

        url = settings.BREACHSENSE_WEBHOOK_CALLBACK_URL
        if not url.startswith("https://"):
            self.stdout.write(
                ko(
                    f"L'URL de rappel n'est pas en HTTPS ({url}). Les identifiants du "
                    "webhook transiteraient en clair à chaque notification."
                )
            )
            return
        if not url.endswith(CHEMIN_WEBHOOK):
            self.stdout.write(
                warn(
                    f"L'URL de rappel ne se termine pas par {CHEMIN_WEBHOOK} : "
                    "vérifiez qu'elle pointe bien sur l'endpoint d'ingestion."
                )
            )

        mode = resolve_mode()
        if mode != MODE_LIVE:
            self.stdout.write(
                ko(
                    f"Mode CTI résolu : {mode}. Cette commande parle à l'API réelle — "
                    "sans licence active, elle ne déclarerait rien."
                )
            )
            return

        try:
            BreachsenseProvider().configure_webhook_credentials()
        except BreachsenseError as exc:
            self.stdout.write(ko(f"Déclaration refusée : {exc}"))
            return

        self.stdout.write(ok("Identifiants du webhook déclarés auprès de Breachsense."))
        self.stdout.write(f"URL de rappel : {url}")
        self.stdout.write(
            "Vérifiez ensuite qu'un actif peut être mis sous surveillance continue "
            "depuis l'espace client."
        )
