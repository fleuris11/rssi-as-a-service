"""Clients fictifs pour rendre le back-office démontrable (Phase 10).

Séparé de ``seed_demo_tenant`` à dessein : celui-là peuple **un** client avec
des fuites réalistes, pour démontrer le produit ; celui-ci crée **plusieurs**
clients sur des offres et des états différents, pour démontrer
l'administration. Les fusionner obligerait à charger l'un pour obtenir
l'autre.

Ces clients n'ont aucune fuite : l'administration ne montre que des
abonnements, des quotas et des compteurs (ADR-014).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.billing import services as billing_services
from apps.billing.models import Plan, Subscription
from apps.tenants.models import Membership, Tenant

DEMO_CLIENT_SUFFIX = "-demo-client"

# (nom, secteur, effectif, code d'offre, état visé)
DEMO_CLIENTS = [
    ("Demo — Menuiserie Lambert", "Artisanat", 12, "veille", Subscription.Status.ACTIVE),
    ("Demo — Transports Vidal", "Transport", 48, "pilotage", Subscription.Status.ACTIVE),
    ("Demo — Clinique des Tilleuls", "Santé", 130, "souverain", Subscription.Status.ACTIVE),
    ("Demo — Agence Novaé", "Communication", 8, "veille", Subscription.Status.TRIAL),
    ("Demo — Garage Peret", "Automobile", 15, "veille", Subscription.Status.SUSPENDED),
]


class Command(BaseCommand):
    help = "Crée des clients de démonstration sur différentes offres et différents états."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Supprime d'abord les clients de démo.")
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="Obligatoire pour tourner avec DEBUG=False.",
        )

    def handle(self, *, reset, allow_production, **options):
        from django.conf import settings

        if not settings.DEBUG and not allow_production:
            raise CommandError(
                "DEBUG=False : refus de créer des clients de démonstration sur un environnement "
                "de type production. Relancez avec --allow-production si c'est bien l'intention."
            )

        with transaction.atomic():
            if reset:
                self._reset()
            created = self._create_clients()

        self.stdout.write(
            self.style.SUCCESS(
                f"{created} client(s) de démonstration prêt(s). "
                "Consultez-les dans l'administration plateforme."
            )
        )

    def _reset(self):
        Tenant.objects.filter(slug__endswith=DEMO_CLIENT_SUFFIX).delete()

    def _create_clients(self) -> int:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        created = 0

        for name, sector, headcount, plan_code, target_status in DEMO_CLIENTS:
            slug = self._slug_for(name)
            if Tenant.objects.filter(slug=slug).exists():
                continue

            plan = Plan.objects.filter(code=plan_code).first()
            if plan is None:
                self.stdout.write(
                    self.style.WARNING(f"Offre {plan_code!r} absente — client {name!r} ignoré.")
                )
                continue

            owner_email = f"contact@{slug}.example"
            owner, _ = User.objects.get_or_create(
                email=owner_email, defaults={"first_name": "Contact", "last_name": name.split("—")[-1].strip()}
            )
            tenant = Tenant.objects.create(
                name=name, slug=slug, sector=sector, headcount=headcount
            )
            Membership.all_objects.create(
                tenant=tenant, user=owner, role=Membership.Role.ADMIN
            )

            # On passe par le service : la garde de capacité s'applique donc à
            # ces clients comme aux vrais. Si le pool est plein, le seed
            # s'arrête proprement plutôt que de fabriquer un état impossible.
            subscription = billing_services.start_trial(tenant=tenant, plan=plan, actor=owner)

            if target_status == Subscription.Status.ACTIVE:
                billing_services.activate(
                    subscription=subscription, reason="Client de démonstration activé."
                )
            elif target_status == Subscription.Status.SUSPENDED:
                billing_services.activate(subscription=subscription)
                billing_services.suspend(
                    subscription=subscription, reason="Impayé (client de démonstration)."
                )
            elif target_status == Subscription.Status.TRIAL:
                # Essai qui se termine bientôt : donne à voir un cas concret
                # dans la liste d'administration.
                subscription.trial_ends_at = timezone.now() + timedelta(days=3)
                subscription.save(update_fields=["trial_ends_at"])

            created += 1

        return created

    @staticmethod
    def _slug_for(name: str) -> str:
        from django.utils.text import slugify

        return f"{slugify(name)[:180]}{DEMO_CLIENT_SUFFIX}"
