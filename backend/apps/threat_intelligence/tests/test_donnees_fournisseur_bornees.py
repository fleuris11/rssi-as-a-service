"""Une donnée venue du fournisseur ne doit jamais faire tomber une analyse.

Panne réelle du 06/09/2026, sur le client de production. Une analyse lancée
depuis l'espace client a échoué entièrement :

    DataError: value too long for type character varying(60)

``finding_type`` est repris **tel quel** de la charge Breachsense — un nom de
logiciel malveillant, une catégorie, un type de contenu. Rien n'en garantit la
longueur, et la colonne en accepte 60. Une seule valeur trop longue a suffi à
perdre :

- les fuites des DEUX autres actifs du même client, déjà récupérées ;
- une quarantaine de requêtes de la licence, réellement consommées ;
- et, comme ``record_usage`` n'était jamais atteint, leur comptabilisation —
  le budget de la plateforme était donc faux, à la baisse.

Trois défauts en un, et ils demandent trois gardes distinctes :

1. **Borner à la frontière** — le seul endroit où une donnée étrangère entre.
2. **Isoler chaque actif** — un lot qui perd tout à cause d'un élément est un
   lot mal conçu.
3. **Compter l'usage même en échec** — un scan raté coûte exactement aussi
   cher qu'un scan réussi.
"""

from unittest.mock import patch

import pytest

from apps.threat_intelligence import services
from apps.threat_intelligence.models import BreachFinding
from apps.threat_intelligence.providers.base import RawFinding, ScanResult
from apps.threat_intelligence.providers.breachsense import normalizer


class TestLesBornesSuiventLeModele:
    """Le normalizer ne peut pas lire les modèles Django (ADR-013 : la couche
    fournisseur reste ignorante de la persistance). Ses bornes sont donc des
    constantes — et une constante recopiée diverge un jour. Ce test est le
    lien qui manque."""

    @pytest.mark.parametrize(
        "constante,champ",
        [
            (normalizer.MAX_FINDING_TYPE, "finding_type"),
            (normalizer.MAX_IDENTIFIER, "identifier_plain"),
            (normalizer.MAX_IDENTIFIER, "identifier_masked"),
            (normalizer.MAX_SECRET_MASKED, "secret_masked"),
        ],
    )
    def test_chaque_borne_vaut_le_max_length_de_sa_colonne(self, constante, champ):
        colonne = BreachFinding._meta.get_field(champ)
        assert constante == colonne.max_length, (
            f"La borne du normalizer pour « {champ} » ({constante}) ne correspond plus "
            f"au modèle ({colonne.max_length}). Une analyse échouera en production sur "
            "un DataError dès qu'une valeur dépassera la plus petite des deux."
        )


class TestUneValeurTropLongueNeCasseRien:
    def test_un_type_de_fuite_interminable_est_tronque(self):
        """Le cas exact de la panne : `mal` (nom du malware) démesuré."""
        charge = {"usr": "a@example.com", "mal": "X" * 400, "src": "fuite", "fnd": "2026-01-01"}

        resultat = normalizer.normalize_finding("stealer", charge)

        assert len(resultat["finding_type"]) == normalizer.MAX_FINDING_TYPE
        assert resultat["finding_type"].startswith("XXX")

    def test_un_identifiant_interminable_est_tronque(self):
        charge = {"eml": ("b" * 300) + "@example.com", "src": "fuite"}

        resultat = normalizer.normalize_finding("creds", charge)

        assert len(resultat["identifier_masked"]) <= normalizer.MAX_IDENTIFIER

    def test_la_troncature_ne_vide_jamais_le_champ(self):
        """Tronquer, pas effacer : une fuite dont le nom de malware est long
        reste une fuite, et son type reste lisible."""
        charge = {"usr": "a@example.com", "mal": "RedLine Stealer " * 20}

        resultat = normalizer.normalize_finding("stealer", charge)

        assert resultat["finding_type"].startswith("RedLine Stealer")

    def test_une_valeur_courte_reste_intacte(self):
        charge = {"usr": "a@example.com", "mal": "RedLine"}
        resultat = normalizer.normalize_finding("stealer", charge)
        assert resultat["finding_type"] == "RedLine"


