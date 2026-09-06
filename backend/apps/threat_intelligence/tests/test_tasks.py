from unittest.mock import patch

import pytest

from apps.threat_intelligence import client_messages, services
from apps.threat_intelligence.models import BreachScanJob
from apps.threat_intelligence.tasks import run_breach_scan_task

pytestmark = pytest.mark.django_db


class TestRunBreachScanTask:
    def test_initial_trigger_without_job_still_scans(self, tenant, website_asset, fake_provider):
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            result = run_breach_scan_task(
                tenant_id=str(tenant.id), asset_id=website_asset.id, triggered_by="initial"
            )
        assert result["findings_created"] == 0

    def test_manual_trigger_with_job_marks_it_done(self, tenant, website_asset, fake_provider):
        job = services.create_scan_job(
            tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
        )
        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            run_breach_scan_task(
                tenant_id=str(tenant.id),
                asset_id=website_asset.id,
                triggered_by="manual",
                job_id=job.id,
            )

        job.refresh_from_db()
        assert job.status == BreachScanJob.Status.DONE

    def test_redelivery_of_finished_job_is_a_noop(self, tenant, website_asset, fake_provider):
        job = services.create_scan_job(
            tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
        )
        services.mark_job_done(job)

        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            result = run_breach_scan_task(
                tenant_id=str(tenant.id),
                asset_id=website_asset.id,
                triggered_by="manual",
                job_id=job.id,
            )

        assert result is None

    def test_unknown_tenant_returns_none(self):
        result = run_breach_scan_task(tenant_id="00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_no_scannable_assets_marks_job_done_with_zero_findings(self, tenant):
        job = services.create_scan_job(tenant=tenant, triggered_by=services.TriggeredBy.MANUAL)

        run_breach_scan_task(tenant_id=str(tenant.id), triggered_by="manual", job_id=job.id)

        job.refresh_from_db()
        assert job.status == BreachScanJob.Status.DONE
        assert job.result_ref["findings_created"] == 0

    def test_failure_marks_job_failed_after_retries_exhausted(self, tenant, website_asset):
        job = services.create_scan_job(
            tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
        )
        # Simulates the task's own last attempt (retries == max_retries) via
        # Celery's request-context push, instead of mocking .retry() itself —
        # .retry() normally raises a control-flow Retry exception the worker
        # catches, so mocking it to raise plainly would misrepresent what
        # "retries exhausted" actually looks like to this code.
        run_breach_scan_task.push_request(retries=run_breach_scan_task.max_retries)
        try:
            with patch(
                "apps.threat_intelligence.services.execute_scan",
                side_effect=RuntimeError("boom"),
            ):
                run_breach_scan_task(
                    tenant_id=str(tenant.id),
                    asset_id=website_asset.id,
                    triggered_by="manual",
                    job_id=job.id,
                )
        finally:
            run_breach_scan_task.pop_request()

        job.refresh_from_db()
        assert job.status == BreachScanJob.Status.FAILED
        # Ce test affirmait l'inverse — « boom » DANS error_message — et
        # verrouillait donc la fuite : ce champ est sérialisé vers le client
        # (BreachScanJobSerializer), et il y affichait le texte brut de
        # l'exception du fournisseur. Le détail vit dans les journaux.
        assert "boom" not in job.error_message
        assert job.error_message == client_messages.SCAN_FAILED

    def test_transient_failure_retries_before_exhaustion(self, tenant, website_asset):
        job = services.create_scan_job(
            tenant=tenant, asset=website_asset, triggered_by=services.TriggeredBy.MANUAL
        )
        with (
            patch(
                "apps.threat_intelligence.services.execute_scan",
                side_effect=RuntimeError("transient"),
            ),
            patch.object(
                run_breach_scan_task, "retry", side_effect=RuntimeError("retry-triggered")
            ) as mock_retry,
            pytest.raises(RuntimeError, match="retry-triggered"),
        ):
            run_breach_scan_task(
                tenant_id=str(tenant.id),
                asset_id=website_asset.id,
                triggered_by="manual",
                job_id=job.id,
            )

        mock_retry.assert_called_once()
        job.refresh_from_db()
        # Not marked failed yet — a retry is still pending, per CLAUDE.md's
        # idempotent/retryable task guidance.
        assert job.status == BreachScanJob.Status.RUNNING


class TestAnalyseLanceeParLExploitant:
    """L'origine `platform_admin` traverse la tâche, `execute_scan`, puis
    l'écriture de l'usage. Les tests de la console bouchonnent `.delay` et
    s'arrêtent à l'envoi : personne ne parcourait la chaîne complète.

    Ce que ces tests garantissent, précisément : l'analyse aboutit avec cette
    origine, elle parcourt tous les actifs du client, et elle laisse une ligne
    d'usage portant la bonne origine — une analyse de l'exploitant consomme la
    licence, elle doit donc se compter comme les autres.

    Ce qu'ils NE garantissent PAS, et il faut le dire : la base de test est
    construite depuis les migrations, donc un `max_length` réduit dans le
    modèle sans migration ne provoque ici aucune erreur. La correspondance
    entre le modèle et la longueur réelle des valeurs est vérifiée au niveau
    Python, dans `platform_admin/tests/test_analyse_depuis_la_console.py`
    (`test_l_origine_tient_dans_sa_colonne`). Vérifié en réintroduisant le
    défaut : ce fichier-ci reste vert, l'autre tombe.
    """

    def test_l_analyse_de_l_exploitant_va_jusqu_a_l_ecriture_de_l_usage(
        self, tenant, website_asset, fake_provider
    ):
        from apps.threat_intelligence.models import BreachIntelligenceUsage

        origine = BreachIntelligenceUsage.TriggeredBy.PLATFORM_ADMIN
        job = services.create_scan_job(tenant=tenant, asset=None, triggered_by=origine)

        with patch("apps.threat_intelligence.services.get_provider", return_value=fake_provider):
            run_breach_scan_task(
                tenant_id=str(tenant.id), asset_id=None, triggered_by=origine, job_id=job.id
            )

        job.refresh_from_db()
        assert job.status == BreachScanJob.Status.DONE

        usage = BreachIntelligenceUsage.all_objects.filter(tenant=tenant).order_by("-id").first()
        assert usage is not None, "L'analyse de l'exploitant consomme la licence : elle se compte."
        assert usage.triggered_by == origine

    def test_l_analyse_de_l_exploitant_porte_sur_tous_les_actifs(
        self, tenant, tenant_owner, website_asset, fake_provider
    ):
        """`asset_id=None` signifie « tous les actifs », pas « aucun ».

        Ce test devait au départ démontrer qu'un `job.id` arrivé par erreur
        dans `asset_id` ne trouvait aucun actif. Il a échoué — et pour une
        raison qui vaut mieux que la démonstration prévue : les deux
        identifiants sont de petits entiers issus de séquences distinctes,
        et ils se rencontrent. Ici, `job.id` valait exactement l'identifiant
        d'un actif existant.

        Le décalage d'arguments n'aurait donc pas produit une erreur visible :
        il aurait analysé **un autre actif que celui demandé**, en silence, et
        facturé la requête au client. Un défaut qui se voit est un défaut
        facile ; celui-là ne se voyait pas.

        D'où le contrat tenu ici, formulé en positif : une analyse sans actif
        précis les parcourt TOUS.
        """
        from apps.monitoring import services as monitoring_services
        from apps.monitoring.models import Asset
        from apps.threat_intelligence.models import BreachIntelligenceUsage

        second = monitoring_services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="second-actif.example",
            ownership_confirmed=True,
        )
        attendus = services.scannable_assets(tenant)
        assert len(attendus) >= 2, "Prérequis : les deux actifs doivent être analysables."

        origine = BreachIntelligenceUsage.TriggeredBy.PLATFORM_ADMIN
        job = services.create_scan_job(tenant=tenant, asset=None, triggered_by=origine)

        vus = []
        provider = fake_provider
        original = provider.scan_domain

        def tracer(domain):
            vus.append(domain)
            return original(domain)

        provider.scan_domain = tracer

        with patch("apps.threat_intelligence.services.get_provider", return_value=provider):
            run_breach_scan_task(
                tenant_id=str(tenant.id), asset_id=None, triggered_by=origine, job_id=job.id
            )

        job.refresh_from_db()
        assert job.status == BreachScanJob.Status.DONE
        # Comparaison sur le NOMBRE d'actifs atteints : le provider reçoit le
        # nom d'hôte (« example.com »), pas la valeur brute de l'actif
        # (« https://example.com »). Ce qui compte ici est qu'ils soient tous
        # parcourus, pas la forme exacte de ce qui leur est transmis.
        assert len(set(vus)) == len(attendus), (
            f"L'analyse de l'exploitant doit parcourir les {len(attendus)} actifs du "
            f"client ; {len(set(vus))} atteint(s) : {sorted(set(vus))}."
        )
        assert second.value in vus or second.value.removeprefix("https://") in vus
