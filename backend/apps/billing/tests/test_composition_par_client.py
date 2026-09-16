"""V2-8 — composer le périmètre d'un client, sans toucher au catalogue.

Le champ ``override_features`` existait et fonctionnait ; rien ne le réglait.
Ce fichier tient les règles que la composition doit respecter :

1. ce qui est **hérité** de l'offre reste lisible à côté de ce qui est
   **effectif** — sans quoi une surcharge devient une dette invisible ;
2. une composition identique à l'offre **reste** une surcharge : c'est une
   décision, et ce client ne doit plus suivre les évolutions de l'offre ;
3. les combinaisons incohérentes sont refusées, avec la phrase qui dit
   pourquoi — un refus sans motif conduit à recommencer la même ;
4. revenir à l'offre efface la surcharge, et le client suit de nouveau.
"""

import pytest

from apps.billing import entitlements, features, services
from apps.billing.models import Plan, Subscription

pytestmark = pytest.mark.django_db


@pytest.fixture
def offre(db):
    return Plan.objects.create(
        code="composition-test",
        name="Offre de test",
        status=Plan.Status.PUBLISHED,
        price_monthly=100,
        monitored_assets=2,
        monthly_scans=10,
        max_users=5,
        watched_accounts=2,
        monthly_watched_account_scans=5,
        features=[
            features.ANSSI_ASSESSMENT,
            features.ASSISTANT,
            features.WATCHED_ACCOUNTS,
            features.REALTIME_MONITORING,
        ],
    )


@pytest.fixture
def abonnement(tenant, offre):
    Subscription.objects.filter(tenant=tenant).update(plan=offre, status=Subscription.Status.ACTIVE)
    return Subscription.objects.get(tenant=tenant)


class TestCeQueLaFicheMontre:
    def test_chaque_fonctionnalite_porte_son_etat_herite_et_son_etat_effectif(self, abonnement):
        lignes = {ligne["key"]: ligne for ligne in services.feature_composition(abonnement)}

        assert set(lignes) == set(features.all_keys()), "le registre entier doit être proposé"
        assert lignes[features.ASSISTANT]["inherited"] is True
        assert lignes[features.ASSISTANT]["enabled"] is True
        assert lignes[features.SECRET_REVEAL]["inherited"] is False
        assert lignes[features.SECRET_REVEAL]["enabled"] is False
        # Sans surcharge, rien ne dévie : l'écran ne doit rien signaler.
        assert all(ligne["deviation"] == "" for ligne in lignes.values())

    def test_l_ecart_avec_l_offre_est_nomme(self, abonnement):
        services.set_feature_overrides(
            subscription=abonnement,
            keys=[features.ASSISTANT, features.SECRET_REVEAL],
        )

        lignes = {ligne["key"]: ligne for ligne in services.feature_composition(abonnement)}

        assert lignes[features.SECRET_REVEAL]["deviation"] == "ajoutee"
        assert lignes[features.ANSSI_ASSESSMENT]["deviation"] == "retiree"
        assert lignes[features.ASSISTANT]["deviation"] == "", "héritée ET effective : aucun écart"

    def test_les_ecrans_derives_accompagnent_la_fonctionnalite(self, abonnement):
        lignes = {ligne["key"]: ligne for ligne in services.feature_composition(abonnement)}

        assert lignes[features.ANSSI_ASSESSMENT]["derived_screens"] == [
            "Résultats",
            "Plan d'action",
        ]


class TestComposer:
    def test_la_composition_remplace_les_fonctionnalites_de_l_offre(self, tenant, abonnement):
        services.set_feature_overrides(subscription=abonnement, keys=[features.ASSISTANT])

        abonnement.refresh_from_db()
        assert abonnement.effective_features == [features.ASSISTANT]

    def test_une_cle_inconnue_est_ignoree_et_non_fatale(self, abonnement):
        services.set_feature_overrides(
            subscription=abonnement, keys=[features.ASSISTANT, "fonctionnalite-inventee"]
        )

        abonnement.refresh_from_db()
        assert abonnement.effective_features == [features.ASSISTANT]

    def test_une_composition_vide_est_une_composition(self, abonnement):
        """« Ce client ne voit que le socle » est une décision légitime, à
        distinguer de « aucune composition »."""
        services.set_feature_overrides(subscription=abonnement, keys=[])

        abonnement.refresh_from_db()
        assert abonnement.override_features == []
        assert abonnement.effective_features == []

    def test_composer_a_l_identique_de_l_offre_reste_une_surcharge(self, abonnement, offre):
        """Sinon le client suivrait la prochaine évolution de l'offre alors
        qu'on a justement décidé de figer son périmètre."""
        services.set_feature_overrides(subscription=abonnement, keys=list(offre.features))
        abonnement.refresh_from_db()
        assert abonnement.override_features is not None

        offre.features = [*offre.features, features.SECRET_REVEAL]
        offre.save(update_fields=["features"])

        abonnement.refresh_from_db()
        assert features.SECRET_REVEAL not in abonnement.effective_features

    def test_la_composition_est_tracee_comme_evenement_d_abonnement(self, abonnement):
        services.set_feature_overrides(subscription=abonnement, keys=[features.ASSISTANT])

        assert abonnement.events.filter(reason__icontains="fonctionnalités").exists()


