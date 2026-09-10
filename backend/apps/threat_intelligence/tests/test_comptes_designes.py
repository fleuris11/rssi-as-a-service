"""Comptes désignés (V2-6, ADR-033).

Trois familles, et la première est celle qui compte le plus : faire surveiller
l'adresse d'un tiers est un traitement de données personnelles de ce tiers. Le
produit n'a pas à juger le fondement invoqué — il a à l'exiger, à le figer et à
le conserver. Ces tests interdisent les trois façons de le contourner :
déclarer sans cocher, déclarer sans finalité, et perdre la déclaration en
retirant le compte.

La deuxième famille tient la séparation d'avec l'exposition générale. Elle est
structurelle (deux tables), mais une table séparée dont on remplirait quand
même le score d'exposition ne servirait à rien : on le vérifie.
"""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.threat_intelligence import services
from apps.threat_intelligence.models import (
    BreachFinding,
    BreachScanJob,
    WatchedAccount,
    WatchedAccountFinding,
)
from apps.threat_intelligence.providers.base import RawFinding, ScanResult

pytestmark = pytest.mark.django_db


def _login(api_client, email, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


def _auth(api_client, user, tenant):
    return {
        "HTTP_AUTHORIZATION": f"Bearer {_login(api_client, user.email)}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


@pytest.fixture
def offre_avec_comptes(tenant):
    """L'offre du client comprend la surveillance de comptes, avec de quoi en
    déclarer trois et lancer cinq analyses."""
    from apps.billing import entitlements

    abonnement = entitlements.get_subscription(tenant)
    abonnement.override_features = [*abonnement.effective_features, "watched_accounts"]
    abonnement.override_watched_accounts = 3
    abonnement.override_monthly_watched_account_scans = 5
    abonnement.save(
        update_fields=[
            "override_features",
            "override_watched_accounts",
            "override_monthly_watched_account_scans",
        ]
    )
    return abonnement


@pytest.fixture
def compte(tenant, tenant_owner, offre_avec_comptes):
    return services.declare_watched_account(
        tenant=tenant,
        user=tenant_owner,
        value="Directrice@Exemple.FR",
        label="Directrice générale",
        category=WatchedAccount.Category.EXECUTIVE,
        legal_basis=WatchedAccount.LegalBasis.COMPANY,
        purpose="Compte exposé aux tentatives de fraude au virement.",
        declaration_accepted=True,
    )


def _fuite_stealer(email="directrice@exemple.fr"):
    return ScanResult(
        findings=[
            RawFinding(
                endpoint="stealer",
                payload={"email": email, "password": "MotDePasse2024!", "date": "2026-05-01"},
            )
        ],
        requests_consumed=1,
        remaining_quota=900,
    )


# --- La déclaration ---------------------------------------------------------


class TestDeclaration:
    def test_enregistre_qui_declare_quoi_quand_et_pourquoi(self, compte, tenant_owner):
        """Les quatre éléments exigés par la consigne V2-6, point 4."""
        assert compte.declared_by == tenant_owner
        assert compte.declared_at is not None
        assert compte.value == "directrice@exemple.fr"
        assert compte.purpose.startswith("Compte exposé")
        assert compte.legal_basis == WatchedAccount.LegalBasis.COMPANY

    def test_fige_le_texte_exact_accepte(self, compte):
        """Le jour où l'on reformulera cet engagement, ce qu'a réellement
        accepté ce client-là ne doit pas changer rétroactivement."""
        assert compte.declaration_text == services.DECLARATION_TEXT
        assert compte.declaration_version == services.DECLARATION_VERSION
        assert "traitement de données personnelles" in compte.declaration_text

    def test_refuse_sans_declaration(self, tenant, tenant_owner, offre_avec_comptes):
        with pytest.raises(services.DeclarationRequiredError):
            services.declare_watched_account(
                tenant=tenant,
                user=tenant_owner,
                value="quelquun@exemple.fr",
                legal_basis=WatchedAccount.LegalBasis.COMPANY,
                purpose="Une raison.",
                declaration_accepted=False,
            )
        assert WatchedAccount.all_objects.count() == 0

    def test_refuse_sans_finalite(self, tenant, tenant_owner, offre_avec_comptes):
        """Une finalité vide rendrait la déclaration ininterprétable le jour
        où quelqu'un la relit — y compris la personne concernée."""
        with pytest.raises(services.DeclarationRequiredError):
            services.declare_watched_account(
                tenant=tenant,
                user=tenant_owner,
                value="quelquun@exemple.fr",
                legal_basis=WatchedAccount.LegalBasis.COMPANY,
                purpose="   ",
                declaration_accepted=True,
            )

    def test_l_api_exige_la_declaration_aussi(
        self, api_client, tenant, tenant_owner, offre_avec_comptes
    ):
        """Une garde de formulaire protège la saisie, pas l'API : un appel
        direct doit rencontrer la même exigence."""
        response = api_client.post(
            reverse("ti-watched-account-list"),
            {
                "value": "contournement@exemple.fr",
                "legal_basis": "company",
                "purpose": "Sans cocher la case.",
                "declaration_accepted": False,
            },
            format="json",
            **_auth(api_client, tenant_owner, tenant),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert WatchedAccount.all_objects.count() == 0

    def test_le_retrait_conserve_la_declaration(self, compte, tenant_owner):
        """C'est la trace qu'on montre à la personne concernée si elle demande
        depuis quand — et jusqu'à quand — son compte a été surveillé."""
        services.remove_watched_account(compte, user=tenant_owner, reason="Départ de l'entreprise")

        compte.refresh_from_db()
        assert compte.is_active is False
        assert compte.removed_at is not None
        assert compte.removed_by == tenant_owner
        # La déclaration d'origine est intacte.
        assert compte.declaration_text == services.DECLARATION_TEXT
        assert compte.declared_at is not None

    def test_le_meme_compte_ne_se_declare_pas_deux_fois(
        self, compte, tenant, tenant_owner, offre_avec_comptes
    ):
        """Casse et espaces normalisés : sinon le même compte compterait deux
        fois dans le quota et serait analysé deux fois."""
        with pytest.raises(services.WatchedAccountError):
            services.declare_watched_account(
                tenant=tenant,
                user=tenant_owner,
                value="  DIRECTRICE@exemple.fr ",
                legal_basis=WatchedAccount.LegalBasis.COMPANY,
                purpose="Doublon.",
                declaration_accepted=True,
            )

    def test_un_compte_retire_peut_etre_redeclare(
        self, compte, tenant, tenant_owner, offre_avec_comptes
    ):
        """Et c'est une NOUVELLE déclaration, avec sa propre date et sa propre
        finalité."""
        services.remove_watched_account(compte, user=tenant_owner)

        nouveau = services.declare_watched_account(
            tenant=tenant,
            user=tenant_owner,
            value="directrice@exemple.fr",
            legal_basis=WatchedAccount.LegalBasis.CONSENT,
            purpose="Nouvelle finalité, nouvel accord.",
            declaration_accepted=True,
        )

        assert nouveau.id != compte.id
        assert nouveau.legal_basis == WatchedAccount.LegalBasis.CONSENT
        assert WatchedAccount.all_objects.filter(tenant=tenant).count() == 2

    def test_le_retrait_n_est_jamais_garde_par_l_offre(
        self, api_client, compte, tenant, tenant_owner, offre_avec_comptes
    ):
        """Arrêter de traiter les données d'un tiers ne doit dépendre d'aucun
        abonnement. C'est le point le plus important de cet écran."""
        offre_avec_comptes.override_features = [
            cle for cle in offre_avec_comptes.effective_features if cle != "watched_accounts"
        ]
        offre_avec_comptes.save(update_fields=["override_features"])

        response = api_client.delete(
            reverse("ti-watched-account-detail", args=[compte.id]),
            **_auth(api_client, tenant_owner, tenant),
        )

        assert response.status_code == status.HTTP_200_OK
        compte.refresh_from_db()
        assert compte.is_active is False

    def test_la_liste_reste_lisible_hors_offre(
        self, api_client, compte, tenant, tenant_owner, offre_avec_comptes
    ):
        """Corollaire : on ne peut pas retirer ce qu'on ne voit plus."""
        offre_avec_comptes.override_features = [
            cle for cle in offre_avec_comptes.effective_features if cle != "watched_accounts"
        ]
        offre_avec_comptes.save(update_fields=["override_features"])

        response = api_client.get(
            reverse("ti-watched-account-list"), **_auth(api_client, tenant_owner, tenant)
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1


# --- Séparation d'avec l'exposition générale --------------------------------


class TestSeparation:
    @pytest.fixture
    def resultat(self, tenant, compte):
        services.execute_watched_account_scan(tenant=tenant, accounts=[compte])
        return WatchedAccountFinding.all_objects.get(tenant=tenant)

    @pytest.fixture(autouse=True)
    def _provider(self):
        with patch("apps.threat_intelligence.watched_accounts.get_provider") as fabrique:
            fabrique.return_value.scan_email.return_value = _fuite_stealer()
            yield fabrique

    def test_le_resultat_n_est_pas_une_fuite_d_actif(self, resultat, tenant):
        """Ce ne sont pas ses actifs : la liste des compromissions ne doit
        pas en contenir un seul."""
        assert BreachFinding.all_objects.filter(tenant=tenant).count() == 0
        assert resultat.account.value == "directrice@exemple.fr"

    def test_n_entre_pas_dans_le_score_d_exposition(self, resultat, tenant):
        from django.utils import timezone

        maintenant = timezone.now()
        indicateurs = services.breach_indicators(
            tenant, start=maintenant - timezone.timedelta(days=30), end=maintenant
        )
        assert indicateurs["open_total"] == 0

    def test_n_ouvre_aucune_alerte_de_surveillance(self, resultat, tenant):
        """Une alerte se pose sur un actif déclaré, et un compte désigné n'en
        est pas un."""
        from apps.monitoring.models import Alert

        assert Alert.all_objects.filter(tenant=tenant).count() == 0

    def test_n_entre_pas_dans_le_registre_des_incidents(self, resultat, tenant, tenant_owner):
        """Le registre (V2-5) part des fuites sur actifs. Un compte désigné
        appartient à quelqu'un d'autre : le faire figurer au registre des
        incidents de l'entreprise serait un contresens."""
        from apps.ai_assistant import services as ai_services

        document = ai_services.compose_document(
            tenant=tenant, user=tenant_owner, document_type="incident_register"
        )
        assert "directrice@exemple.fr" not in document.content_markdown
        assert "Aucun événement détecté" in document.content_markdown

    def test_aucun_secret_n_est_conserve(self, resultat):
        """Révéler le mot de passe du compte d'un tiers est une tout autre
        affaire que révéler celui d'un compte de l'entreprise (ADR-014). Il
        n'y a donc aucune colonne à révéler."""
        assert resultat.has_secret is True
        assert not hasattr(resultat, "secret_encrypted")
        assert "MotDePasse2024!" not in str(resultat.raw_data)
        assert "MotDePasse2024!" != resultat.secret_masked


# --- Analyse à la demande et quotas -----------------------------------------


class TestAnalyse:
    @pytest.fixture(autouse=True)
    def _provider(self):
        with patch("apps.threat_intelligence.watched_accounts.get_provider") as fabrique:
            fabrique.return_value.scan_email.return_value = _fuite_stealer()
            yield fabrique

    def test_analyse_un_compte_et_enregistre_le_resultat(self, tenant, compte):
        rapport = services.execute_watched_account_scan(tenant=tenant, accounts=[compte])

        assert rapport["findings_created"] == 1
        assert rapport["accounts_scanned"] == 1
        compte.refresh_from_db()
        assert compte.last_scanned_at is not None

    def test_une_seconde_analyse_ne_duplique_pas(self, tenant, compte):
        services.execute_watched_account_scan(tenant=tenant, accounts=[compte])
        rapport = services.execute_watched_account_scan(tenant=tenant, accounts=[compte])

        assert rapport["findings_created"] == 0
        assert rapport["findings_seen_again"] == 1
        assert WatchedAccountFinding.all_objects.filter(tenant=tenant).count() == 1

    def test_un_compte_en_echec_ne_fait_pas_tomber_les_autres(
        self, tenant, tenant_owner, compte, offre_avec_comptes, _provider
    ):
        """Leçon du 06/09/2026 : un lot qui perd tout à cause d'un élément est
        un lot mal conçu."""
        second = services.declare_watched_account(
            tenant=tenant,
            user=tenant_owner,
            value="autre@exemple.fr",
            legal_basis=WatchedAccount.LegalBasis.COMPANY,
            purpose="Deuxième compte.",
            declaration_accepted=True,
        )
        _provider.return_value.scan_email.side_effect = [
            RuntimeError("le fournisseur a répondu 500"),
            _fuite_stealer("autre@exemple.fr"),
        ]

        rapport = services.execute_watched_account_scan(tenant=tenant, accounts=[compte, second])

        assert rapport["accounts_failed"] == 1
        assert rapport["findings_created"] == 1

    def test_l_usage_ne_decompte_pas_le_quota_des_actifs(self, tenant, compte):
        """Le quota VIP est vendu à part. Le confondre avec celui des actifs
        viderait le quota général du client sans qu'il comprenne pourquoi."""
        from apps.billing import entitlements

        services.execute_watched_account_scan(tenant=tenant, accounts=[compte])

        assert entitlements.watched_account_scans_used(tenant) == 1
        assert entitlements.monthly_scans_used(tenant) == 0

    def test_le_quota_de_comptes_est_applique(self, tenant, tenant_owner, offre_avec_comptes):
        from apps.billing import entitlements

        for numero in range(3):
            services.declare_watched_account(
                tenant=tenant,
                user=tenant_owner,
                value=f"compte{numero}@exemple.fr",
                legal_basis=WatchedAccount.LegalBasis.COMPANY,
                purpose="Test de quota.",
                declaration_accepted=True,
            )

        with pytest.raises(entitlements.EntitlementError):
            services.declare_watched_account(
                tenant=tenant,
                user=tenant_owner,
                value="celui-de-trop@exemple.fr",
                legal_basis=WatchedAccount.LegalBasis.COMPANY,
                purpose="Le quatrième.",
                declaration_accepted=True,
            )

    def test_le_quota_d_analyses_est_applique(
        self, api_client, tenant, tenant_owner, compte, offre_avec_comptes
    ):
        offre_avec_comptes.override_monthly_watched_account_scans = 1
        offre_avec_comptes.save(update_fields=["override_monthly_watched_account_scans"])
        services.execute_watched_account_scan(tenant=tenant, accounts=[compte])

        response = api_client.post(
            reverse("ti-watched-account-scan"),
            {"account_ids": [compte.id]},
            format="json",
            **_auth(api_client, tenant_owner, tenant),
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED


# --- API --------------------------------------------------------------------


class TestApi:
    def test_declare_depuis_l_espace_client(
        self, api_client, tenant, tenant_owner, offre_avec_comptes
    ):
        response = api_client.post(
            reverse("ti-watched-account-list"),
            {
                "value": "president@exemple.fr",
                "label": "Président",
                "category": "executive",
                "legal_basis": "company",
                "purpose": "Cible probable d'une fraude au président.",
                "declaration_accepted": True,
            },
            format="json",
            **_auth(api_client, tenant_owner, tenant),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["legal_basis_label"]
        assert response.data["purpose"].startswith("Cible probable")

    def test_expose_le_texte_de_declaration_a_l_ecran(
        self, api_client, tenant, tenant_owner, offre_avec_comptes
    ):
        """L'écran doit afficher le texte que le client s'apprête à accepter,
        et non un renvoi à des conditions générales lues il y a six mois."""
        response = api_client.get(
            reverse("ti-watched-account-list"), **_auth(api_client, tenant_owner, tenant)
        )

        assert response.data["declaration_text"] == services.DECLARATION_TEXT
        assert response.data["declaration_version"] == services.DECLARATION_VERSION

    def test_hors_offre_la_declaration_est_refusee(self, api_client, tenant, tenant_owner):
        response = api_client.post(
            reverse("ti-watched-account-list"),
            {
                "value": "quelquun@exemple.fr",
                "legal_basis": "company",
                "purpose": "Sans l'offre.",
                "declaration_accepted": True,
            },
            format="json",
            **_auth(api_client, tenant_owner, tenant),
        )

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED

    def test_lance_une_analyse_et_renvoie_un_job(
        self, api_client, tenant, tenant_owner, compte, offre_avec_comptes
    ):
        with patch("apps.threat_intelligence.views.run_watched_account_scan_task.delay") as delay:
            response = api_client.post(
                reverse("ti-watched-account-scan"),
                {"account_ids": [compte.id]},
                format="json",
                **_auth(api_client, tenant_owner, tenant),
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        delay.assert_called_once()
        job = BreachScanJob.all_objects.get(tenant=tenant)
        assert job.scope == BreachScanJob.Scope.WATCHED_ACCOUNTS
        assert job.result_ref["account_ids"] == [compte.id]

    def test_le_lecteur_ne_declare_pas(self, api_client, tenant, user_factory, offre_avec_comptes):
        from apps.tenants.models import Membership

        lecteur = user_factory(email="lecteur-vip@example.com")
        Membership.all_objects.create(tenant=tenant, user=lecteur, role=Membership.Role.READER)

        response = api_client.post(
            reverse("ti-watched-account-list"),
            {
                "value": "x@exemple.fr",
                "legal_basis": "company",
                "purpose": "Test.",
                "declaration_accepted": True,
            },
            format="json",
            **_auth(api_client, lecteur, tenant),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestEtancheite:
    def test_un_client_ne_voit_pas_les_comptes_du_voisin(
        self, api_client, compte, tenant_factory, user_factory
    ):
        voisin_owner = user_factory(email="voisin-vip@example.com")
        voisin = tenant_factory(voisin_owner, name="Voisin")

        response = api_client.get(
            reverse("ti-watched-account-list"), **_auth(api_client, voisin_owner, voisin)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []

    def test_un_client_ne_peut_pas_retirer_le_compte_du_voisin(
        self, api_client, compte, tenant_factory, user_factory
    ):
        voisin_owner = user_factory(email="voisin-vip2@example.com")
        voisin = tenant_factory(voisin_owner, name="Voisin")

        response = api_client.delete(
            reverse("ti-watched-account-detail", args=[compte.id]),
            **_auth(api_client, voisin_owner, voisin),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        compte.refresh_from_db()
        assert compte.is_active is True

    def test_les_resultats_sont_cloisonnes(
        self, api_client, tenant, compte, tenant_factory, user_factory
    ):
        with patch("apps.threat_intelligence.watched_accounts.get_provider") as fabrique:
            fabrique.return_value.scan_email.return_value = _fuite_stealer()
            services.execute_watched_account_scan(tenant=tenant, accounts=[compte])

        voisin_owner = user_factory(email="voisin-vip3@example.com")
        voisin = tenant_factory(voisin_owner, name="Voisin")

        response = api_client.get(
            reverse("ti-watched-account-finding-list"),
            **_auth(api_client, voisin_owner, voisin),
        )

        assert response.data == []
