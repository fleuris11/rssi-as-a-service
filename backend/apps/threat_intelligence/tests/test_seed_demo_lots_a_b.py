"""Lots A et B — le jeu de démonstration montre ce que les écrans savent faire.

Un écran de démonstration vide ne vend rien, et un écran rempli par insertion
directe en base finit par montrer ce que le produit ne fait pas. D'où trois
règles, tenues ici :

1. le compte surveillé est DÉCLARÉ par le service et ses observations passent
   par l'ingestion réelle — la démonstration obéit aux mêmes gardes qu'un
   client ;
2. elle montre ce qui distingue les écrans : l'historique du premier passage
   et les nouveautés, des groupes à plusieurs occurrences, du traité et de
   l'écarté, un second référentiel propre au client ;
3. elle ne fabrique RIEN de commun à tous les clients. La veille est partagée :
   une publication de démonstration apparaîtrait chez les vrais clients.
"""

import pytest
from django.core.management import call_command

from apps.assessments import services as assessments_services
from apps.regulatory_watch.models import WatchUpdate
from apps.tenants.models import Tenant
from apps.threat_intelligence import services as ti_services
from apps.threat_intelligence.management.commands.seed_demo_tenant import (
    DEMO_TENANT_SLUG,
    DEMO_WATCHED_ACCOUNT,
    demo_watched_history,
    demo_watched_new,
)
from apps.threat_intelligence.models import WatchedAccount, WatchedAccountFinding

pytestmark = pytest.mark.django_db

SLUG_REFERENTIEL = f"{DEMO_TENANT_SLUG}-exigences-assureur"


@pytest.fixture(autouse=True)
def _debug_on(settings):
    # Même précaution que test_seed_demo_tenant : le garde-fou de la commande
    # refuse de tourner hors DEBUG, et il est testé à part.
    settings.DEBUG = True


def _demo():
    return Tenant.objects.get(slug=DEMO_TENANT_SLUG)


class TestComptesSurveillesDeDemonstration:
    def test_le_compte_est_declare_par_le_service(self):
        call_command("seed_demo_tenant")

        compte = WatchedAccount.all_objects.get(tenant=_demo(), value=DEMO_WATCHED_ACCOUNT)
        # La déclaration figée par le service, pas un compte inséré à la main.
        assert compte.declaration_text
        assert compte.legal_basis == WatchedAccount.LegalBasis.CONSENT
        # Domaine réservé : aucune personne réelle ne porte cette adresse.
        assert compte.value.endswith("@example.org")

    def test_distingue_l_historique_des_nouveautes(self):
        call_command("seed_demo_tenant")

        observations = WatchedAccountFinding.all_objects.filter(tenant=_demo())
        assert observations.filter(from_first_scan=True).count() == len(demo_watched_history())
        assert observations.filter(from_first_scan=False).count() == len(demo_watched_new())

    def test_le_regroupement_se_voit(self):
        call_command("seed_demo_tenant")

        groupes = ti_services.group_watched_account_findings(
            ti_services.list_watched_account_findings(_demo())
        )
        assert len(groupes) > 1
        assert any(groupe["occurrences"] > 1 for groupe in groupes)

    def test_montre_du_traite_et_de_l_ecarte(self):
        call_command("seed_demo_tenant")

        resume = ti_services.watched_accounts_summary(_demo())
        assert resume["treated_findings"] >= 1
        assert resume["ignored_findings"] >= 1
        assert resume["from_first_scan"] >= 1
        assert resume["since_first_scan"] >= 1

    def test_rejouer_ne_duplique_rien(self):
        call_command("seed_demo_tenant")
        avant = WatchedAccountFinding.all_objects.filter(tenant=_demo()).count()

        call_command("seed_demo_tenant")

        assert WatchedAccountFinding.all_objects.filter(tenant=_demo()).count() == avant
        assert WatchedAccount.all_objects.filter(tenant=_demo()).count() == 1

    def test_la_remise_a_zero_reconstruit_la_demonstration(self):
        call_command("seed_demo_tenant")
        avant = WatchedAccountFinding.all_objects.filter(tenant=_demo()).count()

        call_command("seed_demo_tenant", reset=True)

        assert WatchedAccountFinding.all_objects.filter(tenant=_demo()).count() == avant
        assert WatchedAccount.all_objects.filter(tenant=_demo()).count() == 1


class TestReferentielsDeDemonstration:
    def test_un_referentiel_propre_au_client_de_demonstration(self):
        call_command("seed_demo_tenant")

        referentiel = assessments_services.get_referential(slug=SLUG_REFERENTIEL)
        assert referentiel.kind == "custom"
        assert referentiel.owner_tenant_id == _demo().id
        assert assessments_services.is_granted(_demo(), referentiel)

    def test_il_reste_invisible_des_autres_clients(self):
        call_command("seed_demo_tenant")
        # Créé directement, et non par la fabrique des tests : celle-ci
        # attribue d'office les référentiels déjà en base.
        autre = Tenant.objects.create(name="Autre client", slug="autre-client-demo")

        proposables = [r.slug for r in assessments_services.assignable_referentials(autre)]
        assert SLUG_REFERENTIEL not in proposables

    def test_aucune_publication_de_veille_n_est_fabriquee(self):
        """La veille est commune à tous les clients : une publication de
        démonstration apparaîtrait chez les vrais."""
        avant = WatchUpdate.objects.count()

        call_command("seed_demo_tenant")

        assert WatchUpdate.objects.count() == avant