@pytest.mark.django_db
class TestUnActifEnEchecNEmporteePasLesAutres:
    def _provider(self, echecs: set[str]):
        class FauxProvider:
            def scan_domain(self, domain):
                if domain in echecs:
                    raise RuntimeError(f"le fournisseur refuse {domain}")
                return ScanResult(
                    findings=[RawFinding(endpoint="creds", payload={"eml": f"x@{domain}"})],
                    requests_consumed=9,
                    remaining_quota=None,
                )

        return FauxProvider()

    def test_les_fuites_des_autres_actifs_sont_conservees(
        self, tenant, tenant_owner, website_asset
    ):
        from apps.monitoring import services as monitoring_services
        from apps.monitoring.models import Asset

        sain = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="sain.example",
            ownership_confirmed=True,
        )
        casse = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="casse.example",
            ownership_confirmed=True,
        )

        with patch.object(services, "get_provider", return_value=self._provider({"casse.example"})):
            resultat = services.execute_scan(
                tenant=tenant, assets=[sain, casse], triggered_by=services.TriggeredBy.INITIAL
            )

        assert resultat["findings_created"] == 1, (
            "La fuite de l'actif sain doit survivre à l'échec de l'autre."
        )
        assert resultat["assets_en_echec"] == ["casse.example"]

    def test_les_requetes_consommees_sont_comptees_malgre_l_echec(
        self, tenant, tenant_owner, website_asset
    ):
        """Un scan raté coûte aussi cher qu'un scan réussi. Ne pas compter ces
        requêtes fausse le budget de la plateforme, à la baisse — et la garde
        de capacité avec lui."""
        from apps.monitoring import services as monitoring_services
        from apps.monitoring.models import Asset
        from apps.threat_intelligence.models import BreachIntelligenceUsage

        sain = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="sain2.example",
            ownership_confirmed=True,
        )
        casse = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="casse2.example",
            ownership_confirmed=True,
        )

        with patch.object(
            services, "get_provider", return_value=self._provider({"casse2.example"})
        ):
            services.execute_scan(
                tenant=tenant, assets=[sain, casse], triggered_by=services.TriggeredBy.INITIAL
            )

        usage = BreachIntelligenceUsage.all_objects.filter(tenant=tenant).order_by("-id").first()
        assert usage is not None, "L'usage doit être enregistré même en échec partiel."
        assert usage.requests_consumed == 9

    def test_si_tout_echoue_l_analyse_est_bien_un_echec(self, tenant, tenant_owner):
        """Un échec partiel produit des résultats exploitables et n'est pas un
        échec. Un échec total n'a rien à montrer : il doit se présenter comme
        tel, sinon le client voit « analyse terminée » et un espace vide."""
        from apps.monitoring import services as monitoring_services
        from apps.monitoring.models import Asset

        casse = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="tout-casse.example",
            ownership_confirmed=True,
        )

        with patch.object(
            services, "get_provider", return_value=self._provider({"tout-casse.example"})
        ):
            with pytest.raises(services.ThreatIntelligenceError):
                services.execute_scan(
                    tenant=tenant,
                    assets=[casse],
                    triggered_by=services.TriggeredBy.INITIAL,
                )


@pytest.mark.django_db
class TestJusquALaBase:
    """Le test qui aurait attrapé la panne. Les précédents s'arrêtent au
    normalizer ; celui-ci va jusqu'à l'écriture, là où PostgreSQL a refusé."""

    def test_une_fuite_au_type_demesure_s_enregistre(self, tenant, website_asset):
        brute = RawFinding(
            endpoint="stealer",
            payload={
                "usr": "victime@example.com",
                # 400 caractères : la charge réelle qui a fait tomber
                # l'analyse en portait suffisamment pour dépasser 60.
                "mal": "Trojan.Generic.VeryLongMalwareFamilyName " * 10,
                "src": "fuite-2026",
            },
        )

        creees = services.ingest_raw_findings(
            tenant=tenant, asset=website_asset, raw_findings=[brute]
        )

        assert len(creees) == 1, (
            "Une valeur trop longue ne doit plus empêcher l'enregistrement : "
            "c'est exactement le DataError du 06/09/2026."
        )
        finding = BreachFinding.all_objects.get(id=creees[0].id)
        assert len(finding.finding_type) <= normalizer.MAX_FINDING_TYPE
        assert finding.finding_type.startswith("Trojan.Generic")
