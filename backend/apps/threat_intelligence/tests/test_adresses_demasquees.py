"""V2-2 partie B — les adresses ne sont plus masquées, mais elles sont encadrées.

Le RSSI ne peut pas agir sans savoir QUI est concerné : prévenir la personne,
vérifier si le compte est encore actif, juger de la gravité — les trois
demandent l'adresse. L'ADR-014 §4 la réduisait pourtant à une forme non
réversible dès qu'elle n'était pas celle d'un membre de l'espace, c'est-à-dire
précisément dans les cas qui comptent : un ancien salarié, une adresse
personnelle utilisée au bureau, un prestataire.

L'encadrement retenu est **délibérément plus léger** que celui de la
révélation d'un secret (ADR-014, cinq conditions cumulatives). Une adresse
n'est pas un mot de passe : elle ne donne accès à rien. Restent un rôle et une
trace — et ces tests vérifient les deux.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.tenants.models import Membership
from apps.threat_intelligence import services
from apps.threat_intelligence.models import IdentifierAccessAudit
from apps.threat_intelligence.providers.base import RawFinding
from apps.threat_intelligence.serializers import BreachFindingSerializer

pytestmark = pytest.mark.django_db

ADRESSE = "ancien.salarie@fournisseur-mail.example"


def _auth(api_client, user, tenant):
    reponse = api_client.post(
        reverse("token-obtain-pair"),
        {"email": user.email, "password": "Str0ng!Passw0rd123"},
        format="json",
    )
    assert reponse.status_code == status.HTTP_200_OK
    return {
        "HTTP_AUTHORIZATION": f"Bearer {reponse.data['access']}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }


@pytest.fixture
def fuite(tenant, website_asset):
    return services.ingest_raw_findings(
        tenant=tenant,
        asset=website_asset,
        raw_findings=[
            RawFinding(endpoint="creds", payload={"eml": ADRESSE, "pwd": "MotDePasse2024!"})
        ],
    )[0]


@pytest.fixture
def membre(user_factory, tenant):
    """Fabrique un membre du tenant au rôle demandé."""

    def _membre(role, email):
        utilisateur = user_factory(email=email)
        Membership.objects.create(user=utilisateur, tenant=tenant, role=role)
        return utilisateur

    return _membre


class TestLAdresseEstConservee:
    def test_une_adresse_tierce_est_stockee_en_clair(self, fuite):
        """Le cœur du changement : avant, ce champ était vide pour toute
        adresse n'appartenant pas à un membre."""
        assert fuite.identifier_plain == ADRESSE

    def test_la_forme_masquee_est_conservee_elle_aussi(self, fuite):
        """Les deux coexistent : c'est la restitution qui choisit, pas le
        stockage. Masquer en base aurait tranché une fois pour toutes, sans
        retour possible, ce qui se décide légitimement par rôle."""
        assert fuite.identifier_masked
        assert fuite.identifier_masked != fuite.identifier_plain
        assert ADRESSE not in fuite.identifier_masked


class TestLaGardeDeRole:
    @pytest.mark.parametrize("role", [Membership.Role.ADMIN, Membership.Role.CONTRIBUTOR])
    def test_administrateur_et_contributeur_voient_l_adresse(self, fuite, role):
        assert services.identifier_for_viewer(fuite, role=role) == ADRESSE

    def test_le_lecteur_ne_voit_que_la_forme_masquee(self, fuite):
        vu = services.identifier_for_viewer(fuite, role=Membership.Role.READER)

        assert vu == fuite.identifier_masked
        assert ADRESSE not in vu

    def test_sans_role_connu_on_masque(self, fuite):
        """Le défaut sûr est celui qui protège. Un appelant qui oublie de
        passer le rôle ne doit pas publier l'adresse par omission — une garde
        dont l'oubli ouvre l'accès n'est pas une garde."""
        assert services.identifier_for_viewer(fuite, role=None) == fuite.identifier_masked

    def test_le_serialiseur_sans_contexte_masque(self, fuite):
        assert BreachFindingSerializer(fuite).data["identifier"] == fuite.identifier_masked

    def test_les_champs_bruts_ne_sont_plus_exposes(self, fuite):
        """`identifier_plain` était servi tel quel tant que le clair n'existait
        que pour les membres. Le laisser aurait contourné la garde : le
        lecteur aurait reçu l'adresse dans le champ voisin de celui qu'on lui
        masque."""
        champs = set(BreachFindingSerializer(fuite).data)

        assert "identifier_plain" not in champs
        assert "identifier_masked" not in champs
        assert "identifier" in champs


