"""Lot C, point 20 — chaque événement métier qui attendait une notification.

La consigne en nomme cinq, livrés sans moyen de prévenir qui que ce soit :
les demandes de fonctionnalités, les demandes de référentiels, les comptes
désignés, le rapport de comité, la veille. Et côté exploitant : « une demande
client qui arrive doit se voir sans ouvrir la console au bon endroit par
hasard ». Un test par branchement, et pour chacun ce qu'il ne doit PAS faire.

Deux pièges de mise en place, rencontrés au premier passage et corrigés :

- l'exploitant doit EXISTER avant l'événement, sinon « prévenir l'exploitant »
  ne trouve personne — ce qui n'arrive jamais en production ;
- un test « ne prévient personne » n'a de sens que s'il existe quelqu'un qui
  AURAIT pu être prévenu. Sans client, il passait à vide.
"""

from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.access_requests import services as access_services
from apps.access_requests import subjects
from apps.access_requests.models import AccessRequest
from apps.access_requests.tests import test_demandes
from apps.notifications import inbox
from apps.notifications.models import Notification
from apps.regulatory_watch import services as watch_services
from apps.regulatory_watch.models import WatchUpdate
from apps.regulatory_watch.tests import test_veille
from apps.tenants.models import Membership
from apps.threat_intelligence import services as ti_services
from apps.threat_intelligence.tests import test_comptes_designes

pytestmark = pytest.mark.django_db

# Fixtures reprises des tests des apps concernées, par affectation : pytest les
# découvre par leur nom dans le module, et elles restent définies à un seul
# endroit.
non_attribue = test_demandes.non_attribue
exploitant = test_veille.exploitant
source_rss = test_veille.source_rss
suggestion = test_veille.suggestion
offre_avec_comptes = test_comptes_designes.offre_avec_comptes
compte = test_comptes_designes.compte


def _de(user, kind):
    return list(Notification.objects.filter(recipient=user, kind=kind))


class TestDemandes:
    @pytest.fixture
    def demande(self, exploitant, tenant, tenant_owner, non_attribue):
        # `exploitant` d'abord : il doit exister quand la demande arrive.
        return access_services.create_request(
            tenant=tenant,
            user=tenant_owner,
            subject_type=subjects.REFERENTIAL,
            subject_key=non_attribue.slug,
            reason="Notre assureur l'exige.",
        )

    def test_une_demande_qui_arrive_se_voit_dans_la_console(self, exploitant, tenant, demande):
        (notification,) = _de(exploitant, inbox.Kind.ACCESS_REQUEST_NEW)

        assert tenant.name in notification.title
        assert notification.link == "/admin/plateforme?onglet=requests"
        assert notification.tenant is None

    def test_le_client_n_est_pas_prevenu_de_sa_propre_demande(self, demande, tenant_owner):
        assert inbox.unread_count(tenant_owner) == 0

    def test_le_demandeur_apprend_que_quelqu_un_s_en_occupe(
        self, demande, tenant, tenant_owner, exploitant, user_factory
    ):
        collegue = user_factory(email="collegue-demande@example.com")
        Membership.all_objects.create(tenant=tenant, user=collegue, role=Membership.Role.ADMIN)

        access_services.advance_request(
            demande,
            status=AccessRequest.Status.CONTACTED,
            response="Nous vous appelons demain.",
            actor=exploitant,
        )

        (notification,) = _de(tenant_owner, inbox.Kind.ACCESS_REQUEST_UPDATED)
        assert "contacté" in notification.title
        assert notification.body == "Nous vous appelons demain."
        assert notification.link == "/mes-demandes"
        # Seul le demandeur : ses collègues n'ont rien demandé.
        assert _de(collegue, inbox.Kind.ACCESS_REQUEST_UPDATED) == []


class TestComptesDesignes:
    @pytest.fixture(autouse=True)
    def _fournisseur(self, exploitant):
        # `exploitant` ici, dans une fixture automatique : il existe avant que
        # le compte soit déclaré.
        with patch("apps.threat_intelligence.watched_accounts.get_provider") as fabrique:
            fabrique.return_value.scan_email.return_value = test_comptes_designes._fuite_stealer()
            yield fabrique

    def test_l_exploitant_sait_qu_un_compte_a_ete_declare_sans_voir_l_adresse(
        self, exploitant, tenant, compte
    ):
        (notification,) = _de(exploitant, inbox.Kind.WATCHED_ACCOUNT_DECLARED)

        assert tenant.name in notification.title
        assert compte.value not in notification.title
        assert compte.value not in notification.body

    def test_les_nouvelles_fuites_previennent_les_administrateurs(
        self, tenant, tenant_owner, compte
    ):
        ti_services.execute_watched_account_scan(tenant=tenant, accounts=[compte])

        (notification,) = _de(tenant_owner, inbox.Kind.WATCHED_FINDINGS_NEW)
        assert notification.title == "1 nouvelle fuite sur vos comptes surveillés"
        assert notification.link == "/comptes-surveilles"
        assert compte.value not in notification.title + notification.body

    def test_une_analyse_sans_nouveaute_ne_previent_personne(self, tenant, tenant_owner, compte):
        ti_services.execute_watched_account_scan(tenant=tenant, accounts=[compte])
        ti_services.execute_watched_account_scan(tenant=tenant, accounts=[compte])

        assert len(_de(tenant_owner, inbox.Kind.WATCHED_FINDINGS_NEW)) == 1


