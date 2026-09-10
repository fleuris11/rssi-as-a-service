"""V2-1 partie B — on ne surveille en continu que ce qu'on possède (ADR-026).

Le défaut couvert ici s'est produit en production : un client a déclaré, puis
fait surveiller, le domaine d'une autre organisation. ADR-010 posait « un
actif n'est vérifié que s'il est déclaré » — la production a montré que
**déclarer n'est pas posséder**.

Les tests séparent les deux gestes que la décision distingue : la
surveillance continue, qui exige une preuve, et l'analyse ponctuelle, qui se
contente d'une déclaration sur l'honneur mais la trace.
"""

from unittest.mock import patch

import pytest
import requests
from django.core import mail
from django.urls import reverse
from rest_framework import status

from apps.monitoring import services
from apps.monitoring.checks import ownership as ownership_checks
from apps.monitoring.checks.ssrf import SSRFError
from apps.monitoring.models import Asset, AssetOwnershipAttestation, AssetOwnershipProof

pytestmark = pytest.mark.django_db

METHODE = AssetOwnershipProof.Method
ETAT = AssetOwnershipProof.Status


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
def actif(tenant, tenant_owner):
    return services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://example.com",
        ownership_confirmed=True,
    )


def _reponse(*, status_code=200, content=b""):
    reponse = requests.Response()
    reponse.status_code = status_code
    reponse._content = content
    return reponse


class TestDeclarationSurLHonneurTracee:
    """Point 6 : l'analyse ponctuelle reste possible sans preuve, mais la
    déclaration est tracée — qui, quand, quel actif."""

    def test_declarer_un_actif_ecrit_la_declaration(self, tenant, tenant_owner):
        actif = services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.WEBSITE,
            value="https://example.com",
            ownership_confirmed=True,
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0",
        )

        declaration = AssetOwnershipAttestation.all_objects.get(asset=actif)
        assert declaration.user_id == tenant_owner.id
        assert declaration.asset_id == actif.id
        assert declaration.created_at is not None
        assert declaration.ip_address == "203.0.113.7"

    def test_le_texte_exact_accepte_est_conserve(self, actif):
        """Une déclaration doit pouvoir être relue dans les termes où elle a
        été présentée — un renvoi vers un libellé qui a changé depuis ne
        prouverait rien."""
        declaration = AssetOwnershipAttestation.all_objects.get(asset=actif)

        assert "habilité" in declaration.statement
        assert declaration.statement == services.ownership_messages.ATTESTATION_STATEMENT

    def test_la_case_non_cochee_ne_cree_ni_actif_ni_declaration(self, tenant, tenant_owner):
        with pytest.raises(services.InvalidAssetError):
            services.create_asset(
                tenant=tenant,
                user=tenant_owner,
                type=Asset.Type.WEBSITE,
                value="https://example.com",
                ownership_confirmed=False,
            )

        assert Asset.all_objects.count() == 0
        assert AssetOwnershipAttestation.all_objects.count() == 0

    def test_l_analyse_ponctuelle_reste_possible_sans_preuve(self, actif):
        """Ce que la décision NE fait pas : bloquer l'analyse ponctuelle.
        Elle n'exige qu'une déclaration, que la déclaration de l'actif a déjà
        produite."""
        assert services.is_ownership_proven(actif) is False
        assert services.ownership_state(actif) == "declared"


class TestLaSurveillanceContinueExigeUnePreuve:
    def test_la_garde_refuse_un_actif_seulement_declare(self, actif):
        with pytest.raises(services.OwnershipNotProvenError):
            services.ensure_ownership_proven(actif)

    def test_la_garde_laisse_passer_un_actif_prouve(self, actif):
        proof = services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT)
        with patch.object(
            ownership_checks, "verify_dns_txt", return_value=(True, "Enregistrement TXT trouvé.")
        ):
            services.verify_ownership_proof(proof)

        services.ensure_ownership_proven(actif)  # ne lève pas
        assert services.ownership_state(actif) == "proven"

    def test_le_refus_dit_au_client_quoi_faire(self, actif):
        """Un refus qui ne dit pas comment en sortir est une impasse."""
        with pytest.raises(services.OwnershipNotProvenError) as exc:
            services.ensure_ownership_proven(actif)

        message = str(exc.value)
        assert "DNS" in message
        assert "fichier" in message
        assert "email" in message
        assert "ponctuelle" in message


