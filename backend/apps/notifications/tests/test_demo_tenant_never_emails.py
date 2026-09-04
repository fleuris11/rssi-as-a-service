"""Le tenant de démonstration n'envoie aucun email.

Défaut relevé en production le 04/09/2026, dans la boîte d'envoi elle-même :
**dix rebonds « 521 Domain not found : NXDOMAIN »**, un par jour depuis le
26 août, tous pour ``marie.durand@cabinet-durand-demo.fr``.

Le domaine de démonstration n'existe pas, et c'est délibéré — personne ne doit
pouvoir confondre la démonstration avec un vrai client. Mais les préférences de
notification partaient sur le défaut du modèle (``weather_enabled=True``), donc
la météo quotidienne était réellement expédiée à une adresse inexistante, tous
les matins à 8 h.

Pourquoi ce n'est pas qu'un désagrément : un domaine qui émet chaque jour vers
des adresses inexistantes **dégrade sa réputation d'expéditeur**, et ce sont
les emails des VRAIS clients qui finissent en indésirables. Le produit vend
précisément des alertes par email : sa propre délivrabilité est une
fonctionnalité.
"""

import pytest
from django.core import mail
from django.core.management import call_command

from apps.notifications import services
from apps.notifications.models import NotificationPreferences
from apps.tenants.models import Tenant
from apps.threat_intelligence.management.commands.seed_demo_tenant import DEMO_TENANT_SLUG

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo_tenant(settings):
    settings.DEBUG = True  # le garde-fou de la commande refuse DEBUG=False
    call_command("seed_demo_tenant", reset=True)
    return Tenant.objects.get(slug=DEMO_TENANT_SLUG)


class TestLeTenantDeDemoNEmetRien:
    def test_les_preferences_de_notification_sont_coupees(self, demo_tenant):
        prefs = NotificationPreferences.all_objects.get(tenant=demo_tenant)
        assert prefs.weather_enabled is False
        assert prefs.realtime_alerts_enabled is False

    def test_la_meteo_ne_part_pas(self, demo_tenant):
        """La garde qui compte : même appelée directement, la météo du tenant
        de démonstration ne doit produire aucun envoi."""
        mail.outbox.clear()
        services.send_weather_email(demo_tenant)
        assert mail.outbox == [], (
            "Le tenant de démonstration a envoyé un email. Son domaine n'existe "
            "pas : chaque envoi est un rebond, et chaque rebond abîme la "
            "réputation d'expéditeur dont dépendent les vrais clients."
        )

    def test_il_n_apparait_pas_dans_les_envois_du_matin(self, demo_tenant):
        """`list_preferences_due_for_weather` ne filtre que sur
        `weather_enabled` : c'est bien ce drapeau qui exclut la démo de la
        tournée quotidienne."""
        from django.utils import timezone

        prefs = NotificationPreferences.all_objects.get(tenant=demo_tenant)
        maintenant = timezone.localtime().replace(
            hour=prefs.weather_time.hour, minute=prefs.weather_time.minute
        )
        dus = services.list_preferences_due_for_weather(maintenant)

        assert demo_tenant.id not in {p.tenant_id for p in dus}
