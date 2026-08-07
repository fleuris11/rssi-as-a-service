from django.core.management.base import BaseCommand, CommandError

from apps.monitoring.models import Asset
from apps.tenants.models import Tenant
from apps.threat_intelligence import services
from apps.threat_intelligence.models import BreachFinding
from apps.threat_intelligence.providers.base import RawFinding


class Command(BaseCommand):
    """Injects one simulated BreachFinding through the real ingestion
    pipeline (normalisation, masquage, dédoublonnage, alerte) for a
    declared asset — without depending on a real Breachsense license.
    Intended for E2E tests and demos (prompt Phase 7 point 7 : "rends-le
    entièrement testable avec des payloads simulés"), never for
    production use."""

    help = "Simule une fuite Breachsense détectée sur un actif déclaré."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", required=True)
        parser.add_argument("--asset-value", required=True)
        parser.add_argument(
            "--endpoint",
            default=BreachFinding.SourceEndpoint.STEALER,
            choices=BreachFinding.SourceEndpoint.values,
        )
        parser.add_argument("--email", default="compte.compromis@example.com")

    def handle(self, *, tenant_slug, asset_value, endpoint, email, **options):
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant introuvable : {tenant_slug!r}") from exc

        asset = Asset.all_objects.filter(tenant=tenant, value=asset_value).first()
        if asset is None:
            raise CommandError(f"Actif introuvable pour {tenant_slug!r} : {asset_value!r}")

        raw = RawFinding(
            endpoint=endpoint,
            payload={
                "email": email,
                "password": "SimulatedP4ssw0rd!23",
                "date": "2026-01-15",
                "type": "simulation-e2e",
            },
        )
        created = services.ingest_raw_findings(tenant=tenant, asset=asset, raw_findings=[raw])

        if created:
            self.stdout.write(self.style.SUCCESS(f"Fuite simulée créée : {created[0].id}"))
        else:
            self.stdout.write(self.style.WARNING("Aucune fuite créée (doublon détecté ?)."))
