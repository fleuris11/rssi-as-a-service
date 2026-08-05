from django.core.management.base import BaseCommand, CommandError

from apps.monitoring import services
from apps.monitoring.models import Asset, CheckResult
from apps.tenants.models import Tenant


class Command(BaseCommand):
    """Injects consecutive CRITICAL http_uptime CheckResults for a declared
    asset and runs the real alert engine, so a DOWN alert opens exactly as
    it would from a genuine outage — without depending on a real external
    target actually being unreachable. Intended for E2E tests and demos
    (see docs/adr — Playwright flow "déclaration d'asset -> check simulé ->
    alerte visible"), never for production use."""

    help = "Simule des échecs consécutifs d'un check pour déclencher une alerte réelle."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", required=True)
        parser.add_argument("--asset-value", required=True)
        parser.add_argument(
            "--check-type",
            default=CheckResult.CheckType.HTTP_UPTIME,
            choices=CheckResult.CheckType.values,
        )
        parser.add_argument("--count", type=int, default=services.CONSECUTIVE_FAILURES_FOR_DOWN)

    def handle(self, *, tenant_slug, asset_value, check_type, count, **options):
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant introuvable : {tenant_slug!r}") from exc

        asset = Asset.all_objects.filter(tenant=tenant, value=asset_value).first()
        if asset is None:
            raise CommandError(f"Actif introuvable pour {tenant_slug!r} : {asset_value!r}")

        alert = None
        for _ in range(count):
            _result, alert = services.simulate_check_result(
                asset,
                check_type=check_type,
                status=CheckResult.Status.CRITICAL,
                details={"error": "Simulation E2E : hôte injoignable."},
            )

        if alert is not None:
            self.stdout.write(
                self.style.SUCCESS(f"Alerte ouverte : {alert.alert_type} ({alert.id})")
            )
        else:
            self.stdout.write(self.style.WARNING("Aucune alerte ouverte (vérifier --count)."))
