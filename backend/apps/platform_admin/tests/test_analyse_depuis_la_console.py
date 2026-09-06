"""Lancer une analyse depuis la fiche d'un client, côté exploitant.

Panne de production, constatée le 06/09/2026. Le bouton « Lancer une analyse »
de la fiche client renvoyait systématiquement une erreur. Dans les journaux du
serveur :

    ImportError: cannot import name 'run_breach_scan'
    from 'apps.threat_intelligence.tasks'

La tâche s'appelle ``run_breach_scan_task``. L'import était donc faux **depuis
le premier jour**, et le bouton n'avait jamais fonctionné une seule fois.

Ce qu'il faut retenir n'est pas la faute de frappe, c'est ce qui l'a laissée
passer : l'import était *à l'intérieur* de la branche ``if action == "scan"``.
Tant que personne n'appelle cette action, Python ne lit jamais cette ligne —
ni au démarrage, ni au chargement du module, ni pendant la suite de tests. Ni
ruff, ni un test de la console qui exerce les *autres* actions, ni un import
du module ne pouvaient le voir. Seul un appel réel de CETTE action l'atteint.

Deux autres défauts attendaient immédiatement derrière, invisibles pour la
même raison :

- les arguments de ``.delay()`` étaient positionnels, donc ``job.id`` serait
  arrivé dans ``asset_id`` — le worker aurait cherché un actif n° 42 ;
- l'origine ``platform_admin`` fait 14 caractères pour une colonne qui en
  acceptait 10 : l'écriture du job aurait levé un ``DataError``.

Trois défauts empilés sur un chemin non exercé. C'est la règle générale que ce
fichier tient : **une branche de code jamais appelée par un test n'est pas du
code testé, c'est du code supposé.**
"""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.threat_intelligence.models import BreachIntelligenceUsage, BreachScanJob

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd123"


