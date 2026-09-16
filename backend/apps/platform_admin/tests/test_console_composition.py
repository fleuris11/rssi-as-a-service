"""V2-8 — l'écran de composition, vu de l'API de la console.

Ce que ces tests tiennent, au-delà du « ça marche » : la traçabilité (qui,
quand, quoi, avant/après), le refus motivé d'une combinaison incohérente, et
le fait qu'une composition ne déborde jamais sur un autre client.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.billing import features
from apps.billing.models import Plan, Subscription
from apps.platform_admin.models import AdminAuditLog

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd123"


@pytest.fixture
def staff_headers(api_client, user_factory):
    staff = user_factory(email="console-composition@example.com", is_staff=True)
    reponse = api_client.post(
        reverse("token-obtain-pair"), {"email": staff.email, "password": PASSWORD}, format="json"
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}"}


@pytest.fixture
def offre(db):
    return Plan.objects.create(
        code="composition-console",
        name="Offre console",
        status=Plan.Status.PUBLISHED,
        price_monthly=100,
        monitored_assets=2,
        monthly_scans=10,
        max_users=5,
        watched_accounts=2,
        monthly_watched_account_scans=5,
        features=[features.ANSSI_ASSESSMENT, features.ASSISTANT, features.WATCHED_ACCOUNTS],
    )


@pytest.fixture
def client_compose(tenant, offre):
    Subscription.objects.filter(tenant=tenant).update(plan=offre, status=Subscription.Status.ACTIVE)
    return tenant


def _url(tenant):
    return reverse("platform-client-features", args=[tenant.id])


class TestLire:
    def test_la_fiche_montre_l_herite_et_l_effectif(
        self, api_client, staff_headers, client_compose
    ):
        reponse = api_client.get(_url(client_compose), **staff_headers)

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["has_override"] is False
        lignes = {ligne["key"]: ligne for ligne in reponse.data["features"]}
        assert lignes[features.ASSISTANT]["inherited"] is True
        assert lignes[features.SECRET_REVEAL]["enabled"] is False
        assert lignes[features.ANSSI_ASSESSMENT]["derived_screens"] == [
            "Résultats",
            "Plan d'action",
        ]

    def test_un_client_sans_abonnement_le_dit_plutot_que_de_tomber(
        self, api_client, staff_headers, tenant_factory, user_factory
    ):
        sans_offre = tenant_factory(user_factory(email="sans-offre@example.com"), name="Sans offre")
        Subscription.objects.filter(tenant=sans_offre).delete()

        reponse = api_client.get(_url(sans_offre), **staff_headers)

        assert reponse.status_code == status.HTTP_404_NOT_FOUND
        assert "attribuez-lui une offre" in reponse.data["detail"]


class TestComposer:
    def test_la_composition_s_applique_au_client(self, api_client, staff_headers, client_compose):
        reponse = api_client.put(
            _url(client_compose),
            {"features": [features.ASSISTANT]},
            format="json",
            **staff_headers,
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["has_override"] is True
        abonnement = Subscription.objects.get(tenant=client_compose)
        assert abonnement.effective_features == [features.ASSISTANT]

    def test_chaque_composition_est_tracee_avec_l_avant_et_l_apres(
        self, api_client, staff_headers, client_compose
    ):
        api_client.put(
            _url(client_compose),
            {"features": [features.ASSISTANT]},
            format="json",
            **staff_headers,
        )

        ligne = AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.FEATURES_COMPOSED, tenant=client_compose
        ).first()
        assert ligne is not None
        avant, apres = ligne.changes["features"]
        assert features.ANSSI_ASSESSMENT in avant
        assert apres == [features.ASSISTANT]
        assert ligne.actor.email == "console-composition@example.com"

    def test_une_composition_sans_changement_n_ecrit_pas_au_journal(
        self, api_client, staff_headers, client_compose, offre
    ):
        api_client.put(
            _url(client_compose), {"features": list(offre.features)}, format="json", **staff_headers
        )

        assert not AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.FEATURES_COMPOSED
        ).exists()

    def test_une_combinaison_incoherente_est_refusee_et_expliquee(
        self, api_client, staff_headers, client_compose
    ):
        Subscription.objects.filter(tenant=client_compose).update(override_watched_accounts=0)

        reponse = api_client.put(
            _url(client_compose),
            {"features": [features.WATCHED_ACCOUNTS]},
            format="json",
            **staff_headers,
        )

        assert reponse.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "compte à surveiller" in reponse.data["problemes"][0]
        abonnement = Subscription.objects.get(tenant=client_compose)
        assert abonnement.override_features is None, "un refus ne doit rien écrire"

    def test_le_champ_est_obligatoire(self, api_client, staff_headers, client_compose):
        reponse = api_client.put(_url(client_compose), {}, format="json", **staff_headers)

        assert reponse.status_code == status.HTTP_400_BAD_REQUEST


class TestRevenirALOffre:
    def test_le_retour_efface_la_surcharge_et_se_trace(
        self, api_client, staff_headers, client_compose, offre
    ):
        api_client.put(_url(client_compose), {"features": []}, format="json", **staff_headers)

        reponse = api_client.delete(_url(client_compose), **staff_headers)

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["has_override"] is False
        abonnement = Subscription.objects.get(tenant=client_compose)
        assert abonnement.effective_features == features.sanitize(offre.features)
        assert AdminAuditLog.objects.filter(
            action=AdminAuditLog.Action.FEATURES_RESET, tenant=client_compose
        ).exists()


class TestEtancheiteEtDroits:
    def test_composer_un_client_ne_touche_pas_a_un_autre(
        self, api_client, staff_headers, client_compose, tenant_factory, user_factory, offre
    ):
        autre = tenant_factory(user_factory(email="autre-client@example.com"), name="Autre client")
        Subscription.objects.filter(tenant=autre).update(plan=offre)
        avant = Subscription.objects.get(tenant=autre).effective_features

        api_client.put(_url(client_compose), {"features": []}, format="json", **staff_headers)

        assert Subscription.objects.get(tenant=autre).effective_features == avant

    def test_un_client_ne_compose_pas_son_propre_perimetre(
        self, api_client, client_compose, tenant_owner
    ):
        """L'écran est en console : un membre du client, même administrateur de
        son entreprise, n'a rien à y faire."""
        reponse = api_client.post(
            reverse("token-obtain-pair"),
            {"email": tenant_owner.email, "password": PASSWORD},
            format="json",
        )
        entetes = {"HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}"}

        refus = api_client.put(_url(client_compose), {"features": []}, format="json", **entetes)

        assert refus.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        assert Subscription.objects.get(tenant=client_compose).override_features is None