class TestRevenirALOffre:
    def test_le_retour_efface_la_surcharge(self, abonnement, offre):
        services.set_feature_overrides(subscription=abonnement, keys=[features.ASSISTANT])

        services.clear_feature_overrides(subscription=abonnement)

        abonnement.refresh_from_db()
        assert abonnement.override_features is None
        assert abonnement.effective_features == features.sanitize(offre.features)

    def test_apres_le_retour_le_client_suit_de_nouveau_son_offre(self, abonnement, offre):
        services.set_feature_overrides(subscription=abonnement, keys=[])
        services.clear_feature_overrides(subscription=abonnement)

        offre.features = [*offre.features, features.SECRET_REVEAL]
        offre.save(update_fields=["features"])

        abonnement.refresh_from_db()
        assert features.SECRET_REVEAL in abonnement.effective_features


class TestCombinaisonsIncoherentes:
    def test_activer_les_comptes_surveilles_sans_quota_est_refuse(self, abonnement):
        abonnement.override_watched_accounts = 0
        abonnement.save(update_fields=["override_watched_accounts"])

        with pytest.raises(services.CompositionError) as refus:
            services.set_feature_overrides(
                subscription=abonnement, keys=[features.WATCHED_ACCOUNTS]
            )

        assert "compte à surveiller" in str(refus.value)
        abonnement.refresh_from_db()
        assert abonnement.override_features is None, "un refus ne doit rien écrire"

    def test_la_surveillance_temps_reel_sans_emplacement_est_refusee(self, abonnement):
        abonnement.override_monitored_assets = 0
        abonnement.save(update_fields=["override_monitored_assets"])

        with pytest.raises(services.CompositionError) as refus:
            services.set_feature_overrides(
                subscription=abonnement, keys=[features.REALTIME_MONITORING]
            )

        assert "emplacement" in str(refus.value)

    def test_le_refus_dit_quoi_faire(self, abonnement):
        abonnement.override_watched_accounts = 0
        abonnement.save(update_fields=["override_watched_accounts"])

        with pytest.raises(services.CompositionError) as refus:
            services.set_feature_overrides(
                subscription=abonnement, keys=[features.WATCHED_ACCOUNTS]
            )

        phrase = refus.value.problemes[0]
        assert "Relevez le quota" in phrase and "retirez la fonctionnalité" in phrase

    def test_une_dependance_entre_fonctionnalites_serait_appliquee(self, abonnement, monkeypatch):
        """La table est vide aujourd'hui (aucune clé n'en exige une autre) : ce
        test vérifie le MÉCANISME, pour qu'il tienne le jour où une dépendance
        apparaîtra."""
        monkeypatch.setitem(
            features.DEPEND_DE, features.SECRET_REVEAL, (features.REUSE_CORRELATION,)
        )

        with pytest.raises(services.CompositionError) as refus:
            services.set_feature_overrides(subscription=abonnement, keys=[features.SECRET_REVEAL])

        assert "Corrélation de réutilisation" in str(refus.value)

    def test_la_dependance_satisfaite_passe(self, abonnement, monkeypatch):
        monkeypatch.setitem(
            features.DEPEND_DE, features.SECRET_REVEAL, (features.REUSE_CORRELATION,)
        )

        services.set_feature_overrides(
            subscription=abonnement,
            keys=[features.SECRET_REVEAL, features.REUSE_CORRELATION],
        )

        abonnement.refresh_from_db()
        assert features.SECRET_REVEAL in abonnement.effective_features


class TestCeQueLeClientVoit:
    """Le client ne reçoit pas seulement « incluse ou non » : il reçoit la
    CAUSE de l'absence, parce que l'interface n'en fait pas la même chose
    (ADR-038) — hors offre se propose, retirée se masque."""

    def test_sans_composition_tout_vient_de_l_offre(self, tenant, abonnement):
        lignes = {f["key"]: f for f in entitlements.summary(tenant)["features"]}

        assert lignes[features.ASSISTANT]["source"] == "plan"
        assert lignes[features.SECRET_REVEAL]["source"] == "plan"

    def test_une_fonctionnalite_retiree_est_marquee_comme_telle(self, tenant, abonnement):
        services.set_feature_overrides(subscription=abonnement, keys=[features.ASSISTANT])

        lignes = {f["key"]: f for f in entitlements.summary(tenant)["features"]}

        assert lignes[features.ANSSI_ASSESSMENT]["included"] is False
        assert lignes[features.ANSSI_ASSESSMENT]["source"] == "override"
        # Hors offre ET hors composition : c'est toujours l'offre qui manque.
        assert lignes[features.SECRET_REVEAL]["source"] == "plan"

    def test_une_fonctionnalite_ajoutee_est_marquee_comme_telle(self, tenant, abonnement):
        services.set_feature_overrides(
            subscription=abonnement, keys=[features.ASSISTANT, features.SECRET_REVEAL]
        )

        lignes = {f["key"]: f for f in entitlements.summary(tenant)["features"]}

        assert lignes[features.SECRET_REVEAL]["included"] is True
        assert lignes[features.SECRET_REVEAL]["source"] == "override"
        assert lignes[features.ASSISTANT]["source"] == "plan", "héritée : elle vient de l'offre"


class TestCoherenceDuRegistre:
    """Les tables déclaratives ne doivent citer que des clés qui existent :
    une clé fantôme y serait une règle qui ne s'applique jamais."""

    def test_toutes_les_cles_citees_existent(self):
        citees = {
            *features.DEPEND_DE,
            *(cle for exigees in features.DEPEND_DE.values() for cle in exigees),
            *features.QUOTA_REQUIS,
            *features.ECRANS_DERIVES,
        }

        assert citees <= set(features.all_keys())

    def test_chaque_quota_requis_designe_un_attribut_reel(self, abonnement):
        for attribut, _libelle in features.QUOTA_REQUIS.values():
            assert hasattr(abonnement, attribut), attribut