class TestVerificationParEnregistrementDNS:
    def test_le_bon_enregistrement_prouve_la_possession(self, actif):
        proof = services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT)
        attendu = ownership_checks.expected_dns_record(proof.token)

        with patch.object(ownership_checks, "_txt_records", return_value=["v=spf1 -all", attendu]):
            proof = services.verify_ownership_proof(proof)

        assert proof.status == ETAT.VERIFIED
        assert proof.verified_at is not None

    def test_un_jeton_d_une_tentative_precedente_ne_vaut_plus(self, actif):
        proof = services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT)
        ancien = ownership_checks.expected_dns_record("jeton-perime")

        with patch.object(ownership_checks, "_txt_records", return_value=[ancien]):
            proof = services.verify_ownership_proof(proof)

        assert proof.status == ETAT.FAILED
        # Le message distingue « rien publié » de « publié, mais le mauvais » :
        # c'est la confusion la plus fréquente et la plus décourageante.
        assert "ne porte pas le jeton attendu" in proof.last_error

    def test_aucun_enregistrement_dit_que_la_publication_prend_du_temps(self, actif):
        proof = services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT)

        with patch.object(ownership_checks, "_txt_records", return_value=[]):
            proof = services.verify_ownership_proof(proof)

        assert proof.status == ETAT.FAILED
        assert "quelques minutes" in proof.last_error

    def test_un_dns_injoignable_ne_conclut_pas_a_l_absence_de_preuve(self, actif):
        """« Je n'ai pas pu vérifier » et « la preuve n'est pas là » sont deux
        choses. Les confondre ferait accuser le client d'un incident réseau."""
        proof = services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT)

        with patch.object(
            ownership_checks,
            "_txt_records",
            side_effect=ownership_checks.OwnershipCheckError("Requête DNS TXT impossible"),
        ):
            proof = services.verify_ownership_proof(proof)

        assert proof.status == ETAT.FAILED
        assert "DNS" in proof.last_error


class TestVerificationParFichier:
    def test_le_fichier_contenant_le_jeton_prouve_la_possession(self, actif):
        proof = services.start_ownership_proof(asset=actif, method=METHODE.HTTP_FILE)

        with patch.object(
            ownership_checks, "safe_get", return_value=_reponse(content=proof.token.encode())
        ):
            proof = services.verify_ownership_proof(proof)

        assert proof.status == ETAT.VERIFIED

    def test_un_fichier_absent_est_un_echec_explicite(self, actif):
        proof = services.start_ownership_proof(asset=actif, method=METHODE.HTTP_FILE)

        with patch.object(ownership_checks, "safe_get", return_value=_reponse(status_code=404)):
            proof = services.verify_ownership_proof(proof)

        assert proof.status == ETAT.FAILED
        assert ownership_checks.HTTP_FILE_PATH in proof.last_error

    def test_un_fichier_au_mauvais_contenu_est_refuse(self, actif):
        proof = services.start_ownership_proof(asset=actif, method=METHODE.HTTP_FILE)

        with patch.object(
            ownership_checks, "safe_get", return_value=_reponse(content=b"autre chose")
        ):
            proof = services.verify_ownership_proof(proof)

        assert proof.status == ETAT.FAILED

    def test_un_domaine_pointant_vers_une_adresse_interne_est_refuse(self, actif):
        """Un domaine dont on ne sait pas encore s'il appartient au client est
        exactement la cible qu'il ne faut pas suivre les yeux fermés."""
        proof = services.start_ownership_proof(asset=actif, method=METHODE.HTTP_FILE)

        with patch.object(
            ownership_checks, "safe_get", side_effect=SSRFError("Adresse IP non autorisée")
        ):
            proof = services.verify_ownership_proof(proof)

        assert proof.status == ETAT.FAILED
        assert "toute sécurité" in proof.last_error


class TestVerificationParEmail:
    def test_seules_les_adresses_d_administration_sont_admises(self, actif):
        with pytest.raises(services.OwnershipError) as exc:
            services.start_ownership_proof(
                asset=actif, method=METHODE.EMAIL, email_recipient="moi@example.com"
            )

        assert "admin@example.com" in str(exc.value)

    def test_l_email_part_a_l_adresse_generique_du_domaine(self, actif):
        proof = services.start_ownership_proof(
            asset=actif, method=METHODE.EMAIL, email_recipient="admin"
        )

        assert proof.email_recipient == "admin@example.com"
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["admin@example.com"]

    def test_l_email_dit_au_tiers_comment_refuser(self, actif):
        """C'est le sens même de la méthode : sans porte de sortie, l'email
        n'est qu'une formalité de plus."""
        services.start_ownership_proof(asset=actif, method=METHODE.EMAIL, email_recipient="admin")

        corps = mail.outbox[0].body
        assert "ne transmettez pas ce code" in corps
        assert "rien ne sera activé" in corps

    def test_le_bon_code_prouve_la_possession(self, actif):
        proof = services.start_ownership_proof(
            asset=actif, method=METHODE.EMAIL, email_recipient="postmaster"
        )

        proof = services.verify_ownership_proof(proof, submitted_token=proof.token)

        assert proof.status == ETAT.VERIFIED

    def test_un_mauvais_code_ne_prouve_rien(self, actif):
        proof = services.start_ownership_proof(
            asset=actif, method=METHODE.EMAIL, email_recipient="admin"
        )

        proof = services.verify_ownership_proof(proof, submitted_token="pas-le-bon")

        assert proof.status == ETAT.FAILED
        assert services.is_ownership_proven(actif) is False


