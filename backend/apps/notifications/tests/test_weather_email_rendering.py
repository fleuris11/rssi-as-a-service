"""Ce que le dirigeant lit vraiment dans sa météo du matin.

Trois défauts relevés le 04/09/2026 en lisant l'email d'un client RÉEL — pas
en lisant le code. Aucun n'était détectable par les tests existants, qui
vérifiaient que l'email partait, jamais ce qu'il contenait.

1. **Le plus grave tombait hors du courrier.** Le contexte coupait aux 20
   premières fuites dans l'ordre de la base, avant tout tri. Sur 137 fuites,
   l'email n'affichait que de la « surface d'attaque » — la catégorie la moins
   grave — pendant que les deux sessions compromises (critique) n'y étaient
   pas. C'est l'inverse exact de la promesse du produit.

2. **Vingt lignes rigoureusement identiques.** Même actif, même catégorie,
   même gravité, vingt fois. Elles n'apprennent rien de plus que « il y en a
   vingt », et elles noient ce qui compte.

3. **`Surface d&#x27;attaque`** dans la version TEXTE. Django échappe le HTML
   par défaut, y compris pour un gabarit `.txt` : l'apostrophe arrivait
   encodée chez le client.
"""

import pytest
from django.template.loader import render_to_string

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset
from apps.notifications import services
from apps.threat_intelligence.models import BreachFinding


@pytest.fixture
def website_asset(tenant, tenant_owner):
    return monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://example.com",
        ownership_confirmed=True,
    )


def _finding(tenant, asset, *, severity, endpoint, identifier=""):
    return BreachFinding.all_objects.create(
        tenant=tenant,
        asset=asset,
        source_endpoint=endpoint,
        severity=severity,
        status=BreachFinding.Status.OPEN,
        identifier_masked=identifier,
        dedup_hash=f"{endpoint}-{severity}-{identifier}-{BreachFinding.all_objects.count()}",
    )


@pytest.mark.django_db
class TestOrdreEtRegroupement:
    def test_le_plus_grave_arrive_en_premier(self, tenant, website_asset):
        """Le défaut n°1, dans sa forme minimale : beaucoup de peu grave,
        un seul critique, et il doit être en tête.

        ORDRE DE CRÉATION IMPORTANT : le critique est créé EN PREMIER, donc
        en dernier dans l'ordre naturel de ``list_findings`` (par date
        décroissante). Une première version de ce test le créait en dernier —
        il passait alors même sans le tri, parce que la date le remontait
        toute seule. Il ne prouvait rien. Vérifié depuis en retirant le tri :
        sans lui, ce test échoue.
        """
        _finding(tenant, website_asset, severity="critical", endpoint="sessions", identifier="crit")
        for i in range(12):
            _finding(
                tenant, website_asset, severity="attention", endpoint="asm", identifier=f"a{i}"
            )

        lignes = services.build_weather_context(tenant)["open_breach_findings"]

        assert lignes[0]["severity_label"] == "Critique", (
            "La ligne critique doit ouvrir la liste ; sinon elle sort de l'email "
            "dès qu'il y a plus de quelques fuites."
        )

    def test_aucune_gravite_haute_n_est_perdue_par_la_troncature(self, tenant, website_asset):
        # Idem : la ligne « élevée » est créée en premier, donc la plus
        # ancienne — c'est précisément le cas que l'ancienne troncature
        # perdait.
        _finding(tenant, website_asset, severity="high", endpoint="creds", identifier="eleve")
        for i in range(40):
            _finding(
                tenant, website_asset, severity="attention", endpoint="asm", identifier=f"a{i}"
            )

        lignes = services.build_weather_context(tenant)["open_breach_findings"]

        assert any(ligne["severity_label"] == "Élevée" for ligne in lignes)
        assert len(lignes) <= services.WEATHER_MAX_BREACH_ROWS

    def test_les_lignes_identiques_sont_regroupees_avec_leur_nombre(self, tenant, website_asset):
        for _ in range(5):
            _finding(tenant, website_asset, severity="attention", endpoint="asm")

        contexte = services.build_weather_context(tenant)
        lignes = contexte["open_breach_findings"]

        assert len(lignes) == 1, "Cinq lignes identiques ne valent qu'une ligne et un compte."
        assert lignes[0]["count"] == 5
        assert contexte["breach_total"] == 5

    def test_le_total_annonce_est_celui_de_toutes_les_fuites(self, tenant, website_asset):
        for i in range(30):
            _finding(tenant, website_asset, severity="high", endpoint="creds", identifier=f"e{i}")

        contexte = services.build_weather_context(tenant)

        assert contexte["breach_total"] == 30
        # Le client doit savoir qu'il ne voit pas tout, et où voir le reste.
        assert contexte["breach_hidden"] > 0


@pytest.mark.django_db
class TestRenduDesGabarits:
    def test_la_version_texte_n_echappe_pas_le_html(self, tenant, website_asset):
        """Le défaut n°3 : « Surface d&#x27;attaque » chez le client."""
        _finding(tenant, website_asset, severity="attention", endpoint="asm")

        corps = render_to_string(
            "notifications/weather_email.txt", services.build_weather_context(tenant)
        )

        assert "&#x27;" not in corps and "&amp;" not in corps and "&quot;" not in corps
        assert "'" in corps, "Une apostrophe réelle doit apparaître, pas son entité."

    def test_les_deux_versions_annoncent_le_meme_total(self, tenant, website_asset):
        for i in range(15):
            _finding(tenant, website_asset, severity="high", endpoint="creds", identifier=f"e{i}")
        contexte = services.build_weather_context(tenant)

        texte = render_to_string("notifications/weather_email.txt", contexte)
        html = render_to_string("notifications/weather_email.html", contexte)

        assert "15" in texte and "15" in html

    def test_aucun_terme_interne_ne_figure_dans_la_meteo(self, tenant, website_asset):
        """Le client lit son exposition, pas notre chaîne d'approvisionnement."""
        _finding(tenant, website_asset, severity="critical", endpoint="sessions")
        contexte = services.build_weather_context(tenant)

        for gabarit in ("weather_email.txt", "weather_email.html"):
            corps = render_to_string(f"notifications/{gabarit}", contexte).lower()
            for terme in ("breachsense", "anthropic", "claude", "celery", "traceback"):
                assert terme not in corps, f"« {terme} » apparaît dans {gabarit}"
