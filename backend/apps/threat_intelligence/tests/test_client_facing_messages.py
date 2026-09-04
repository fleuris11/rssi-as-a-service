"""Aucun message lu par un client ne doit révéler l'intérieur du produit.

Ce test existe parce que la fuite passait par l'endroit où personne ne cherche
une fuite : les messages d'erreur. Un dirigeant de PME qui lançait une analyse
pouvait lire, dans son propre espace, « Breachsense a répondu 400 : Request
missing the appropriate parameters », ou « Le budget d'analyses de la
plateforme pour ce mois est atteint (87/1000) ».

Trois choses fuyaient, et elles n'ont pas la même gravité :

1. **Le nom du fournisseur** — un secret commercial.
2. **L'état de la plateforme** — « 87/1000 », « pool de 15 » : la
   consommation des AUTRES clients, dans un produit dont l'argument de vente
   est le cloisonnement. C'est la plus grave.
3. **Notre configuration** — « le webhook n'est pas configuré sur cet
   environnement » avoue un défaut d'exploitation au client qui paie pour ne
   pas s'en occuper.

Le test ne relit pas des chaînes à la main : il **exécute** les chemins
d'échec et inspecte ce qui en sort, y compris le champ ``error_message`` d'un
job de scan, qui est sérialisé vers le client.
"""

from unittest.mock import patch

import pytest

from apps.billing.capacity import PlatformCapacityError
from apps.threat_intelligence import client_messages, quota, services, tasks
from apps.threat_intelligence.models import BreachScanJob
from apps.threat_intelligence.providers.breachsense.client import BreachsenseBadRequestError

INTERDITS = client_messages.FORBIDDEN_IN_CLIENT_MESSAGES


def _messages_client_du_module() -> dict[str, str]:
    """Toutes les constantes de message du module, par nom."""
    return {
        nom: valeur
        for nom, valeur in vars(client_messages).items()
        if nom.isupper() and isinstance(valeur, str)
    }


def _verifier(nom: str, message: str) -> None:
    bas = message.lower()
    for terme in INTERDITS:
        assert terme not in bas, (
            f"Le message client « {nom} » contient le terme interne « {terme} » :\n"
            f"    {message}\n"
            "Un client ne doit lire ni le nom du fournisseur, ni l'état de la "
            "plateforme, ni notre configuration."
        )
    # Un chiffre isolé dans un message d'erreur est presque toujours un
    # compteur de ressource partagée (« 3 emplacements restants », « 87/1000 »).
    assert not any(c.isdigit() for c in message), (
        f"Le message client « {nom} » contient un chiffre :\n    {message}\n"
        "Les compteurs de ressource sont ceux de la plateforme, pas du client."
    )


class TestConstantesDeMessages:
    def test_aucune_constante_ne_contient_de_vocabulaire_interne(self):
        messages = _messages_client_du_module()
        assert messages, "Aucune constante trouvée — le module a-t-il été renommé ?"
        for nom, message in messages.items():
            _verifier(nom, message)

    #: Messages qui constatent un état DÉJÀ satisfait plutôt que de refuser.
    #: « C'est déjà fait » n'a pas de sortie à proposer : la demande du client
    #: est remplie. La règle ci-dessous vise les refus, pas les constats.
    SANS_SORTIE_ATTENDUE = {"ASSET_ALREADY_MONITORED"}

    def test_chaque_refus_dit_quoi_faire(self):
        """Un refus qui n'indique pas de sortie transforme un incident en
        appel au support — ou en client qui s'en va."""
        sorties = (
            "contactez",
            "réessayez",
            "relancer",
            "retirez",
            "possible",
            "repart",
            "prochain",
        )
        for nom, message in _messages_client_du_module().items():
            if nom in self.SANS_SORTIE_ATTENDUE:
                continue
            bas = message.lower()
            assert any(s in bas for s in sorties), (
                f"Le message « {nom} » constate sans rien proposer :\n    {message}"
            )


class TestCapaciteePlateforme:
    def test_le_message_exploitant_reste_detaille(self):
        """Le back-office doit continuer à voir les chiffres : c'est lui qui
        agit dessus."""
        exc = PlatformCapacityError(
            "Budget atteint (87/1000), passez à un palier supérieur.",
            client_message="Les analyses sont momentanément indisponibles.",
        )
        assert "87/1000" in str(exc)
        assert "palier" in str(exc)

    def test_le_message_client_ne_porte_ni_chiffre_ni_interne(self):
        exc = PlatformCapacityError(
            "Budget atteint (87/1000), passez à un palier supérieur.",
            client_message="Les analyses sont momentanément indisponibles. Contactez-nous.",
        )
        _verifier("PlatformCapacityError.client_message", exc.client_message)

    def test_un_repli_neutre_existe_toujours(self):
        """Une levée sans `client_message` ne doit jamais retomber sur le
        message d'exploitation par défaut d'`Exception`."""
        exc = PlatformCapacityError("Détail interne : pool 15/15 saturé.")
        assert "15" not in exc.client_message
        assert "pool" not in exc.client_message.lower()
        _verifier("DEFAULT_CLIENT_MESSAGE", exc.client_message)


@pytest.mark.django_db
class TestEchecDeScan:
    def test_l_erreur_du_fournisseur_n_atteint_jamais_le_client(self, tenant, website_asset):
        """Le chemin exact de la panne du 01/09 : l'API répond 400, et le
        client lisait la réponse brute dans son espace."""
        job = BreachScanJob.all_objects.create(
            tenant=tenant, triggered_by=services.TriggeredBy.MANUAL
        )

        erreur = BreachsenseBadRequestError(
            "Breachsense a répondu 400 : Request missing the appropriate parameters"
        )
        with patch.object(services, "execute_scan", side_effect=erreur):
            tasks.run_breach_scan_task.apply(
                kwargs={
                    "tenant_id": str(tenant.id),
                    "triggered_by": services.TriggeredBy.MANUAL,
                    "job_id": job.id,
                }
            )

        job.refresh_from_db()
        assert job.status == BreachScanJob.Status.FAILED
        # C'est ce champ que `BreachScanJobSerializer` expose au client.
        _verifier("BreachScanJob.error_message", job.error_message)
        assert job.error_message == client_messages.SCAN_FAILED


class TestBudgetFournisseur:
    def test_le_refus_de_quota_ne_publie_pas_la_consommation_du_parc(self):
        manager = quota.QuotaManager()
        with patch.object(manager, "get_remaining", return_value=3):
            with pytest.raises(quota.QuotaExceededError) as exc_info:
                manager.ensure_query_budget_available(margin=50)
        _verifier("QuotaExceededError", str(exc_info.value))
