"""Une analyse lancée doit rester visible, même après un changement d'écran.

Remonté par le client en production le 06/09/2026, en trois questions qui
n'en font qu'une :

    « quand l'analyse est lancée ça ne me dit pas si c'est terminé ou pas,
      ça me met juste analyse en cours, et si je change d'écran je ne sais
      pas si l'analyse s'arrête ou pas »

Techniquement, l'analyse ne s'arrête jamais : elle tourne dans un worker
Celery, indépendante de l'onglet qui l'a déclenchée. Mais l'écran n'en savait
rien. L'état « analyse en cours » vivait dans une variable du composant React,
détruite au démontage, et la boucle d'interrogation s'arrêtait avec elle. Le
client revenait sur la page et ne voyait plus rien : ni « en cours », ni
« terminée », ni résultat. Il relançait — et tombait sur le délai anti-abus,
qui lui refusait l'analyse qu'il croyait avoir perdue.

Le correctif ne touche pas au worker, qui faisait déjà son travail : il rend
le job interrogeable depuis l'état du tenant, pour que l'écran puisse
retrouver une analyse en cours à chaque chargement. Deux champs, deux
questions :

- ``running_scan_id`` — est-ce que ça tourne en ce moment ?
- ``last_scan_finished_at`` — et sinon, quand est-ce que ça a fini ?

Sans le second, une page sans analyse en cours est indiscernable d'une page
où rien n'a jamais été lancé.
"""

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.threat_intelligence import services
from apps.threat_intelligence.models import BreachIntelligenceUsage, BreachScanJob

pytestmark = pytest.mark.django_db


def _auth(api_client, user, tenant):
    response = api_client.post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": "Str0ng!Passw0rd123"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    return {
        "HTTP_AUTHORIZATION": f"Bearer {response.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


def _statut(api_client, user, tenant):
    response = api_client.get(
        reverse("threat-intelligence-status"), **_auth(api_client, user, tenant)
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data


def _job(tenant, statut, **extra):
    return BreachScanJob.all_objects.create(
        tenant=tenant,
        status=statut,
        triggered_by=BreachIntelligenceUsage.TriggeredBy.MANUAL,
        **extra,
    )


class TestUneAnalyseEnCoursSeRetrouve:
    def test_sans_analyse_le_champ_est_vide(self, api_client, tenant, tenant_owner):
        assert _statut(api_client, tenant_owner, tenant)["running_scan_id"] is None

    def test_une_analyse_en_attente_est_signalee(self, api_client, tenant, tenant_owner):
        """« En attente » compte autant que « en cours » : entre le clic et la
        prise en charge par le worker, il s'écoule un instant pendant lequel
        le client ne doit pas voir la page redevenir vierge."""
        job = _job(tenant, BreachScanJob.Status.PENDING)

        assert _statut(api_client, tenant_owner, tenant)["running_scan_id"] == job.id

    def test_une_analyse_en_cours_est_signalee(self, api_client, tenant, tenant_owner):
        job = _job(tenant, BreachScanJob.Status.RUNNING)

        assert _statut(api_client, tenant_owner, tenant)["running_scan_id"] == job.id

    def test_une_analyse_terminee_ne_l_est_plus(self, api_client, tenant, tenant_owner):
        """Sinon l'écran resterait bloqué sur « analyse en cours » pour
        toujours — l'inverse exact du défaut, tout aussi trompeur."""
        _job(tenant, BreachScanJob.Status.DONE, finished_at=timezone.now())

        assert _statut(api_client, tenant_owner, tenant)["running_scan_id"] is None

    def test_une_analyse_en_echec_ne_bloque_pas_l_ecran(self, api_client, tenant, tenant_owner):
        _job(tenant, BreachScanJob.Status.FAILED, finished_at=timezone.now())

        assert _statut(api_client, tenant_owner, tenant)["running_scan_id"] is None


class TestLaDerniereAnalyseTerminee:
    def test_la_date_de_fin_est_exposee(self, api_client, tenant, tenant_owner):
        job = _job(tenant, BreachScanJob.Status.DONE, finished_at=timezone.now())

        donnees = _statut(api_client, tenant_owner, tenant)

        assert donnees["last_scan_finished_at"] is not None
        assert donnees["last_scan_finished_at"].replace(tzinfo=None) == job.finished_at.replace(
            tzinfo=None
        )

    def test_c_est_bien_la_plus_recente(self, api_client, tenant, tenant_owner):
        ancienne = timezone.now() - timezone.timedelta(days=3)
        _job(tenant, BreachScanJob.Status.DONE, finished_at=ancienne)
        recente = _job(tenant, BreachScanJob.Status.DONE, finished_at=timezone.now())

        donnees = _statut(api_client, tenant_owner, tenant)

        assert donnees["last_scan_finished_at"].replace(tzinfo=None) == recente.finished_at.replace(
            tzinfo=None
        )

    def test_une_analyse_ratee_ne_compte_pas_comme_terminee(self, api_client, tenant, tenant_owner):
        """« Dernière analyse terminée le… » doit désigner une analyse qui a
        abouti. Afficher la date d'un échec ferait croire au client que ses
        résultats datent de ce moment-là."""
        _job(tenant, BreachScanJob.Status.FAILED, finished_at=timezone.now())

        assert _statut(api_client, tenant_owner, tenant)["last_scan_finished_at"] is None


class TestLeSuiviResteCloisonne:
    def test_l_analyse_d_un_autre_client_est_invisible(
        self, api_client, tenant, tenant_owner, other_tenant
    ):
        """Le suivi d'analyse est un nouveau champ exposé au client : il passe
        par la même règle que tout le reste. Un tenant ne doit pas déduire de
        cet écran qu'une analyse tourne chez quelqu'un d'autre."""
        _job(other_tenant, BreachScanJob.Status.RUNNING)
        _job(other_tenant, BreachScanJob.Status.DONE, finished_at=timezone.now())

        donnees = _statut(api_client, tenant_owner, tenant)

        assert donnees["running_scan_id"] is None
        assert donnees["last_scan_finished_at"] is None


class TestLesServicesDirectement:
    def test_la_plus_recente_analyse_en_cours_l_emporte(self, tenant):
        """Deux analyses en cours ne devraient pas exister — le délai
        anti-abus l'empêche — mais si cela arrive, l'écran doit suivre la
        dernière lancée, pas une ancienne restée bloquée."""
        _job(tenant, BreachScanJob.Status.RUNNING)
        derniere = _job(tenant, BreachScanJob.Status.PENDING)

        assert services.get_running_scan_job(tenant).id == derniere.id

    def test_une_analyse_terminee_sans_date_est_ignoree(self, tenant):
        """Défense contre une donnée incohérente : un job marqué terminé sans
        date de fin ferait afficher « Dernière analyse terminée le null »."""
        _job(tenant, BreachScanJob.Status.DONE, finished_at=None)

        assert services.get_last_finished_scan_job(tenant) is None
