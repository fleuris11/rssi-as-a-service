"""Lot C, point 20 — le centre de notifications (ADR-037).

Le mécanisme, une fois, générique : qui reçoit, qui peut lire, et ce qu'on ne
reçoit jamais deux fois. Les branchements métier ont leurs propres tests dans
``test_inbox_branchements.py``.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.notifications import inbox
from apps.notifications.models import Notification
from apps.tenants.models import Membership

pytestmark = pytest.mark.django_db


def _login(api_client, email, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}


@pytest.fixture
def exploitant(user_factory):
    return user_factory(email="exploitant@example.com", is_staff=True)


class TestDestinataires:
    def test_les_administrateurs_actifs_du_client_sont_prevenus(
        self, tenant, tenant_owner, user_factory
    ):
        contributeur = user_factory(email="contrib-inbox@example.com")
        Membership.all_objects.create(
            tenant=tenant, user=contributeur, role=Membership.Role.CONTRIBUTOR
        )
        parti = user_factory(email="parti-inbox@example.com", is_active=False)
        Membership.all_objects.create(tenant=tenant, user=parti, role=Membership.Role.ADMIN)

        cree = inbox.notify_tenant_admins(
            tenant, kind=inbox.Kind.COMMITTEE_REPORT_READY, title="Rapport prêt"
        )

        assert cree == 1
        assert Notification.objects.get().recipient == tenant_owner

    def test_l_exploitant_est_prevenu_sans_client_rattache(self, exploitant, tenant_owner):
        inbox.notify_staff(kind=inbox.Kind.ACCESS_REQUEST_NEW, title="Nouvelle demande")

        notification = Notification.objects.get()
        assert notification.recipient == exploitant
        assert notification.tenant is None

    def test_un_meme_evenement_ne_notifie_pas_deux_fois(self, tenant, tenant_owner):
        for _ in range(3):
            inbox.notify_tenant_admins(
                tenant,
                kind=inbox.Kind.COMMITTEE_REPORT_READY,
                title="Rapport de septembre prêt",
                dedupe_key=f"comite:{tenant.id}:2026-09",
            )

        assert Notification.objects.count() == 1


class TestCeQuOnPeutLire:
    def test_personne_ne_lit_les_notifications_d_un_autre(
        self, api_client, tenant, tenant_owner, user_factory
    ):
        autre = user_factory(email="autre-inbox@example.com")
        inbox.notify([autre], kind=inbox.Kind.ACCESS_REQUEST_UPDATED, title="Secret de l'autre")

        response = api_client.get(
            reverse("notification-inbox"), **_login(api_client, tenant_owner.email)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_un_ancien_membre_ne_voit_plus_ce_qui_concerne_le_client(
        self, tenant, tenant_owner, user_factory
    ):
        ancien = user_factory(email="ancien-inbox@example.com")
        adhesion = Membership.all_objects.create(
            tenant=tenant, user=ancien, role=Membership.Role.ADMIN
        )
        inbox.notify([ancien], tenant=tenant, kind=inbox.Kind.WATCHED_FINDINGS_NEW, title="Fuite")
        assert inbox.unread_count(ancien) == 1

        adhesion.delete()

        assert inbox.unread_count(ancien) == 0
        assert not inbox.list_for_user(ancien).exists()

    def test_un_client_ne_voit_jamais_les_notifications_d_exploitant(
        self, tenant, tenant_owner, exploitant
    ):
        inbox.notify_staff(kind=inbox.Kind.ACCESS_REQUEST_NEW, title="Demande de Cabinet X")

        assert inbox.unread_count(tenant_owner) == 0

    def test_marquer_comme_lu_ne_touche_que_les_siennes(
        self, api_client, tenant, tenant_owner, user_factory
    ):
        autre = user_factory(email="autre2-inbox@example.com")
        inbox.notify([autre], kind=inbox.Kind.ACCESS_REQUEST_UPDATED, title="À l'autre")
        a_l_autre = Notification.objects.get()

        response = api_client.post(
            reverse("notification-inbox-read"),
            {"ids": [a_l_autre.id]},
            format="json",
            **_login(api_client, tenant_owner.email),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 0
        a_l_autre.refresh_from_db()
        assert a_l_autre.read_at is None


class TestApi:
    def test_la_cloche_compte_les_non_lues(self, api_client, tenant, tenant_owner):
        for i in range(3):
            inbox.notify_tenant_admins(
                tenant, kind=inbox.Kind.WATCHED_FINDINGS_NEW, title=f"Fuite {i}"
            )

        response = api_client.get(
            reverse("notification-inbox-count"), **_login(api_client, tenant_owner.email)
        )

        assert response.data == {"unread": 3}

    def test_la_liste_se_filtre_et_se_cherche(self, api_client, tenant, tenant_owner):
        inbox.notify_tenant_admins(
            tenant, kind=inbox.Kind.WATCHED_FINDINGS_NEW, title="Fuite sur la compta"
        )
        inbox.notify_tenant_admins(
            tenant, kind=inbox.Kind.COMMITTEE_REPORT_READY, title="Rapport prêt"
        )
        entetes = _login(api_client, tenant_owner.email)
        api_client.post(
            reverse("notification-inbox-read"),
            {"ids": [Notification.objects.get(title="Rapport prêt").id]},
            format="json",
            **entetes,
        )

        non_lues = api_client.get(reverse("notification-inbox"), {"unread": "1"}, **entetes)
        recherche = api_client.get(reverse("notification-inbox"), {"q": "compta"}, **entetes)

        assert [n["title"] for n in non_lues.data["results"]] == ["Fuite sur la compta"]
        assert [n["title"] for n in recherche.data["results"]] == ["Fuite sur la compta"]

    def test_tout_marquer_comme_lu(self, api_client, tenant, tenant_owner):
        for i in range(2):
            inbox.notify_tenant_admins(tenant, kind=inbox.Kind.WATCHED_FINDINGS_NEW, title=f"F{i}")
        entetes = _login(api_client, tenant_owner.email)

        response = api_client.post(
            reverse("notification-inbox-read"), {"all": True}, format="json", **entetes
        )

        assert response.data["updated"] == 2
        assert inbox.unread_count(tenant_owner) == 0

    def test_la_cloche_exige_une_connexion(self, api_client):
        response = api_client.get(reverse("notification-inbox-count"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
