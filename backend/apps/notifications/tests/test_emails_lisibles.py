"""Ce que le dirigeant doit pouvoir faire de ces emails, sans être technicien.

Refonte du 04/09/2026, demandée après lecture d'un vrai bulletin. Quatre
reproches, tous fondés :

1. **On ne distinguait pas l'alerte du bulletin.** Deux emails de même allure,
   deux objets qui se ressemblaient. Or ce sont deux choses opposées : un
   bulletin se lit au calme, une alerte appelle une action tout de suite.
2. **« Compromissions détectées (20) »** suivi de vingt lignes. Un dirigeant
   n'a ni le temps ni la raison de lire un inventaire.
3. **Aucune explication.** L'email énonçait un type et une gravité, et
   laissait deviner le risque, les conséquences et ce qu'il fallait faire.
4. **La métaphore météo n'était pas tenue.** Les symboles étaient ⚠️ et 🔴 —
   des pictogrammes d'alerte, pas un temps qu'il fait — et rien n'expliquait
   comment les lire.

Ces tests tiennent les réponses. Ils portent sur le CONTENU RENDU, pas sur le
fait qu'un email parte : c'est précisément ce que les tests précédents ne
vérifiaient pas, et c'est pour ça que les défauts ont survécu.
"""

import pytest
from django.core import mail
from django.template.loader import render_to_string

from apps.monitoring import plain_language as monitoring_plain_language
from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Alert, Asset
from apps.notifications import services
from apps.threat_intelligence.models import BreachFinding

pytestmark = pytest.mark.django_db


@pytest.fixture
def website_asset(tenant, tenant_owner):
    return monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://example.com",
        ownership_confirmed=True,
    )


def _finding(tenant, asset, *, severity="high", endpoint="creds", identifiant=""):
    return BreachFinding.all_objects.create(
        tenant=tenant,
        asset=asset,
        source_endpoint=endpoint,
        severity=severity,
        status=BreachFinding.Status.OPEN,
        identifier_masked=identifiant,
        dedup_hash=f"{endpoint}-{severity}-{identifiant}-{BreachFinding.all_objects.count()}",
    )


class TestLesDeuxEmailsSeDistinguent:
    """Reproche n°1. Ils doivent se reconnaître AVANT ouverture, dans une
    liste de messages, puis au premier coup d'œil une fois ouverts."""

    def test_les_objets_ne_se_ressemblent_pas(self, tenant, tenant_owner, website_asset):
        alerte = Alert.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )
        mail.outbox.clear()
        services.send_weather_email(tenant)
        objet_bulletin = mail.outbox[-1].subject

        mail.outbox.clear()
        services.send_realtime_alert_email(alerte)
        objet_alerte = mail.outbox[-1].subject

        assert "Bulletin" in objet_bulletin and "Alerte" not in objet_bulletin
        assert "Alerte" in objet_alerte and "Bulletin" not in objet_alerte
        # Le symbole météo appartient au bulletin : le mettre aussi sur
        # l'alerte annulerait la distinction que l'objet doit porter.
        assert not any(s in objet_alerte for s in ("☀️", "⛅", "⛈️"))

    def test_l_alerte_ne_porte_aucune_metaphore_meteo(self, tenant, website_asset):
        alerte = Alert.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )
        mail.outbox.clear()
        services.send_realtime_alert_email(alerte)

        corps = mail.outbox[-1].body
        assert not any(s in corps for s in ("☀️", "⛅", "⛈️"))


