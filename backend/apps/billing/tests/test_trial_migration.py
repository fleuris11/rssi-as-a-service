"""Bascule des essais en cours vers l'offre d'essai dédiée (ADR-024).

Ce que ces tests protègent n'est pas visible aujourd'hui : tant qu'aucune
garde de fonctionnalité n'est posée, un essai resté sur « Veille » a
exactement les mêmes droits qu'un essai sur « Essai ». Le défaut n'apparaîtra
qu'au moment où les six gardes manquantes tomberont — c'est-à-dire trop tard
pour le remarquer sans casser l'essai d'un prospect réel.

D'où le choix d'écrire ces tests **avant** les gardes plutôt qu'avec elles.

La règle est testée directement plutôt qu'à travers `migrate` : rejouer
l'historique des migrations pour éprouver une règle métier confondrait ce
qu'on vérifie (la règle) et ce qui la transporte (la migration).
"""

from decimal import Decimal

import pytest

from apps.billing.models import Plan, Subscription, SubscriptionEvent
from apps.billing.trial_migration import basculer_essais
from apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db

CODE_ESSAI = "essai"


def _catalogue(code):
    """Les offres réelles, posées par les migrations 0002 et 0003.

    Volontairement pas de catalogue fabriqué pour l'occasion : c'est la
    répartition réelle des fonctionnalités entre « Veille » et « Essai » qui
    fait l'objet de la bascule. Un faux catalogue testerait la mécanique en
    laissant passer une erreur de contenu.
    """
    return Plan.objects.get(code=code)


def _plan(code, *, assets=1, status=Plan.Status.PUBLISHED, features=None):
    """Offre synthétique, pour les cas qui n'existent pas au catalogue."""
    return Plan.objects.create(
        code=code,
        name=code.capitalize(),
        monitored_assets=assets,
        monthly_scans=20,
        max_users=3,
        price_monthly=Decimal("89"),
        status=status,
        features=features if features is not None else ["realtime_monitoring"],
    )


def _abonnement(plan, *, status=Subscription.Status.TRIAL, nom="Client", **kwargs):
    tenant = Tenant.objects.create(name=nom, slug=nom.lower().replace(" ", "-"))
    return Subscription.objects.create(tenant=tenant, plan=plan, status=status, **kwargs)


@pytest.fixture
def offre_essai():
    return _catalogue(CODE_ESSAI)


def _basculer():
    return basculer_essais(Plan, Subscription, SubscriptionEvent, code_essai=CODE_ESSAI)


class TestCeQuiEstBascule:
    def test_un_essai_sur_une_offre_du_catalogue_est_bascule(self, offre_essai):
        abonnement = _abonnement(_catalogue("veille"), nom="Novae")

        rapport = _basculer()

        abonnement.refresh_from_db()
        assert abonnement.plan.code == CODE_ESSAI
        assert len(rapport.basculees) == 1
        assert rapport.basculees[0].tenant == "Novae"

    def test_l_essai_gagne_les_fonctionnalites_qu_il_aurait_perdues(self, offre_essai):
        # Le coeur du sujet : « Veille » n'inclut pas le diagnostic. Sans cette
        # bascule, la pose des gardes le retirerait à un essai en cours.
        abonnement = _abonnement(_catalogue("veille"))

        _basculer()

        abonnement.refresh_from_db()
        assert "anssi_assessment" in abonnement.effective_features
        assert "charter_generation" in abonnement.effective_features

    @pytest.mark.parametrize(
        "status",
        [
            Subscription.Status.ACTIVE,
            Subscription.Status.SUSPENDED,
            Subscription.Status.CANCELLED,
            Subscription.Status.EXPIRED,
        ],
    )
    def test_seuls_les_essais_sont_touches(self, offre_essai, status):
        # Un client actif sur « Veille » a CHOISI et PAYÉ cette offre. Le
        # basculer sur l'essai lui donnerait gratuitement ce qui est vendu
        # 249 € — l'exact inverse du défaut qu'on corrige.
        abonnement = _abonnement(_catalogue("veille"), status=status)

        rapport = _basculer()

        abonnement.refresh_from_db()
        assert abonnement.plan.code == "veille"
        assert rapport.basculees == []

    def test_un_essai_deja_sur_l_offre_d_essai_n_est_pas_retouche(self, offre_essai):
        abonnement = _abonnement(offre_essai)
        avant = abonnement.updated_at

        rapport = _basculer()

        abonnement.refresh_from_db()
        assert abonnement.updated_at == avant
        assert rapport.basculees == []
        assert SubscriptionEvent.objects.count() == 0


class TestIdempotence:
    def test_une_seconde_passe_ne_trouve_plus_rien(self, offre_essai):
        _abonnement(_catalogue("veille"))

        premier = _basculer()
        second = _basculer()

        assert len(premier.basculees) == 1
        assert second.basculees == []

    def test_l_idempotence_ne_repose_pas_sur_le_statut_interne_de_l_offre(self, offre_essai):
        """Trou de couverture trouvé en neutralisant les gardes une à une.

        Supprimer l'exclusion « déjà sur l'offre d'essai » ne faisait rougir
        aucun test : la protection des offres internes rattrapait le cas, par
        coïncidence — l'offre d'essai est interne. Le jour où quelqu'un la
        publierait depuis la console, l'idempotence tomberait sans qu'un seul
        test ne le signale, et chaque passe écrirait un changement d'offre
        fictif dans l'historique du client.
        """
        Plan.objects.filter(code=CODE_ESSAI).update(status=Plan.Status.PUBLISHED)
        abonnement = _abonnement(Plan.objects.get(code=CODE_ESSAI))
        avant = abonnement.updated_at

        rapport = _basculer()

        abonnement.refresh_from_db()
        assert rapport.basculees == []
        assert SubscriptionEvent.objects.count() == 0
        assert abonnement.updated_at == avant

    def test_une_seconde_passe_n_ecrit_aucun_evenement_supplementaire(self, offre_essai):
        # L'idempotence porte sur les effets, pas seulement sur le rapport :
        # un second événement laisserait croire à deux changements d'offre.
        _abonnement(_catalogue("veille"))

        _basculer()
        apres_une_passe = SubscriptionEvent.objects.count()
        _basculer()

        assert SubscriptionEvent.objects.count() == apres_une_passe == 1


