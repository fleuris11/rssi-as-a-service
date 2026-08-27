"""Phase 12 — toute clé du registre est appliquée quelque part.

## Le défaut que ce fichier existe pour empêcher

Six des neuf clés du registre étaient déclarées, vendues sur la grille
tarifaire, et gardées par rien. Un client « Veille » à 89 € obtenait
l'essentiel de « Pilotage » à 249 €.

Ce défaut était **invisible par construction** : aucun test ne peut échouer
sur une garde absente, et aucun client ne se plaint d'avoir trop de
fonctionnalités. Le registre *donnait l'apparence* d'un contrôle d'accès.

## Pourquoi une table de sondes plutôt qu'une recherche textuelle

Un test qui vérifierait « la chaîne `anssi_assessment` apparaît dans un
fichier de vues » passerait au vert sur une occurrence en commentaire, sur un
import mort, ou sur une garde placée derrière un `if False`. Il mesurerait la
présence d'un mot, pas celle d'un contrôle.

``SONDES`` associe donc chaque clé à un **appel réel** qui doit être refusé
quand l'offre ne la comprend pas. Ajouter une clé au registre sans lui donner
de sonde fait échouer ``test_toute_cle_du_registre_est_sondee`` ; poser une
sonde sans garde derrière fait échouer le test de refus.

## Deux formes de garde, pas une

- **refus** : l'appel entier est refusé en 402. C'est la forme des chemins qui
  *produisent* quelque chose.
- **omission** : l'appel réussit, mais l'analyse vendue en est absente. C'est
  la forme de la corrélation de réutilisation, greffée sur un flux qui contient
  les fuites du client — les lui cacher pour lui vendre un calcul serait
  prendre ses données en otage.

## Ce qui n'est PAS testé ici, et pourquoi

Le sens du côté « autorisé » est volontairement faible : on vérifie que la
réponse **n'est pas un 402**, pas qu'elle vaut 200. Un export PDF renvoie 404
sur un document absent, une charte 429 sur quota épuisé : ce sont d'autres
contrôles, avec leurs propres tests. Affirmer ici un 200 ferait dépendre la
garde d'une chaîne entière — et rendrait rouge, par exemple, une machine sans
les bibliothèques de WeasyPrint.
"""

from collections.abc import Callable
from dataclasses import dataclass
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.billing import features
from apps.billing.models import Plan, Subscription

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd123"
REFUS = status.HTTP_402_PAYMENT_REQUIRED


# --- Outillage ---------------------------------------------------------------


@dataclass(frozen=True)
class Sonde:
    """Un point d'usage réel d'une fonctionnalité.

    ``appeler`` reçoit le client d'API, les en-têtes d'authentification et le
    contexte (tenant, actif, fuite) et exerce le chemin gardé.
    ``mode`` dit comment se lit un refus.
    """

    libelle: str
    appeler: Callable
    mode: str = "refus"  # "refus" (402) ou "omission"


