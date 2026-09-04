"""Le délai entre deux analyses manuelles se règle, à deux niveaux.

Il était figé sur ``BREACHSENSE_SCAN_COOLDOWN_HOURS`` : 24 h pour tout le
monde, modifiable seulement par variable d'environnement et redémarrage. Or ce
délai ne protège pas le client — il protège le budget de requêtes partagé. Il
n'a donc aucune raison d'être le même pour un prospect qu'on démarche, un
client qu'on accompagne, et le parc en régime de croisière.

Deux niveaux, du plus spécifique au plus général :

1. ``tenant.scan_cooldown_hours`` — la fiche du client ;
2. le réglage de plateforme, depuis la console, sans redéploiement ;
3. la variable d'environnement, tant que rien n'a été réglé.

Le piège de ce genre de cascade est le **zéro**. ``0`` veut dire « aucun
délai », pas « non renseigné » : un test de vérité (``if surcharge:``) le
ferait retomber sur le niveau supérieur et appliquerait 24 h à un client à qui
l'exploitant vient d'accorder l'inverse. Deux tests ci-dessous ne visent que
ce cas.
"""

import pytest

from apps.threat_intelligence import services

pytestmark = pytest.mark.django_db


class TestResolutionDuDelai:
    def test_sans_reglage_on_prend_la_valeur_par_defaut(self, tenant, settings):
        settings.BREACHSENSE_SCAN_COOLDOWN_HOURS = 24
        assert services.scan_cooldown_hours(tenant) == 24

    def test_la_surcharge_du_client_prime_sur_la_plateforme(self, tenant, settings):
        settings.BREACHSENSE_SCAN_COOLDOWN_HOURS = 24
        tenant.scan_cooldown_hours = 2
        tenant.save(update_fields=["scan_cooldown_hours"])

        assert services.scan_cooldown_hours(tenant) == 2

    def test_zero_sur_le_client_veut_dire_aucun_delai(self, tenant, settings):
        """Le piège. ``0`` est une valeur, pas une absence de valeur."""
        settings.BREACHSENSE_SCAN_COOLDOWN_HOURS = 24
        tenant.scan_cooldown_hours = 0
        tenant.save(update_fields=["scan_cooldown_hours"])

        assert services.scan_cooldown_hours(tenant) == 0, (
            "Un 0 traité comme « non renseigné » ferait retomber sur 24 h — "
            "exactement l'inverse de ce que l'exploitant a demandé."
        )

    def test_null_sur_le_client_retombe_bien_sur_la_plateforme(self, tenant, settings):
        settings.BREACHSENSE_SCAN_COOLDOWN_HOURS = 6
        tenant.scan_cooldown_hours = None
        tenant.save(update_fields=["scan_cooldown_hours"])

        assert services.scan_cooldown_hours(tenant) == 6


class TestApplicationDuDelai:
    def test_un_delai_nul_n_impose_aucune_attente(self, tenant, settings):
        settings.BREACHSENSE_SCAN_COOLDOWN_HOURS = 24
        tenant.scan_cooldown_hours = 0
        tenant.save(update_fields=["scan_cooldown_hours"])

        services.mark_scan_cooldown(tenant)
        services.ensure_scan_cooldown_elapsed(tenant)  # ne doit pas lever

    def test_un_delai_actif_bloque_la_seconde_analyse(self, tenant, settings):
        settings.BREACHSENSE_SCAN_COOLDOWN_HOURS = 24
        services.mark_scan_cooldown(tenant)

        with pytest.raises(services.CooldownActiveError):
            services.ensure_scan_cooldown_elapsed(tenant)

    def test_l_empreinte_posee_dure_le_temps_reellement_configure(self, tenant, settings):
        """``mark_scan_cooldown`` posait une empreinte calée sur la variable
        d'environnement, pendant que la vérification lisait la valeur résolue.
        Régler 2 h dans la console laissait donc un blocage de 24 h en cache :
        le client restait bloqué un jour entier malgré le réglage."""
        from django.core.cache import cache

        settings.BREACHSENSE_SCAN_COOLDOWN_HOURS = 24
        tenant.scan_cooldown_hours = 2
        tenant.save(update_fields=["scan_cooldown_hours"])

        services.mark_scan_cooldown(tenant)

        cle = services.SCAN_COOLDOWN_CACHE_KEY.format(tenant_id=tenant.id)
        restant = cache.ttl(cle) if hasattr(cache, "ttl") else None
        if restant is None:
            pytest.skip("Le backend de cache utilisé n'expose pas le TTL restant.")
        assert restant <= 2 * 3600, f"Empreinte de {restant}s posée pour un délai de 2 h."


class TestMessageAuClient:
    def test_le_refus_ne_nomme_ni_le_fournisseur_ni_le_mecanisme(self, tenant, settings):
        settings.BREACHSENSE_SCAN_COOLDOWN_HOURS = 24
        services.mark_scan_cooldown(tenant)

        with pytest.raises(services.CooldownActiveError) as exc_info:
            services.ensure_scan_cooldown_elapsed(tenant)

        message = str(exc_info.value).lower()
        assert "breachsense" not in message
        assert "anti-abus" not in message, (
            "« délai anti-abus » dit au client qu'on se protège de lui. "
            "Il lit une attente, pas un soupçon."
        )