class TestJetonsEtRejeu:
    def test_deux_ouvertures_de_la_meme_methode_ne_laissent_qu_un_jeton_valide(self, actif):
        premier = services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT)
        second = services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT)

        assert premier.token != second.token
        restants = services.list_ownership_proofs(actif).filter(method=METHODE.DNS_TXT)
        assert [p.id for p in restants] == [second.id]

    def test_le_jeton_n_est_pas_devinable(self, actif):
        jetons = {
            services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT).token
            for _ in range(5)
        }

        assert len(jetons) == 5
        assert all(len(j) >= 20 for j in jetons)

    def test_une_possession_deja_prouvee_ne_se_rejoue_pas(self, actif):
        proof = services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT)
        with patch.object(ownership_checks, "verify_dns_txt", return_value=(True, "ok")):
            services.verify_ownership_proof(proof)

        with pytest.raises(services.OwnershipError):
            services.start_ownership_proof(asset=actif, method=METHODE.HTTP_FILE)


class TestActifsAnterieursARegulariser:
    """Point 7 : les actifs déjà surveillés sont marqués « à vérifier » sans
    être coupés."""

    def _rendre_anterieur(self, asset):
        """L'état d'un actif déclaré avant la V2-1 : aucune déclaration
        tracée, puisque le modèle n'existait pas."""
        AssetOwnershipAttestation.all_objects.filter(asset=asset).delete()
        return asset

    def test_un_actif_anterieur_est_a_verifier(self, actif):
        self._rendre_anterieur(actif)

        assert services.needs_ownership_review(actif) is True
        assert services.ownership_state(actif) == "to_review"

    def test_un_actif_a_verifier_n_est_pas_coupe(self, actif):
        self._rendre_anterieur(actif)
        actif.refresh_from_db()

        assert actif.is_active is True

    def test_un_actif_declare_apres_la_v2_1_n_est_pas_a_regulariser(self, actif):
        assert services.needs_ownership_review(actif) is False

    def test_la_liste_de_regularisation_ne_retient_que_les_actifs_anterieurs(
        self, actif, tenant, tenant_owner
    ):
        self._rendre_anterieur(actif)
        recent = services.create_asset(
            tenant=tenant,
            user=tenant_owner,
            type=Asset.Type.EMAIL_DOMAIN,
            value="autre.example",
            ownership_confirmed=True,
        )

        a_regulariser = list(services.assets_needing_ownership_review())

        assert [a.id for a in a_regulariser] == [actif.id]
        assert recent.id not in [a.id for a in a_regulariser]

    def test_prouver_la_possession_sort_l_actif_de_la_liste(self, actif):
        self._rendre_anterieur(actif)
        proof = services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT)
        with patch.object(ownership_checks, "verify_dns_txt", return_value=(True, "ok")):
            services.verify_ownership_proof(proof)

        assert list(services.assets_needing_ownership_review()) == []


class TestApiPossession:
    def test_l_ecran_recoit_l_etat_et_les_adresses_admises(
        self, api_client, tenant, tenant_owner, actif
    ):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.get(
            reverse("asset-ownership", args=[actif.id]), format="json", **headers
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["state"] == "declared"
        assert response.data["proven"] is False
        assert "admin@example.com" in response.data["email_choices"]

    def test_ouvrir_une_preuve_renvoie_la_consigne_a_publier(
        self, api_client, tenant, tenant_owner, actif
    ):
        headers = _auth(api_client, tenant_owner, tenant)

        response = api_client.post(
            reverse("asset-ownership", args=[actif.id]),
            {"method": "dns_txt"},
            format="json",
            **headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        instructions = response.data["instructions"]
        assert instructions["record_type"] == "TXT"
        assert instructions["record_value"].startswith("rssi-verification=")

    def test_une_preuve_non_encore_publiee_repond_200_et_non_400(
        self, api_client, tenant, tenant_owner, actif
    ):
        """« Pas encore publié » est une étape normale du parcours. Un 400
        ferait passer pour une faute du client ce qui n'en est pas une, et
        l'écran perdrait le message qui lui dit quoi corriger."""
        headers = _auth(api_client, tenant_owner, tenant)
        proof = services.start_ownership_proof(asset=actif, method=METHODE.DNS_TXT)

        with patch.object(ownership_checks, "_txt_records", return_value=[]):
            response = api_client.post(
                reverse("asset-ownership-verify", args=[actif.id, proof.id]),
                {},
                format="json",
                **headers,
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["verified"] is False
        assert response.data["proof"]["last_error"]

    def test_un_tenant_ne_voit_pas_la_possession_d_un_autre(
        self, api_client, tenant, tenant_owner, actif, user_factory, tenant_factory
    ):
        """Étanchéité : exigée pour toute ressource exposée par l'API."""
        intrus = user_factory(email="intrus@example.com")
        tenant_intrus = tenant_factory(intrus, name="Entreprise Intruse")
        headers = _auth(api_client, intrus, tenant_intrus)

        lecture = api_client.get(
            reverse("asset-ownership", args=[actif.id]), format="json", **headers
        )
        ecriture = api_client.post(
            reverse("asset-ownership", args=[actif.id]),
            {"method": "dns_txt"},
            format="json",
            **headers,
        )

        assert lecture.status_code == status.HTTP_404_NOT_FOUND
        assert ecriture.status_code == status.HTTP_404_NOT_FOUND
        assert AssetOwnershipProof.all_objects.count() == 0