class TestOnExpliqueEtOnDitQuoiFaire:
    """Reproches n°2 et 3 : par type, avec le sens et l'action."""

    def test_le_bulletin_groupe_par_type_et_non_par_ligne(self, tenant, website_asset):
        for i in range(20):
            _finding(tenant, website_asset, identifiant=f"c{i}")

        lignes = services.build_weather_context(tenant)["open_breach_findings"]

        assert len(lignes) == 1, "Vingt fuites du même type ne font qu'une entrée."
        assert lignes[0]["count"] == 20

    def test_chaque_groupe_porte_son_sens_et_son_action(self, tenant, website_asset):
        _finding(tenant, website_asset, severity="critical", endpoint="sessions")

        groupe = services.build_weather_context(tenant)["open_breach_findings"][0]

        assert len(groupe["meaning"]) > 60, "Une explication, pas une étiquette."
        assert len(groupe["action"]) > 40, "Une action concrète, pas un renvoi."

    def test_les_alertes_aussi_sont_expliquees_et_groupees(self, tenant, tenant_owner):
        """Trois sites injoignables produisaient trois blocs identiques."""
        for i in range(3):
            actif = monitoring_services.create_asset(
                tenant=tenant,
                user=tenant_owner,
                type=Asset.Type.WEBSITE,
                value=f"https://site{i}.example.com",
                ownership_confirmed=True,
            )
            Alert.all_objects.create(
                tenant=tenant,
                asset=actif,
                alert_type=Alert.AlertType.DOWN,
                severity=Alert.Severity.CRITICAL,
            )

        alertes = services.build_weather_context(tenant)["open_alerts"]

        assert len(alertes) == 1, "Un seul bloc « Site indisponible », trois actifs listés."
        assert alertes[0]["count"] == 3
        assert alertes[0]["meaning"] and alertes[0]["action"]

    def test_les_compromissions_ne_sont_pas_redites_dans_la_surveillance(
        self, tenant, website_asset
    ):
        """Elles sont déjà détaillées plus haut : les répéter affichait
        « ouvrez la page Compromissions » juste sous la section qui venait de
        tout expliquer."""
        Alert.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            alert_type=Alert.AlertType.BREACH_COMPROMISE,
            severity=Alert.Severity.CRITICAL,
        )

        assert services.build_weather_context(tenant)["open_alerts"] == []

    def test_chaque_type_d_alerte_a_son_explication(self):
        """Couverture éditoriale : un type sans entrée retomberait sur une
        phrase générique, et le dirigeant perdrait justement ce qu'on lui
        promet."""
        for valeur, _label in Alert.AlertType.choices:
            explication = monitoring_plain_language.explain(valeur)
            generique = monitoring_plain_language.explain("_type_inexistant_")
            assert explication != generique, f"Aucune explication dédiée pour « {valeur} »."


class TestLaMetaphoreMeteoEstTenue:
    """Reproche n°4."""

    def test_les_symboles_sont_meteorologiques(self, tenant, website_asset):
        contexte = services.build_weather_context(tenant)
        assert contexte["mood_emoji"] in ("☀️", "⛅", "⛈️")

    def test_le_bulletin_explique_comment_le_lire(self, tenant, website_asset):
        contexte = services.build_weather_context(tenant)
        corps = render_to_string("notifications/weather_email.txt", contexte)

        for symbole in ("☀️", "⛅", "⛈️"):
            assert symbole in corps, f"La légende doit présenter {symbole}."
        assert "Beau temps" in corps and "Orage" in corps

    def test_chaque_actif_porte_son_propre_temps(self, tenant, website_asset):
        actif = services.build_weather_context(tenant)["assets"][0]
        assert actif["mood_emoji"] in ("☀️", "⛅", "⛈️")

    def test_quand_tout_va_bien_on_le_dit(self, tenant, website_asset):
        contexte = services.build_weather_context(tenant)
        assert contexte["tout_va_bien"] is True
        assert contexte["mood_emoji"] == "☀️"
        corps = render_to_string("notifications/weather_email.txt", contexte)
        assert "Aucune action attendue" in corps


class TestAucunResteDeGabarit:
    """Un commentaire de gabarit ne doit jamais partir chez le client.

    Défaut introduit puis rattrapé le jour même, en regardant le rendu :
    ``{# … #}`` ne commente QU'UNE ligne. Écrit sur plusieurs lignes, Django
    l'émet tel quel — le commentaire d'implémentation partait donc dans
    l'email. Il faut ``{% comment %}``.
    """

    def test_aucun_email_ne_contient_de_syntaxe_de_gabarit(self, tenant, website_asset):
        _finding(tenant, website_asset)
        alerte = Alert.all_objects.create(
            tenant=tenant,
            asset=website_asset,
            alert_type=Alert.AlertType.DOWN,
            severity=Alert.Severity.CRITICAL,
        )
        contexte_alerte = {
            "tenant_name": tenant.name,
            "asset_value": website_asset.value,
            "alert_type_label": alerte.get_alert_type_display(),
            "severity_label": alerte.get_severity_display(),
            "meaning": "x",
            "action": "y",
            "dashboard_url": "https://exemple.test",
        }
        rendus = {
            "weather_email.txt": services.build_weather_context(tenant),
            "weather_email.html": services.build_weather_context(tenant),
            "realtime_alert_email.txt": contexte_alerte,
            "realtime_alert_email.html": contexte_alerte,
        }
        for gabarit, contexte in rendus.items():
            corps = render_to_string(f"notifications/{gabarit}", contexte)
            for residu in ("{#", "#}", "{%", "%}", "{{", "}}"):
                assert residu not in corps, (
                    f"{gabarit} laisse « {residu} » dans le message envoyé — "
                    "un commentaire multi-ligne doit utiliser {% comment %}."
                )