class TestVeille:
    @pytest.fixture(autouse=True)
    def _un_client_a_prevenir(self, tenant, tenant_owner):
        """Sans client, « personne n'est prévenu » serait vrai par construction."""
        assert inbox.tenant_admins(tenant) == [tenant_owner]

    def test_une_publication_retenue_previent_les_clients(
        self, suggestion, exploitant, tenant, tenant_owner
    ):
        watch_services.review_update(
            suggestion, status=WatchUpdate.Status.KEPT, reviewer=exploitant
        )

        (notification,) = _de(tenant_owner, inbox.Kind.WATCH_UPDATE_PUBLISHED)
        assert notification.link == "/veille"
        assert notification.tenant == tenant

    def test_une_suggestion_ecartee_ne_previent_personne(
        self, suggestion, exploitant, tenant_owner
    ):
        watch_services.review_update(
            suggestion, status=WatchUpdate.Status.DISMISSED, reviewer=exploitant
        )

        assert inbox.unread_count(tenant_owner) == 0

    def test_retenir_puis_integrer_ne_previent_qu_une_fois(
        self, suggestion, exploitant, tenant_owner, referential
    ):
        watch_services.review_update(
            suggestion, status=WatchUpdate.Status.KEPT, reviewer=exploitant
        )
        watch_services.integrate_as_measure(
            suggestion,
            reviewer=exploitant,
            referential=referential,
            domain_code="domaine-a",
            code="V-1",
            official_title="Mesure issue de la veille",
            plain_language="Appliquez la recommandation ?",
        )

        assert len(_de(tenant_owner, inbox.Kind.WATCH_UPDATE_PUBLISHED)) == 1

    def test_une_integration_directe_previent_aussi(
        self, suggestion, exploitant, tenant_owner, referential
    ):
        """Intégrée sans passer par « retenue » : elle devient publique tout de
        même, et le client doit l'apprendre."""
        watch_services.integrate_as_measure(
            suggestion,
            reviewer=exploitant,
            referential=referential,
            domain_code="domaine-a",
            code="V-2",
            official_title="Mesure intégrée directement",
            plain_language="Appliquez la recommandation ?",
        )

        assert len(_de(tenant_owner, inbox.Kind.WATCH_UPDATE_PUBLISHED)) == 1

    def test_une_publication_deja_retenue_re_triee_ne_previent_pas_a_nouveau(
        self, suggestion, exploitant, tenant_owner
    ):
        watch_services.review_update(
            suggestion, status=WatchUpdate.Status.KEPT, reviewer=exploitant, note="premier tri"
        )
        watch_services.review_update(
            suggestion, status=WatchUpdate.Status.KEPT, reviewer=exploitant, note="relu"
        )

        assert len(_de(tenant_owner, inbox.Kind.WATCH_UPDATE_PUBLISHED)) == 1


class TestRapportDeComite:
    def test_le_rapport_du_mois_ecoule_est_signale_une_seule_fois(self, tenant, tenant_owner):
        from apps.notifications import tasks

        tasks.notify_committee_reports()
        tasks.notify_committee_reports()

        (notification,) = _de(tenant_owner, inbox.Kind.COMMITTEE_REPORT_READY)
        mois_ecoule = (timezone.localdate().replace(day=1) - timezone.timedelta(days=1)).month
        assert tasks.MOIS_FR[mois_ecoule - 1] in notification.title
        assert notification.link == "/rapports"

    def test_la_tache_est_planifiee_et_routee_vers_une_file_consommee(self):
        from django.conf import settings

        from config.celery import app

        entree = app.conf.beat_schedule["notifications-committee-reports"]
        assert entree["task"] == "apps.notifications.tasks.notify_committee_reports"
        assert "apps.notifications.tasks.*" in settings.CELERY_TASK_ROUTES
