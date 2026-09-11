"""Lot B — la chaîne référentiel, rendue utilisable.

Le compteur « Clients » du catalogue affichait **0 pour tous les
référentiels**, alors que sept attributions actives existaient en production.

La cause n'était pas dans la donnée : ``Referential.assignments`` traverse la
relation inverse, donc le manager PAR DÉFAUT de ``ReferentialAssignment``,
qui est scopé par tenant et « échoue fermé » — sans tenant dans le contexte,
il renvoie vide. La console d'administration n'en a pas.

C'est la classe de défaut la plus coûteuse de ce projet : une garde de
sécurité qui fait correctement son travail, un appelant qui aurait dû
utiliser ``all_objects``, et un chiffre faux que rien ne signale. Ces tests
l'épinglent là où il s'est produit, et interdisent qu'il revienne.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.assessments import services
from apps.assessments.models import ReferentialAssignment
from apps.platform_admin.models import PlatformAdminProfile

pytestmark = pytest.mark.django_db


@pytest.fixture
def exploitant(user_factory):
    user = user_factory(email="catalogue@example.com", is_staff=True)
    PlatformAdminProfile.objects.create(user=user, level=PlatformAdminProfile.Level.FULL)
    return user


def _auth(api_client, user):
    response = api_client.post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": "Str0ng!Passw0rd123"},
        format="json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {response.data['access']}"}


class TestCompteurDuCatalogue:
    """B1.1 — le compteur doit dire la vérité."""

    def test_le_catalogue_compte_les_clients_attribues(
        self, api_client, exploitant, referential, tenant
    ):
        services.assign_referential(tenant=tenant, referential=referential, granted_by=exploitant)

        response = api_client.get(
            reverse("platform-referential-list"), **_auth(api_client, exploitant)
        )

        ligne = next(r for r in response.data if r["slug"] == referential.slug)
        assert ligne["assigned_tenants"] == 1

    def test_le_compteur_ne_depend_pas_d_un_tenant_en_contexte(
        self, api_client, exploitant, referential, tenant, tenant_factory, user_factory
    ):
        """LE test de non-régression.

        La console n'a pas de tenant en contexte. Un compteur qui passerait
        par le manager scopé y renverrait 0 sans que rien ne le signale —
        c'est exactement ce qui se produisait.
        """
        autre_owner = user_factory(email="autre-catalogue@example.com")
        autre = tenant_factory(autre_owner, name="Autre Client")
        services.assign_referential(tenant=tenant, referential=referential, granted_by=exploitant)
        services.assign_referential(tenant=autre, referential=referential, granted_by=exploitant)

        response = api_client.get(
            reverse("platform-referential-list"), **_auth(api_client, exploitant)
        )

        ligne = next(r for r in response.data if r["slug"] == referential.slug)
        assert ligne["assigned_tenants"] == 2

    def test_une_attribution_retiree_ne_compte_plus(
        self, api_client, exploitant, referential, tenant
    ):
        services.assign_referential(tenant=tenant, referential=referential, granted_by=exploitant)
        services.revoke_referential(tenant=tenant, referential=referential, revoked_by=exploitant)

        response = api_client.get(
            reverse("platform-referential-list"), **_auth(api_client, exploitant)
        )

        ligne = next(r for r in response.data if r["slug"] == referential.slug)
        assert ligne["assigned_tenants"] == 0
        # Retrait LOGIQUE : la ligne existe toujours, l'historique du client
        # n'est pas detruit.
        assert ReferentialAssignment.all_objects.filter(tenant=tenant).exists()


class TestAucunCheminDeRepli:
    """B1.1 — aucun contournement silencieux de la garde d'attribution."""

    def test_un_client_sans_attribution_n_a_pas_de_referentiel_par_defaut(self, tenant):
        with pytest.raises(services.NoActiveReferentialError):
            services.get_default_referential(tenant)

    def test_la_porte_derobee_a_ete_retiree(self):
        """``get_active_referential`` prenait « le référentiel actif de la
        plateforme » sans rien savoir des attributions. Zéro appelant dans
        tout le dépôt, tests compris : du code mort qui documentait un
        contournement. Le laisser, c'était attendre qu'on s'en serve."""
        assert not hasattr(services, "get_active_referential")

    def test_le_diagnostic_refuse_de_demarrer_sans_attribution(
        self, api_client, tenant, tenant_owner
    ):
        response = api_client.post(
            reverse("assessment-start"),
            {},
            format="json",
            **{
                "HTTP_AUTHORIZATION": f"Bearer {api_client.post(reverse('token-obtain-pair'), {'email': tenant_owner.email, 'password': 'Str0ng!Passw0rd123'}, format='json').data['access']}",
                "HTTP_X_TENANT_ID": str(tenant.id),
            },
        )

        # 503 et non 500 : l'indisponibilite est ASSUMEE et temporaire — il
        # manque une attribution, pas un bout de code. Le message servi au
        # client le dit sans nommer notre outillage, et le detail exploitable
        # part dans les journaux.
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "attribu" in str(response.data).lower()
