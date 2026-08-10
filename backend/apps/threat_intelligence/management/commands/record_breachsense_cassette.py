"""Records ONE real Breachsense scan into a replayable cassette (Phase 8A,
ADR-015). This is the only command in the codebase that deliberately spends
the platform's shared query budget — hence the explicit ``--confirm-live-call``
flag: no cassette is ever recorded as a side effect of something else.

ADR-014 applies to fixtures exactly as it applies to the database: every
payload is passed through ``normalizer.mask_payload`` BEFORE being written,
so a cassette on disk (and therefore in Git) never contains a secret in
clear.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.threat_intelligence.providers.breachsense.normalizer import mask_payload
from apps.threat_intelligence.providers.breachsense.provider import BreachsenseProvider
from apps.threat_intelligence.providers.replay_provider import cassette_path


class Command(BaseCommand):
    help = (
        "Enregistre une cassette rejouable à partir d'UN scan Breachsense réel "
        "(consomme le quota partagé — voir ADR-015)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--domain", required=True)
        parser.add_argument(
            "--confirm-live-call",
            action="store_true",
            help="Obligatoire : confirme que cet appel doit réellement consommer du quota.",
        )
        parser.add_argument(
            "--output",
            default="",
            help="Chemin de sortie (par défaut : tests/fixtures/breachsense/<domaine>.json).",
        )

    def handle(self, *, domain, confirm_live_call, output, **options):
        if not confirm_live_call:
            raise CommandError(
                "Cette commande consomme le quota Breachsense réel (1000 req/mois partagées). "
                "Relancez avec --confirm-live-call si c'est bien l'intention."
            )

        if not settings.BREACHSENSE_LICENSE_KEY:
            raise CommandError(
                "BREACHSENSE_LICENSE_KEY absente : impossible d'enregistrer une cassette réelle."
            )

        # Provider concret instancié directement (pas get_provider()) : cette
        # commande DOIT taper l'API réelle, quel que soit BREACHSENSE_MODE —
        # c'est précisément son rôle, et c'est le seul endroit où c'est vrai.
        provider = BreachsenseProvider()
        result = provider.scan_domain(domain)

        endpoints: dict[str, list] = {}
        for finding in result.findings:
            masked_payload, _seen, _masked, _plain = mask_payload(finding.payload)
            endpoints.setdefault(finding.endpoint, []).append(masked_payload)

        cassette = {
            "domain": domain,
            "recorded_at": datetime.now(UTC).isoformat(),
            "requests_consumed": result.requests_consumed,
            # Rappel explicite dans le fichier lui-même, pour quiconque
            # l'ouvre sans avoir lu l'ADR : les secrets ont déjà été masqués.
            "secrets_masked": True,
            "endpoints": endpoints,
        }

        path = Path(output) if output else cassette_path(domain)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(cassette, handle, ensure_ascii=False, indent=2, sort_keys=True)

        total = sum(len(items) for items in endpoints.values())
        self.stdout.write(
            self.style.SUCCESS(
                f"Cassette enregistrée : {path} "
                f"({total} enregistrements, {result.requests_consumed} requêtes consommées)."
            )
        )
