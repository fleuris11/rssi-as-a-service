"""Clients fictifs pour rendre le back-office démontrable (Phase 10).

Séparé de ``seed_demo_tenant`` à dessein : celui-là peuple **un** client avec
des fuites réalistes, pour démontrer le produit ; celui-ci crée **plusieurs**
clients sur des offres et des états différents, pour démontrer
l'administration. Les fusionner obligerait à charger l'un pour obtenir
l'autre.

Ces clients n'ont aucune fuite : l'administration ne montre que des
abonnements, des quotas et des compteurs (ADR-014).

Depuis la phase 11, la commande crée aussi des **prospects** à divers stades :
sans eux, la vue de suivi commercial et la conversion sans ressaisie ne se
démontrent pas.
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
    # Essai en cours : il porte l'offre d'essai, pas une offre du catalogue
    # (ADR-024). Le laisser sur « Veille » ferait diverger le seed de la
    # migration 0004, qui bascule justement les essais vers « Essai » — les
    # deux se contrediraient à chaque rechargement du jeu de démonstration.
    # La différenciation « Veille » reste illustrée par Lambert (actif) et
    # Peret (suspendu), qui suffisent aux tuiles grisées.
    ("Demo — Agence Novaé", "Communication", 8, "essai", Subscription.Status.TRIAL),
    ("Demo — Garage Peret", "Automobile", 15, "veille", Subscription.Status.SUSPENDED),
]

# Prospects de démonstration (phase 11).
# (entreprise, contact, fonction, taille, statut, relance dans N jours, motif de perte)
# ``None`` en relance = aucune date prévue ; combiné à une dernière activité
# ancienne, c'est ce qui fait apparaître un prospect comme « en sommeil ».
DEMO_PROSPECTS = [
    ("Demo — Cabinet Ferrand", "Inès Ferrand", "Associée", "10-49", "new", 0, ""),
    ("Demo — Imprimerie Sault", "Marc Sault", "Gérant", "1-9", "contacted", 2, ""),
    ("Demo — Groupe Ancelin", "Sofia Ancelin", "DSI", "250+", "scheduled", 5, ""),
    ("Demo — Laboratoire Vionnet", "Théo Vionnet", "Directeur", "50-249", "proposal", 1, ""),
    ("Demo — Étude Bardet", "Claire Bardet", "Notaire", "10-49", "new", None, ""),
    (
        "Demo — Transports Kessler",
        "Yann Kessler",
        "Responsable IT",
        "50-249",
        "lost",
        None,
        "Budget reporté à l'exercice suivant.",
    ),
]

# Ancienneté simulée du prospect « en sommeil » : au-delà du seuil de la vue
# de suivi (14 jours), pour qu'il y apparaisse réellement.
STALE_PROSPECT_AGE_DAYS = 40


class Command(BaseCommand):
    help = "Crée des clients de démonstration sur différentes offres et différents états."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Supprime d'abord les clients de démo."
        )
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
            prospects = self._create_prospects()

        self.stdout.write(
            self.style.SUCCESS(
                f"{created} client(s) et {prospects} prospect(s) de démonstration prêts. "
                "Consultez-les dans l'administration plateforme."
            )
        )

    def _reset(self):
        from apps.marketing.models import DemoRequest

        Tenant.objects.filter(slug__endswith=DEMO_CLIENT_SUFFIX).delete()
        DemoRequest.objects.filter(company__startswith="Demo — ").delete()

    def _create_prospects(self) -> int:
        """Prospects couvrant chaque étape du suivi commercial.

        Passe par le service, comme le ferait la console : le motif de perte
        obligatoire et les autres règles s'appliquent donc ici aussi.
        """
        from apps.marketing import services as marketing_services
        from apps.marketing.models import DemoRequest

        created = 0
        today = timezone.localdate()

        for company, full_name, role, size, status, follow_up, lost_reason in DEMO_PROSPECTS:
            if DemoRequest.objects.filter(company=company).exists():
                continue

            prospect = marketing_services.create_prospect(
                company=company,
                full_name=full_name,
                role=role,
                email=f"{full_name.split()[0].lower()}@{self._slug_for(company)[:40]}.example",
                company_size=size,
                message="Prospect de démonstration.",
            )
            marketing_services.update_prospect(
                prospect=prospect,
                status=status,
                lost_reason=lost_reason,
                next_follow_up_on=(
                    today + timedelta(days=follow_up) if follow_up is not None else None
                ),
            )

            if status == "new" and follow_up is None:
                # Le cas « en sommeil » : aucune relance prévue et plus aucune
                # activité depuis longtemps. ``update_at`` étant auto_now, on
                # le force par un UPDATE direct.
                DemoRequest.objects.filter(id=prospect.id).update(
                    updated_at=timezone.now() - timedelta(days=STALE_PROSPECT_AGE_DAYS)
                )

            marketing_services.add_prospect_note(
                prospect=prospect,
                body="Premier échange : découverte du besoin.",
            )
            created += 1

        return created

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
                email=owner_email,
                defaults={"first_name": "Contact", "last_name": name.split("—")[-1].strip()},
            )
            tenant = Tenant.objects.create(name=name, slug=slug, sector=sector, headcount=headcount)
            Membership.all_objects.create(tenant=tenant, user=owner, role=Membership.Role.ADMIN)

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
