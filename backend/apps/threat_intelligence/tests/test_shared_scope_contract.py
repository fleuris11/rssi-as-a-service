"""Épinglage du périmètre de findings vu par les consommateurs partagés.

POURQUOI CE FICHIER EXISTE — à lire avant de le supprimer en le prenant pour
un doublon de `test_exposure_feed.py` :

En Phase 8B, `services.list_findings` a reçu un défaut plus restrictif (les
signaux pré-incident — radar, dark web, surface d'attaque — ont été exclus de
la liste « Compromissions »). Ce changement a modifié, **sans faire rougir un
seul test**, le contexte envoyé à l'assistant IA et à la météo quotidienne,
qui voyaient l'ensemble des findings depuis la Phase 7. Le défaut de la
fonction avait changé ; ses appelants, eux, attendaient toujours la vue
complète. Rien ne l'a signalé : aucun test n'affirmait ce que ces deux
contextes devaient contenir.

Ces tests comblent exactement ce trou. Ils n'testent pas « la fonction marche »
(couvert ailleurs) mais **le contrat de périmètre entre modules** : si une
requête en amont est rétrécie (ou élargie) sans que l'appelant soit revu, ils
rougissent. C'est leur seule raison d'être, et c'est suffisant.

Ils s'appuient sur le tenant de démonstration parce qu'il est le seul jeu de
données du dépôt à couvrir **tous** les `source_endpoint` : un jeu de test
ad hoc plus petit laisserait passer précisément le genre de rétrécissement
qu'on veut détecter.
"""

import pytest
from django.core.management import call_command

from apps.ai_assistant import services as ai_services
from apps.notifications import services as notifications_services
from apps.threat_intelligence import services
from apps.threat_intelligence.management.commands.seed_demo_tenant import (
    DEMO_TENANT_SLUG,
    demo_findings_payloads,
)
from apps.threat_intelligence.models import BreachFinding

pytestmark = pytest.mark.django_db

# Le seed couvre tous les endpoints ; on en dérive les attentes plutôt que de
# recopier une liste qui divergerait au premier ajout de payload de démo.
SEEDED_ENDPOINTS = {endpoint for endpoint, _payload, _idx in demo_findings_payloads()}
SEEDED_TOTAL = len(demo_findings_payloads())
PRE_INCIDENT_ENDPOINTS = set(services.PRE_INCIDENT_ENDPOINTS)


@pytest.fixture
def demo_tenant(settings):
    settings.DEBUG = True  # le garde-fou de la commande refuse DEBUG=False
    call_command("seed_demo_tenant", reset=True)
    from apps.tenants.models import Tenant

    return Tenant.objects.get(slug=DEMO_TENANT_SLUG)


class TestSeedCoversEveryEndpoint:
    """Prérequis des tests ci-dessous : si le seed cessait de couvrir un
    endpoint, ils deviendraient silencieusement plus faibles."""

    def test_demo_data_covers_every_source_endpoint(self, demo_tenant):
        seeded = set(
            BreachFinding.all_objects.filter(tenant=demo_tenant).values_list(
                "source_endpoint", flat=True
            )
        )
        assert seeded == SEEDED_ENDPOINTS
        assert PRE_INCIDENT_ENDPOINTS <= seeded, (
            "le jeu de démo doit contenir des signaux pré-incident, sinon "
            "l'épinglage ci-dessous ne détecte plus rien"
        )


class TestAssistantContextScope:
    def test_assistant_sees_the_full_picture_including_pre_incident(self, demo_tenant):
        """L'assistant conseille le dirigeant sur l'ensemble de sa situation :
        lui cacher les signaux d'exposition publique l'amputerait d'une partie
        du raisonnement (c'est le rétrécissement survenu en 8B)."""
        context = ai_services.build_assistant_context(demo_tenant)

        endpoints = {row["type"] for row in context["compromissions_ouvertes"]}
        expected_labels = {
            BreachFinding.SourceEndpoint(e).label for e in PRE_INCIDENT_ENDPOINTS
        }
        assert expected_labels <= endpoints

    def test_assistant_sees_every_open_finding(self, demo_tenant):
        context = ai_services.build_assistant_context(demo_tenant)
        open_count = BreachFinding.all_objects.filter(
            tenant=demo_tenant, status=BreachFinding.Status.OPEN
        ).count()
        assert open_count == SEEDED_TOTAL
        assert len(context["compromissions_ouvertes"]) == open_count


class TestWeatherContextScope:
    def test_weather_sees_the_full_picture_including_pre_incident(self, demo_tenant):
        demo_tenant.ai_enabled = False  # court-circuite l'enrichissement IA
        demo_tenant.save(update_fields=["ai_enabled"])

        context = notifications_services.build_weather_context(demo_tenant)

        labels = {row["source_label"] for row in context["open_breach_findings"]}
        expected_labels = {
            BreachFinding.SourceEndpoint(e).label for e in PRE_INCIDENT_ENDPOINTS
        }
        assert expected_labels <= labels

    def test_weather_sees_every_open_finding(self, demo_tenant):
        demo_tenant.ai_enabled = False
        demo_tenant.save(update_fields=["ai_enabled"])

        context = notifications_services.build_weather_context(demo_tenant)

        assert len(context["open_breach_findings"]) == SEEDED_TOTAL


class TestExposureSynthesisContextScope:
    def test_synthesis_context_sees_the_full_picture(self, demo_tenant):
        """La synthèse raisonne par actif : elle passe par build_exposure_feed,
        qui inclut déjà les signaux pré-incident. Épinglé pour que ce chemin
        reste distinct de celui de la liste."""
        context = ai_services.build_exposure_synthesis_context(demo_tenant)
        assert context["nombre_total_de_fuites_ouvertes"] == SEEDED_TOTAL


class TestFindingsListScope:
    """Le pendant : la liste, elle, DOIT rester restreinte. Sans cette
    assertion, « élargir list_findings pour réparer l'IA » repasserait sans
    bruit et annulerait l'arbitrage de la Phase 8B."""

    def test_list_excludes_pre_incident_by_default(self, demo_tenant):
        endpoints = set(
            services.list_findings(demo_tenant).values_list("source_endpoint", flat=True)
        )
        assert endpoints
        assert not (endpoints & PRE_INCIDENT_ENDPOINTS)

    def test_explicit_flag_restores_the_full_picture(self, demo_tenant):
        endpoints = set(
            services.list_findings(demo_tenant, include_pre_incident=True).values_list(
                "source_endpoint", flat=True
            )
        )
        assert endpoints == SEEDED_ENDPOINTS


class TestCriticalCountScope:
    """Autre consommateur partagé (endpoint « status » du tenant) : il compte
    les fuites critiques ouvertes en interrogeant le modèle directement, donc
    sans passer par list_findings. Épinglé pour que ce périmètre-là aussi soit
    un choix visible et non un effet de bord."""

    def test_critical_count_includes_pre_incident_critical_signals(self, demo_tenant):
        expected = BreachFinding.all_objects.filter(
            tenant=demo_tenant,
            status=BreachFinding.Status.OPEN,
            severity=BreachFinding.Severity.CRITICAL,
        ).count()

        assert services.count_critical_open_findings(demo_tenant) == expected
        assert expected > 0