@pytest.fixture
def staff_client(api_client, user_factory):
    staff = user_factory(email="exploitant-analyse@example.com")
    staff.is_staff = True
    staff.save(update_fields=["is_staff"])
    response = api_client.post(
        reverse("token-obtain-pair"),
        {"email": staff.email, "password": PASSWORD},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api_client


def _url(tenant):
    return reverse("platform-client-actions", args=[tenant.id])


class TestLeBoutonAnalyseFonctionne:
    def test_l_action_aboutit_et_cree_un_job(self, staff_client, tenant):
        """Le test qui manquait. Il échoue sur l'ImportError seul, sans avoir
        besoin de connaître le nom de la tâche : il suffit d'appeler."""
        with patch("apps.threat_intelligence.tasks.run_breach_scan_task.delay") as delay:
            response = staff_client.post(_url(tenant), {"action": "scan"}, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED, (
            f"L'analyse depuis la fiche client doit aboutir. Reçu : {response.status_code} "
            f"— {getattr(response, 'data', None)}"
        )
        assert delay.called, "La tâche d'analyse doit être envoyée au worker."

        job = BreachScanJob.all_objects.get(id=response.data["job_id"])
        assert job.tenant_id == tenant.id
        assert job.status == BreachScanJob.Status.PENDING

    def test_le_job_est_transmis_par_mot_cle_et_pas_par_position(self, staff_client, tenant):
        """Le second défaut. En positionnel, `job.id` atterrissait dans
        `asset_id` : le worker aurait cherché un actif portant le numéro du
        job, n'aurait rien trouvé, et aurait terminé le job en « aucun actif
        à analyser » — un échec silencieux, présenté comme un succès."""
        with patch("apps.threat_intelligence.tasks.run_breach_scan_task.delay") as delay:
            response = staff_client.post(_url(tenant), {"action": "scan"}, format="json")

        assert delay.call_args.args == (), (
            "Aucun argument positionnel : la signature de la tâche est "
            "(tenant_id, asset_id, triggered_by, job_id) et un décalage y est indétectable."
        )
        kwargs = delay.call_args.kwargs
        assert kwargs["tenant_id"] == str(tenant.id)
        assert kwargs["asset_id"] is None, "L'analyse porte sur tous les actifs du client."
        assert kwargs["job_id"] == response.data["job_id"]

    def test_l_origine_tient_dans_sa_colonne(self, staff_client, tenant):
        """Le troisième défaut. « platform_admin » fait 14 caractères ; la
        colonne en acceptait 10. PostgreSQL n'arrondit pas : il refuse."""
        with patch("apps.threat_intelligence.tasks.run_breach_scan_task.delay"):
            response = staff_client.post(_url(tenant), {"action": "scan"}, format="json")

        job = BreachScanJob.all_objects.get(id=response.data["job_id"])
        origine = BreachIntelligenceUsage.TriggeredBy.PLATFORM_ADMIN
        assert job.triggered_by == origine
        for modele in (BreachScanJob, BreachIntelligenceUsage):
            colonne = modele._meta.get_field("triggered_by")
            assert len(origine) <= colonne.max_length, (
                f"{modele.__name__}.triggered_by accepte {colonne.max_length} caractères, "
                f"or « {origine} » en fait {len(origine)} : l'écriture lèvera un DataError."
            )

    def test_l_origine_se_distingue_d_une_analyse_du_client(self, staff_client, tenant):
        """Une analyse lancée par l'exploitant consomme le quota du client. Si
        elle s'enregistrait comme « manuelle », le client verrait son compteur
        descendre sans avoir rien fait, et personne ne pourrait dire pourquoi."""
        assert (
            BreachIntelligenceUsage.TriggeredBy.PLATFORM_ADMIN
            != BreachIntelligenceUsage.TriggeredBy.MANUAL
        )
        with patch("apps.threat_intelligence.tasks.run_breach_scan_task.delay"):
            response = staff_client.post(_url(tenant), {"action": "scan"}, format="json")

        job = BreachScanJob.all_objects.get(id=response.data["job_id"])
        assert job.triggered_by != BreachIntelligenceUsage.TriggeredBy.MANUAL

    def test_l_exploitant_n_est_pas_soumis_au_delai_anti_abus(self, staff_client, tenant):
        """Le délai protège la licence d'un client qui s'acharne sur le bouton.
        L'exploitant qui diagnostique un compte n'est pas ce cas — et il est le
        seul à pouvoir débloquer un client qui vient d'épuiser son délai."""
        from apps.threat_intelligence import services as ti_services

        ti_services.mark_scan_cooldown(tenant)

        with patch("apps.threat_intelligence.tasks.run_breach_scan_task.delay"):
            response = staff_client.post(_url(tenant), {"action": "scan"}, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED


class TestToutesLesActionsDeLaFicheSontAtteignables:
    """La garde générale. Chaque action de la fiche importe ses dépendances
    dans sa propre branche : le défaut d'origine peut se reproduire à
    l'identique dans n'importe laquelle. Appeler chacune au moins une fois est
    la seule façon de le voir.

    Le contrat tenu ici est volontairement minimal — aucune action ne doit
    répondre 500. Ce qu'elles font ensuite relève de leurs tests propres ;
    ce qui compte ici est qu'elles s'exécutent.
    """

    ACTIONS = ["scan", "refresh_synthesis", "purge_secrets"]

    @pytest.mark.parametrize("action", ACTIONS)
    def test_aucune_action_ne_casse_a_l_import(self, staff_client, tenant, action):
        with (
            patch("apps.threat_intelligence.tasks.run_breach_scan_task.delay"),
            patch("apps.ai_assistant.tasks.generate_exposure_synthesis_task.delay"),
        ):
            response = staff_client.post(_url(tenant), {"action": action}, format="json")

        assert response.status_code < 500, (
            f"L'action « {action} » renvoie {response.status_code}. Une erreur serveur ici "
            "signale presque toujours un import ou un appel jamais exercé — c'est exactement "
            "la panne du 06/09/2026."
        )

    def test_la_purge_efface_vraiment_le_secret_et_le_dit(self, staff_client, tenant):
        """Le troisième défaut trouvé par le test générique. Le plus vicieux
        des trois : même une fois le nom de champ corrigé, la purge laissait
        `has_secret` à vrai — l'interface aurait continué d'afficher « mot de
        passe récupérable » sur une fuite dont le secret n'existait plus."""
        from apps.monitoring.models import Asset
        from apps.threat_intelligence.models import BreachFinding

        actif = Asset.all_objects.create(
            tenant=tenant,
            type=Asset.Type.EMAIL_DOMAIN,
            value="purge-console.example",
            ownership_confirmed=True,
        )
        fuite = BreachFinding.all_objects.create(
            tenant=tenant,
            asset=actif,
            source_endpoint=BreachFinding.SourceEndpoint.CREDS,
            finding_type="fuite",
            severity=BreachFinding.Severity.CRITICAL,
            identifier_masked="v***@example.com",
            secret_encrypted=b"blob-chiffre",
            has_secret=True,
            dedup_hash="purge-console-1",
        )

        response = staff_client.post(_url(tenant), {"action": "purge_secrets"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["purged"] == 1

        fuite.refresh_from_db()
        assert bytes(fuite.secret_encrypted) == b""
        assert fuite.has_secret is False, (
            "Un secret effacé doit cesser d'être annoncé comme récupérable."
        )
        assert fuite.secret_purged_at is not None
        assert BreachFinding.all_objects.filter(id=fuite.id).exists(), (
            "La purge efface le mot de passe, pas la fuite : le client doit "
            "continuer de voir qu'il a été compromis."
        )

    def test_la_synthese_envoie_un_identifiant_de_job_ia(self, staff_client, tenant):
        """Le second défaut trouvé par le test ci-dessus. La tâche attend un
        identifiant d'AIJob : lui passer l'UUID du tenant produisait un job
        introuvable côté worker — un 202 suivi de rien du tout."""
        from apps.ai_assistant.models import AIJob

        with patch("apps.ai_assistant.tasks.generate_exposure_synthesis_task.delay") as delay:
            response = staff_client.post(
                _url(tenant), {"action": "refresh_synthesis"}, format="json"
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        job = AIJob.all_objects.get(id=response.data["job_id"])
        assert job.tenant_id == tenant.id
        assert job.use_case == AIJob.UseCase.EXPOSURE_SYNTHESIS
        delay.assert_called_once_with(job.id)