def _auth(api_client, user, tenant):
    reponse = api_client.post(
        reverse("token-obtain-pair"), {"email": user.email, "password": PASSWORD}, format="json"
    )
    return {
        "HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


def _accorder(tenant, cles):
    """Fixe les fonctionnalités du tenant, sans toucher au catalogue.

    Une surcharge d'abonnement plutôt qu'un changement d'offre : elle isole
    **une seule variable** — la clé sous test — là où changer d'offre ferait
    varier les quotas, le prix et sept autres fonctionnalités en même temps.
    La conformité au catalogue réel est vérifiée séparément, plus bas.
    """
    subscription = Subscription.objects.get(tenant=tenant)
    subscription.override_features = list(cles)
    subscription.save(update_fields=["override_features"])
    return subscription


# --- Les sondes --------------------------------------------------------------


def _sonde_diagnostic(client, entetes, ctx):
    return client.post(reverse("assessment-start"), **entetes)


def _sonde_repondre_mesure(client, entetes, ctx):
    # Identifiants fantômes : la garde est posée avant la recherche de
    # l'évaluation et de la mesure. 402 hors offre, 404 dedans.
    return client.put(
        reverse("assessment-answer", args=[999999, 999999]),
        {"value": "yes", "note": ""},
        format="json",
        **entetes,
    )


def _sonde_terminer_evaluation(client, entetes, ctx):
    return client.post(reverse("assessment-complete", args=[999999]), **entetes)


def _sonde_envoyer_message(client, entetes, ctx):
    return client.post(
        reverse("ai-message-list", args=[999999]),
        {"content": "bonjour"},
        format="json",
        **entetes,
    )


def _sonde_assistant(client, entetes, ctx):
    return client.post(reverse("ai-conversation-list"), **entetes)


def _sonde_charte(client, entetes, ctx):
    return client.post(
        reverse("ai-document-list"), {"type": "it_charter"}, format="json", **entetes
    )


def _sonde_export_pdf(client, entetes, ctx):
    # Document volontairement inexistant : la garde est posée AVANT la
    # recherche du document, donc un identifiant fantôme suffit à l'exercer —
    # 402 si l'offre ne comprend pas l'export, 404 sinon. Cela évite d'avoir
    # besoin de WeasyPrint pour tester une règle commerciale.
    return client.get(reverse("ai-document-export-pdf", args=[999999]), **entetes)


def _sonde_synthese(client, entetes, ctx):
    return client.post(reverse("breach-exposure-synthesis-refresh"), **entetes)


def _sonde_revelation(client, entetes, ctx):
    return client.post(reverse("breach-finding-reveal", args=[999999]), **entetes)


def _sonde_surveillance(client, entetes, ctx):
    return client.post(
        reverse("monitored-asset-list"), {"asset_id": ctx["asset"].id}, format="json", **entetes
    )


def _sonde_correlation(client, entetes, ctx):
    """Mode « omission » : le flux doit être servi, la corrélation non calculée.

    On espionne ``correlation.correlate`` plutôt que d'inspecter la réponse :
    l'exigence Green IT est que le calcul soit **sauté**, pas filtré après
    coup. Un test sur la seule charge utile passerait au vert sur une
    implémentation qui calcule puis jette.
    """
    with patch("apps.threat_intelligence.correlation.correlate", return_value={}) as espion:
        reponse = client.get(reverse("breach-exposure-feed"), **entetes)
    return reponse, espion.called


# Une LISTE par clé, et non une sonde unique. La distinction a été trouvée en
# neutralisant les gardes une par une : avec une seule sonde par clé, retirer
# la garde de « répondre à une mesure », de « terminer l'évaluation » ou de
# « envoyer un message » ne faisait rougir aucun test. La clé restait bien
# appliquée *quelque part* — au démarrage de l'évaluation, à l'ouverture de la
# conversation — et le test structurel s'en contentait.
#
# Or c'est précisément le trou qui compte : une évaluation ouverte avant un
# changement d'offre serait restée remplissable indéfiniment par appel direct
# à l'API. « La clé est gardée quelque part » ne vaut pas « la clé est gardée
# partout où elle doit l'être ».
SONDES: dict[str, list[Sonde]] = {
    features.ANSSI_ASSESSMENT: [
        Sonde("démarrer une évaluation", _sonde_diagnostic),
        Sonde("répondre à une mesure", _sonde_repondre_mesure),
        Sonde("terminer l'évaluation", _sonde_terminer_evaluation),
    ],
    features.ASSISTANT: [
        Sonde("ouvrir une conversation", _sonde_assistant),
        Sonde("envoyer un message", _sonde_envoyer_message),
    ],
    features.CHARTER_GENERATION: [Sonde("générer une charte", _sonde_charte)],
    features.PDF_EXPORT: [Sonde("exporter un document en PDF", _sonde_export_pdf)],
    features.EXPOSURE_SYNTHESIS: [Sonde("régénérer la synthèse", _sonde_synthese)],
    features.SECRET_REVEAL: [Sonde("révéler un mot de passe", _sonde_revelation)],
    features.REALTIME_MONITORING: [Sonde("surveiller un actif", _sonde_surveillance)],
    features.REUSE_CORRELATION: [
        Sonde("corréler les réutilisations", _sonde_correlation, mode="omission")
    ],
}

# Chaque point d'usage est exercé séparément : c'est le grain auquel une garde
# peut disparaître.
POINTS_D_USAGE = [(cle, sonde) for cle, sondes in SONDES.items() for sonde in sondes]
IDENTIFIANTS = [f"{cle}::{sonde.libelle}" for cle, sonde in POINTS_D_USAGE]


# --- Contexte ----------------------------------------------------------------


@pytest.fixture
def contexte(db, user_factory, tenant_factory, api_client):
    from apps.monitoring import services as monitoring_services
    from apps.monitoring.models import Asset

    user = user_factory(email="garde@example.com")
    tenant = tenant_factory(user, name="Entreprise Gardes")
    asset = monitoring_services.create_asset(
        tenant=tenant,
        user=user,
        type=Asset.Type.WEBSITE,
        value="https://exemple-gardes.test",
        ownership_confirmed=True,
    )
    return {
        "client": api_client,
        "entetes": _auth(api_client, user, tenant),
        "tenant": tenant,
        "user": user,
        "asset": asset,
    }


# --- Le test qui empêche la récidive -----------------------------------------


class TestRegistreEtGardes:
    def test_toute_cle_du_registre_est_sondee(self):
        """Le test structurel.

        Il échoue dans les deux sens : une clé ajoutée au registre sans point
        d'usage, et une sonde laissée derrière une clé retirée. C'est le seul
        test du dépôt capable d'échouer sur une garde *absente* — tous les
        autres ne peuvent constater que le comportement d'un code présent.
        """
        registre = set(features.all_keys())
        sondees = set(SONDES)

        assert registre - sondees == set(), (
            "Clé(s) déclarée(s) au registre et appliquée(s) nulle part : "
            f"{sorted(registre - sondees)}. Poser la garde, ou retirer la clé "
            "du registre (voir ADR-025)."
        )
        assert sondees - registre == set(), (
            f"Sonde(s) sans clé correspondante : {sorted(sondees - registre)}."
        )

    def test_extended_history_a_bien_disparu(self):
        # ADR-025 : clé sans référent, retirée. Si elle revient, elle doit
        # revenir AVEC une rétention réelle et une garde — donc avec une sonde,
        # ce que le test ci-dessus imposera.
        assert "extended_history" not in features.all_keys()

    def test_chaque_cle_a_au_moins_un_point_d_usage(self):
        vides = [cle for cle, sondes in SONDES.items() if not sondes]
        assert vides == [], f"clé(s) sans point d'usage : {vides}"

    @pytest.mark.parametrize("cle,sonde", POINTS_D_USAGE, ids=IDENTIFIANTS)
    def test_la_fonctionnalite_est_refusee_hors_offre(self, cle, sonde, contexte):
        # Toutes les autres clés accordées : seule celle-ci manque. Sans cette
        # précaution, un refus pourrait venir d'une garde voisine — c'est
        # exactement le recouvrement mutuel qu'on cherche à exclure.
        _accorder(contexte["tenant"], [k for k in features.all_keys() if k != cle])

        resultat = sonde.appeler(contexte["client"], contexte["entetes"], contexte)

        if sonde.mode == "omission":
            reponse, calcule = resultat
            assert reponse.status_code == status.HTTP_200_OK, (
                f"« {sonde.libelle} » : le flux doit rester servi, seule l'analyse est retirée."
            )
            assert not calcule, f"« {sonde.libelle} » : l'analyse a été calculée hors offre."
        else:
            assert resultat.status_code == REFUS, (
                f"« {sonde.libelle} » n'est pas gardée : attendu 402, "
                f"obtenu {resultat.status_code}."
            )

    @pytest.mark.parametrize("cle,sonde", POINTS_D_USAGE, ids=IDENTIFIANTS)
    def test_la_fonctionnalite_est_accessible_dans_l_offre(self, cle, sonde, contexte):
        _accorder(contexte["tenant"], features.all_keys())

        resultat = sonde.appeler(contexte["client"], contexte["entetes"], contexte)

        if sonde.mode == "omission":
            reponse, calcule = resultat
            assert reponse.status_code == status.HTTP_200_OK
            assert calcule, f"« {sonde.libelle} » : l'analyse n'est pas calculée dans l'offre."
        else:
            assert resultat.status_code != REFUS, (
                f"« {sonde.libelle} » est refusée alors que l'offre la comprend."
            )

    def test_le_refus_nomme_l_offre_qui_debloque(self, contexte):
        # Un refus qui ne dit que « non » n'aide personne et ne vend rien
        # (ADR-019). La forme est celle des trois gardes antérieures.
        _accorder(contexte["tenant"], [])

        reponse = SONDES[features.ANSSI_ASSESSMENT][0].appeler(
            contexte["client"], contexte["entetes"], contexte
        )

        assert reponse.status_code == REFUS
        assert reponse.data["required_plan"], "le refus doit nommer une offre"
        assert "Diagnostic de maturité" in reponse.data["detail"]


# --- Conformité au catalogue réel --------------------------------------------


class TestCatalogueReel:
    """Les tests ci-dessus isolent une clé à la fois par surcharge. Ceux-ci
    vérifient la réalité commerciale : ce que « Veille » à 89 € donne
    vraiment, par rapport à « Pilotage » à 249 €."""

    @pytest.mark.parametrize(
        "cle",
        [
            features.ANSSI_ASSESSMENT,
            features.ASSISTANT,
            features.CHARTER_GENERATION,
            features.PDF_EXPORT,
            features.REUSE_CORRELATION,
        ],
    )
    def test_veille_ne_donne_pas_ce_qui_est_vendu_avec_pilotage(self, cle, contexte):
        subscription = Subscription.objects.get(tenant=contexte["tenant"])
        subscription.plan = Plan.objects.get(code="veille")
        subscription.override_features = None
        subscription.save(update_fields=["plan", "override_features"])

        for sonde in SONDES[cle]:
            resultat = sonde.appeler(contexte["client"], contexte["entetes"], contexte)

            if sonde.mode == "omission":
                _, calcule = resultat
                assert not calcule, sonde.libelle
            else:
                assert resultat.status_code == REFUS, sonde.libelle

    def test_pilotage_donne_les_huit_fonctionnalites_du_registre(self):
        # Si le catalogue et le registre divergent, une offre vend une clé qui
        # n'existe plus — ou en oublie une que le produit sait faire.
        pilotage = Plan.objects.get(code="pilotage")
        assert set(pilotage.features) == set(features.all_keys())

    def test_l_offre_d_essai_garde_le_diagnostic(self):
        # C'est la raison d'être d'ADR-024 : sans cela, poser la garde
        # `anssi_assessment` casse l'essai de tout prospect.
        essai = Plan.objects.get(code="essai")
        assert features.ANSSI_ASSESSMENT in essai.features
        assert features.SECRET_REVEAL not in essai.features