class TestTracabilite:
    def test_chaque_bascule_laisse_un_evenement_nommant_les_deux_offres(self, offre_essai):
        # Exigence de la phase 10 : aucune transition implicite. C'est aussi
        # la seule reprise possible si la bascule doit être défaite.
        _abonnement(_catalogue("veille"))

        _basculer()

        evenement = SubscriptionEvent.objects.get()
        assert evenement.from_plan == "Veille"
        assert evenement.to_plan == "Essai"
        assert "ADR-024" in evenement.reason
        assert evenement.actor is None

    def test_le_statut_de_l_abonnement_ne_change_pas(self, offre_essai):
        # On change d'offre, pas d'état : un essai reste un essai, et sa date
        # de fin court toujours.
        abonnement = _abonnement(_catalogue("veille"))

        _basculer()

        abonnement.refresh_from_db()
        evenement = SubscriptionEvent.objects.get()
        assert abonnement.status == Subscription.Status.TRIAL
        assert evenement.from_status == evenement.to_status == "trial"

    def test_le_rapport_nomme_ce_qui_a_ete_bascule(self, offre_essai):
        _abonnement(_catalogue("veille"), nom="Agence Novae")

        lignes = "\n".join(_basculer().lignes())

        assert "1 abonnement(s) déplacé(s)" in lignes
        assert "Agence Novae" in lignes
        assert "veille -> essai" in lignes

    def test_le_rapport_le_dit_quand_il_n_y_a_rien_a_faire(self, offre_essai):
        # Un silence ne distingue pas « rien à basculer » de « le code n'a pas
        # tourné ». Pendant un déploiement, la différence compte.
        lignes = "\n".join(_basculer().lignes())

        assert "aucun essai à basculer" in lignes


class TestSurcharges:
    def test_une_surcharge_de_fonctionnalites_est_conservee(self, offre_essai):
        # Écart assumé avec ``change_plan``, qui efface les surcharges. Ici
        # personne n'a renégocié : effacer retirerait à un client ce qu'un
        # exploitant lui avait délibérément accordé.
        abonnement = _abonnement(
            _catalogue("veille"),
            override_features=["realtime_monitoring", "secret_reveal"],
        )

        _basculer()

        abonnement.refresh_from_db()
        assert abonnement.override_features == ["realtime_monitoring", "secret_reveal"]
        assert "secret_reveal" in abonnement.effective_features

    def test_une_surcharge_de_quota_est_conservee(self, offre_essai):
        abonnement = _abonnement(_catalogue("veille"), override_monitored_assets=4)

        _basculer()

        abonnement.refresh_from_db()
        assert abonnement.monitored_assets_quota == 4


class TestGardesDeSurete:
    def test_sans_offre_d_essai_rien_n_est_touche_et_le_dit(self):
        # L'offre est administrable depuis la console : elle peut avoir été
        # renommée ou retirée. Une migration qui lèverait ici bloquerait tout
        # le déploiement pour un défaut de catalogue qui ne casse rien.
        abonnement = _abonnement(_catalogue("veille"))
        Plan.objects.filter(code=CODE_ESSAI).delete()

        rapport = _basculer()

        abonnement.refresh_from_db()
        assert abonnement.plan.code == "veille"
        assert rapport.empechement
        assert "NON EFFECTUÉE" in "\n".join(rapport.lignes())

    def test_la_bascule_est_refusee_si_elle_augmentait_l_engagement(self):
        # L'offre d'essai est modifiable sans redéploiement. Si quelqu'un y
        # porte les emplacements à 3, basculer en masse consommerait la
        # ressource rare (ADR-013) sans que personne ne l'ait demandé.
        Plan.objects.filter(code=CODE_ESSAI).update(monitored_assets=3)
        abonnement = _abonnement(_catalogue("veille"))

        rapport = _basculer()

        abonnement.refresh_from_db()
        assert abonnement.plan.code == "veille"
        assert rapport.basculees == []
        assert "augmenterait l'engagement" in "\n".join(rapport.lignes())

    def test_la_bascule_n_augmente_jamais_l_engagement_plateforme(self, offre_essai):
        # Formulation directe de l'invariant, indépendamment des offres en
        # présence : c'est lui qui dispense d'un contrôle de capacité.
        for code in ("veille", "pilotage", "souverain"):
            _abonnement(_catalogue(code), nom=f"Client {code}")

        avant = sum(a.monitored_assets_quota for a in Subscription.objects.all())
        _basculer()
        apres = sum(a.monitored_assets_quota for a in Subscription.objects.all())

        assert apres <= avant

    def test_un_essai_sur_une_autre_offre_interne_est_laisse_en_place(self, offre_essai):
        # Offre partenaire, tarif négocié, compte de démonstration : une offre
        # interne a été attribuée à la main. Défaire une décision d'exploitant
        # serait pire que le défaut qu'on corrige.
        partenaire = _plan("partenaire", status=Plan.Status.INTERNAL)
        abonnement = _abonnement(partenaire)

        rapport = _basculer()

        abonnement.refresh_from_db()
        assert abonnement.plan.code == "partenaire"
        assert rapport.basculees == []
        assert "attribuée délibérément" in "\n".join(rapport.lignes())