class TestParLApi:
    def test_l_administrateur_recoit_l_adresse(self, api_client, tenant, tenant_owner, fuite):
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(reverse("breach-finding-detail", args=[fuite.id]), **entetes)

        assert reponse.data["identifier"] == ADRESSE

    def test_le_lecteur_ne_recoit_pas_l_adresse(self, api_client, tenant, membre, fuite):
        lecteur = membre(Membership.Role.READER, "lecteur@example.com")
        entetes = _auth(api_client, lecteur, tenant)

        reponse = api_client.get(reverse("breach-finding-detail", args=[fuite.id]), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        assert ADRESSE not in str(reponse.data)

    def test_le_contributeur_recoit_l_adresse(self, api_client, tenant, membre, fuite):
        contributeur = membre(Membership.Role.CONTRIBUTOR, "contrib@example.com")
        entetes = _auth(api_client, contributeur, tenant)

        reponse = api_client.get(reverse("breach-finding-detail", args=[fuite.id]), **entetes)

        assert reponse.data["identifier"] == ADRESSE

    def test_le_fil_d_exposition_suit_la_meme_regle(self, api_client, tenant, membre, fuite):
        lecteur = membre(Membership.Role.READER, "lecteur2@example.com")

        entetes = _auth(api_client, lecteur, tenant)
        vue_lecteur = api_client.get(reverse("breach-exposure-feed"), **entetes)

        assert ADRESSE not in str(vue_lecteur.data)

    def test_un_signal_de_reutilisation_ne_contourne_pas_la_garde(
        self, api_client, tenant, website_asset, membre
    ):
        """L'adresse voyage aussi dans les signaux de corrélation. Sans reprise
        de la règle à cet endroit, elle serait masquée dans la fuite et servie
        en clair dans le signal juste à côté."""
        for endpoint in ("creds", "combo"):
            cle = "eml" if endpoint == "creds" else "usr"
            services.ingest_raw_findings(
                tenant=tenant,
                asset=website_asset,
                raw_findings=[RawFinding(endpoint=endpoint, payload={cle: ADRESSE, "pwd": "x"})],
            )
        lecteur = membre(Membership.Role.READER, "lecteur3@example.com")
        entetes = _auth(api_client, lecteur, tenant)

        reponse = api_client.get(reverse("breach-exposure-feed"), **entetes)

        # Le signal existe bien — ce n'est pas son absence qui protège.
        signaux = [s for groupe in reponse.data["assets"] for s in groupe["reuse_signals"]]
        assert signaux, "le signal de réutilisation doit être présent, sinon le test ne prouve rien"
        assert ADRESSE not in str(reponse.data)


class TestLaTracabilite:
    def test_une_consultation_est_tracee(self, api_client, tenant, tenant_owner, fuite):
        entetes = _auth(api_client, tenant_owner, tenant)

        api_client.get(reverse("breach-finding-detail", args=[fuite.id]), **entetes)

        trace = IdentifierAccessAudit.all_objects.get(tenant=tenant)
        assert trace.user_id == tenant_owner.id  # qui
        assert trace.created_at is not None  # quand
        assert trace.asset_ids == [fuite.asset_id]  # quel actif
        assert trace.identifier_count == 1
        assert trace.context == IdentifierAccessAudit.Context.CONSULTATION

    def test_la_trace_ne_contient_pas_les_adresses(self, api_client, tenant, tenant_owner, fuite):
        """Un journal d'accès qui recopie la donnée consultée double
        l'exposition qu'il est censé encadrer."""
        entetes = _auth(api_client, tenant_owner, tenant)
        api_client.get(reverse("breach-finding-detail", args=[fuite.id]), **entetes)

        trace = IdentifierAccessAudit.all_objects.get(tenant=tenant)
        assert ADRESSE not in str(trace.__dict__)

    def test_la_consultation_d_un_lecteur_n_est_pas_tracee(self, api_client, tenant, membre, fuite):
        """Rien n'a été servi en clair : tracer un accès qui n'a pas eu lieu
        ferait du journal un compteur de pages vues, et lui retirerait sa
        valeur de preuve."""
        lecteur = membre(Membership.Role.READER, "lecteur4@example.com")
        entetes = _auth(api_client, lecteur, tenant)

        api_client.get(reverse("breach-finding-detail", args=[fuite.id]), **entetes)

        assert IdentifierAccessAudit.all_objects.filter(tenant=tenant).count() == 0

    def test_une_page_sans_adresse_n_est_pas_tracee(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        services.ingest_raw_findings(
            tenant=tenant,
            asset=website_asset,
            raw_findings=[
                RawFinding(endpoint="radar", payload={"data": "exemple.fr", "src": "forum"})
            ],
        )
        entetes = _auth(api_client, tenant_owner, tenant)

        api_client.get(reverse("breach-finding-list"), **entetes)

        assert IdentifierAccessAudit.all_objects.filter(tenant=tenant).count() == 0

    def test_la_liste_trace_une_seule_ligne_pour_toute_la_page(
        self, api_client, tenant, tenant_owner, website_asset
    ):
        """Une ligne par adresse ferait, sur un actif réel de production,
        28 450 lignes d'audit pour un seul affichage."""
        for i in range(5):
            services.ingest_raw_findings(
                tenant=tenant,
                asset=website_asset,
                raw_findings=[
                    RawFinding(endpoint="creds", payload={"eml": f"p{i}@exemple.fr", "pwd": "x"})
                ],
            )
        entetes = _auth(api_client, tenant_owner, tenant)

        api_client.get(reverse("breach-finding-list"), **entetes)

        traces = IdentifierAccessAudit.all_objects.filter(tenant=tenant)
        assert traces.count() == 1
        assert traces.first().identifier_count == 5

    def test_l_administrateur_du_tenant_peut_lire_le_journal(
        self, api_client, tenant, tenant_owner, fuite
    ):
        """Une trace que seul l'éditeur peut lire ne prouve rien à celui qui
        en aurait besoin — un salarié, un délégué à la protection des
        données, un auditeur."""
        entetes = _auth(api_client, tenant_owner, tenant)
        api_client.get(reverse("breach-finding-detail", args=[fuite.id]), **entetes)

        reponse = api_client.get(reverse("breach-identifier-audit-list"), **entetes)

        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["results"][0]["identifier_count"] == 1
        assert reponse.data["results"][0]["user_email"] == tenant_owner.email

    def test_le_journal_est_refuse_au_lecteur(self, api_client, tenant, membre):
        lecteur = membre(Membership.Role.READER, "lecteur5@example.com")
        entetes = _auth(api_client, lecteur, tenant)

        reponse = api_client.get(reverse("breach-identifier-audit-list"), **entetes)

        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_le_journal_est_cloisonne_par_entreprise(
        self, api_client, tenant, tenant_owner, fuite, user_factory, tenant_factory
    ):
        entetes = _auth(api_client, tenant_owner, tenant)
        api_client.get(reverse("breach-finding-detail", args=[fuite.id]), **entetes)

        autre = user_factory(email="autre@example.com")
        autre_tenant = tenant_factory(autre, name="Autre Entreprise")
        entetes_autre = _auth(api_client, autre, autre_tenant)

        reponse = api_client.get(reverse("breach-identifier-audit-list"), **entetes_autre)

        assert reponse.data["results"] == []


class TestLesSecretsRestentProteges:
    """Ce que la V2-2 ne change PAS : le mot de passe et le cookie de session
    restent masqués et soumis à la procédure de révélation."""

    def test_le_mot_de_passe_reste_masque_pour_l_administrateur(
        self, api_client, tenant, tenant_owner, fuite
    ):
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(reverse("breach-finding-detail", args=[fuite.id]), **entetes)

        assert "MotDePasse2024!" not in str(reponse.data)
        assert reponse.data["secret_masked"].startswith("•")
        assert reponse.data["has_secret"] is True

    def test_le_secret_n_apparait_pas_dans_les_champs_restitues(
        self, api_client, tenant, website_asset, tenant_owner
    ):
        """Les champs restitués viennent de `raw_data`, donc de la charge DÉJÀ
        masquée : un secret ne peut pas ressortir par ce chemin même si un
        champ secret se glissait dans une liste blanche."""
        services.ingest_raw_findings(
            tenant=tenant,
            asset=website_asset,
            raw_findings=[
                RawFinding(
                    endpoint="sessions",
                    payload={
                        "user_name": "marie",
                        "val": "SECRET-COOKIE-REEL",
                        "dom": "outil.example",
                        "cookie_name": "session_id",
                    },
                )
            ],
        )
        entetes = _auth(api_client, tenant_owner, tenant)

        reponse = api_client.get(reverse("breach-finding-list"), **entetes)

        assert "SECRET-COOKIE-REEL" not in str(reponse.data)
