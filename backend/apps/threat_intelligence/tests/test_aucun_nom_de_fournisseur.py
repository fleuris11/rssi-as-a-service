"""RÈGLE ABSOLUE : le nom de la source de renseignement ne sort jamais.

Ni à l'écran, ni dans un message d'erreur, ni dans un export, ni dans un
email. Ce n'est pas une pudeur, c'est un actif commercial : un client qui
connaît la source peut aller voir son tarif public, et le rapport entre ce
qu'il paie et ce que coûte la donnée devient une conversation qu'on n'a pas
choisi d'avoir.

Un balayage existait déjà, mais **seulement sur les constantes de message
d'erreur** (``test_client_facing_messages.py``). Il ne voyait rien de ce qui
part par le chemin normal : la liste des fuites, le fil d'exposition, le
détail d'une compromission, les textes de vulgarisation, les libellés des
champs restitués. C'est là que la surface est la plus grande, et c'est là
qu'elle n'était pas gardée.

Ce module balaie donc **la charge réellement servie**, en parcourant
récursivement chaque chaîne des réponses d'API — pas une relecture à l'œil
des fichiers source.
"""

import json
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.threat_intelligence import (
    client_messages,
    correlation,
    finding_details,
    plain_language,
    services,
)
from apps.threat_intelligence.providers.base import RawFinding

pytestmark = pytest.mark.django_db

NOMS = client_messages.VENDOR_NAMES


def _chaines(valeur, chemin="racine"):
    """Toutes les chaînes d'une structure imbriquée, avec leur chemin.

    Le chemin est ce qui rend un échec exploitable : « racine.assets[0]
    .findings[2].details[1].implication » désigne la ligne à corriger, là où
    un simple « le mot apparaît quelque part » enverrait chercher.
    """
    if isinstance(valeur, str):
        yield chemin, valeur
    elif isinstance(valeur, dict):
        for cle, sous in valeur.items():
            yield from _chaines(sous, f"{chemin}.{cle}")
    elif isinstance(valeur, (list, tuple)):
        for i, sous in enumerate(valeur):
            yield from _chaines(sous, f"{chemin}[{i}]")


def _verifier(charge, origine):
    trouves = []
    for chemin, texte in _chaines(charge, origine):
        bas = texte.lower()
        for nom in NOMS:
            if nom in bas:
                trouves.append(f"« {nom} » dans {chemin} :\n    {texte[:200]}")
    assert not trouves, (
        "Le nom de la source de renseignement est servi au client :\n"
        + "\n".join(trouves)
        + "\n\nIl ne doit apparaître nulle part côté client (ADR-027)."
    )


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


#: Une charge par point d'entrée, avec des champs renseignés partout : le
#: balayage ne vaut que si les textes qu'il inspecte existent réellement.
CHARGES = {
    "stealer": {
        "usr": "marie@exemple.fr",
        "pwd": "MotDePasse2024!",
        "src": "secure.atmel.com",
        "os": "Windows 10 Home",
        "mal": "Raccoon",
        "fle": "collecte_2026.txt",
        "hid": "MACHINE-4711",
        "inf": "2026-08-01",
        "fnd": "2026-09-04",
    },
    "combo": {"usr": "paul@exemple.fr", "pwd": "x", "src": "liste", "cnt": 4, "fnd": "2026-06-07"},
    "creds": {"eml": "sophie@exemple.fr", "pwd": "y", "src": "plateforme", "hash": 1},
    "sessions": {
        "user_name": "marie",
        "val": "cookie",
        "dom": "outil.exemple.fr",
        "cookie_name": "session_id",
        "expires": "2026-12-01",
        "mal": "RedLine",
        "fnd": "2026-08-02",
    },
    "nhi": {
        "usr": "svc-compta",
        "token": "sk-live-x",
        "platform": "Stripe",
        "category": "service-account",
        "source_type": "dépôt de code public",
        "prefix": "sk-live",
        "fnd": "2026-07-01",
    },
    "darkweb": {
        "data": "exemple.fr",
        "name": "Exemple SARL",
        "site": "forum",
        "desc": "mention",
        "tadesc": "groupe",
        "found": "2026-05-01",
    },
    "radar": {"data": "exemple.fr", "src": "forum public", "found": "2026-05-02"},
    "docs": {
        "doc_id": "d-1",
        "file_name": "clients-2026.xlsx",
        "file_hash": "abc",
        "file_size": 2411724,
        "content_type": "text/csv",
        "leak_date": "2026-08-20",
        "extraction_timestamp": "2026-08-21",
        "threat_actor": "groupe",
        "company_name": "Exemple SARL",
        "domain_name": "exemple.fr",
        "url_main_post": "https://fuite.example/post/1",
        "url_for_breach": "https://fuite.example/dl/1",
    },
    "asm": {
        "dom": "exemple.co",
        "type": "pphish",
        "cname": "ailleurs.example",
        "ip": "203.0.113.1",
    },
}


@pytest.fixture
def toutes_les_fuites(tenant, website_asset):
    creees = []
    for endpoint, charge in CHARGES.items():
        creees += services.ingest_raw_findings(
            tenant=tenant,
            asset=website_asset,
            raw_findings=[RawFinding(endpoint=endpoint, payload=charge)],
        )
    assert len(creees) == len(CHARGES)
    return creees


class TestTexteEditorial:
    """Les textes écrits à la main — c'est là qu'un nom se glisse le plus
    facilement, parce qu'on les rédige sans y penser."""

    def test_la_vulgarisation_ne_nomme_jamais_la_source(self):
        _verifier(plain_language.all_explanations(), "plain_language")
        _verifier(
            {str(k): v for k, v in plain_language.all_subtype_explanations().items()},
            "plain_language.sous_types",
        )

    def test_les_libelles_de_champs_ne_nomment_jamais_la_source(self):
        champs = {
            endpoint: [
                {"label": c.label, "implication": c.implication_pour("Raccoon")} for c in liste
            ]
            for endpoint, liste in finding_details.all_detail_fields().items()
        }
        _verifier(champs, "finding_details")

    def test_le_glossaire_des_logiciels_ne_nomme_jamais_la_source(self):
        _verifier(finding_details.GLOSSAIRE_MALVEILLANTS, "glossaire")
        _verifier(finding_details.IMPLICATION_MALVEILLANT_INCONNUE, "glossaire.repli")

    def test_les_signaux_de_correlation_ne_nomment_jamais_la_source(self):
        _verifier(correlation.SIGNAL_DEFINITIONS, "correlation")

    def test_les_messages_client_ne_nomment_jamais_la_source(self):
        constantes = {
            nom: valeur
            for nom, valeur in vars(client_messages).items()
            if nom.isupper() and isinstance(valeur, str)
        }
        _verifier(constantes, "client_messages")


class TestChargesServies:
    """Le balayage qui compte : ce que l'API renvoie réellement."""

    def test_la_liste_des_fuites(self, api_client, tenant, tenant_owner, toutes_les_fuites):
        entetes = _auth(api_client, tenant_owner, tenant)
        reponse = api_client.get(reverse("breach-finding-list"), **entetes)
        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["results"], "la liste doit contenir des fuites, sinon rien n'est balayé"
        _verifier(json.loads(json.dumps(reponse.data, default=str)), "liste")

    def test_le_detail_de_chaque_fuite(self, api_client, tenant, tenant_owner, toutes_les_fuites):
        entetes = _auth(api_client, tenant_owner, tenant)
        for fuite in toutes_les_fuites:
            reponse = api_client.get(reverse("breach-finding-detail", args=[fuite.id]), **entetes)
            assert reponse.status_code == status.HTTP_200_OK
            _verifier(
                json.loads(json.dumps(reponse.data, default=str)),
                f"detail[{fuite.source_endpoint}]",
            )

    def test_le_fil_d_exposition(self, api_client, tenant, tenant_owner, toutes_les_fuites):
        entetes = _auth(api_client, tenant_owner, tenant)
        reponse = api_client.get(reverse("breach-exposure-feed"), **entetes)
        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.data["assets"], "le fil doit contenir un actif, sinon rien n'est balayé"
        _verifier(json.loads(json.dumps(reponse.data, default=str)), "fil")

    def test_le_radar_pre_incident(self, api_client, tenant, tenant_owner, toutes_les_fuites):
        entetes = _auth(api_client, tenant_owner, tenant)
        reponse = api_client.get(reverse("breach-pre-incident"), **entetes)
        assert reponse.status_code == status.HTTP_200_OK
        _verifier(json.loads(json.dumps(reponse.data, default=str)), "radar")

    def test_l_etat_du_service(self, api_client, tenant, tenant_owner):
        entetes = _auth(api_client, tenant_owner, tenant)
        reponse = api_client.get(reverse("threat-intelligence-status"), **entetes)
        assert reponse.status_code == status.HTTP_200_OK
        _verifier(json.loads(json.dumps(reponse.data, default=str)), "statut")


class TestEmails:
    """Un email part sans que personne ne le relise. C'est le canal le plus
    facile à oublier, et le seul qui sorte du produit."""

    def test_la_meteo_quotidienne_ne_nomme_jamais_la_source(
        self, tenant, tenant_owner, website_asset, toutes_les_fuites
    ):
        from django.core import mail

        from apps.notifications import services as notifications_services

        notifications_services.send_weather_email(tenant)

        assert mail.outbox, "aucun email envoyé — le test ne balaierait rien"
        for message in mail.outbox:
            _verifier(message.subject, "meteo.sujet")
            _verifier(message.body, "meteo.corps")
            for contenu, _type in getattr(message, "alternatives", []):
                _verifier(contenu, "meteo.html")


class TestLeBalayageEchoueQuandIlLeDoit:
    """Une garde qu'on n'a pas vue échouer ne prouve rien."""

    def test_un_nom_de_fournisseur_est_bien_detecte(self):
        with pytest.raises(AssertionError) as exc:
            _verifier({"texte": "Breachsense a répondu 400"}, "essai")
        assert "breachsense" in str(exc.value)

    def test_le_chemin_de_la_chaine_fautive_est_donne(self):
        with pytest.raises(AssertionError) as exc:
            _verifier({"a": [{"b": "propulsé par Anthropic"}]}, "essai")
        assert "essai.a[0].b" in str(exc.value)

    def test_la_detection_ignore_la_casse(self):
        with pytest.raises(AssertionError):
            _verifier("BREACHSENSE", "essai")


class TestAucuneUrlDeDocument:
    """ADR-027 partie C : jamais de lien vers un document volé.

    Rediriger un client vers un fichier volé engagerait sa responsabilité
    autant que la nôtre. La garde est structurelle — les champs d'URL ne
    figurent dans aucune liste blanche — et vérifiée ici sur la charge servie.
    """

    def test_les_champs_d_url_ne_sont_dans_aucune_liste_blanche(self):
        for endpoint, champs in finding_details.all_detail_fields().items():
            cles = {c.key for c in champs}
            for interdit in finding_details.CHAMPS_INTERDITS:
                assert interdit not in cles, (
                    f"Le champ « {interdit} » a été ajouté à la liste blanche de "
                    f"« {endpoint} ». Il ne doit jamais être restitué au client."
                )

    def test_aucune_url_de_fuite_dans_le_detail_d_un_document(
        self, api_client, tenant, tenant_owner, toutes_les_fuites
    ):
        entetes = _auth(api_client, tenant_owner, tenant)
        document = next(f for f in toutes_les_fuites if f.source_endpoint == "docs")
        # Prérequis : la charge d'origine contient bien des URL, sinon le test
        # ne prouve rien — il vérifierait l'absence de ce qui n'a jamais été là.
        assert "url_main_post" in document.raw_data

        reponse = api_client.get(reverse("breach-finding-detail", args=[document.id]), **entetes)

        charge = json.dumps(reponse.data, default=str)
        assert "fuite.example" not in charge
        assert "url_main_post" not in charge
        assert "url_for_breach" not in charge

    def test_le_document_dit_quoi_faire_plutot_que_d_offrir_un_lien(
        self, api_client, tenant, tenant_owner, toutes_les_fuites
    ):
        entetes = _auth(api_client, tenant_owner, tenant)
        document = next(f for f in toutes_les_fuites if f.source_endpoint == "docs")

        reponse = api_client.get(reverse("breach-finding-detail", args=[document.id]), **entetes)

        action = reponse.data["recommended_action"]
        assert "72" in action  # le délai de notification, l'information la plus actionnable
        assert "télécharger" in action.lower()  # et l'interdiction, dite explicitement
        # Les métadonnées, elles, sont bien là.
        details = {d["label"]: d["value"] for d in reponse.data["details"]}
        assert "Nom du document" in details
        assert "Taille" in details
        # Le type MIME est un nom technique : il est traduit, jamais servi tel
        # quel. Et la taille en octets ne dit rien — « 2,3 Mo » si.
        assert details["Type de document"] == "Fichier de données (CSV)", (
            "Le type MIME doit être traduit, jamais servi tel quel : "
            f"{details['Type de document']!r}"
        )
        assert details["Taille"] == "2,3 Mo"


class TestAucunNomTechniqueBrut:
    """Point 2 de la consigne : jamais les noms techniques bruts à l'écran."""

    def test_chaque_libelle_est_en_francais_et_non_le_nom_du_champ(self):
        for endpoint, champs in finding_details.all_detail_fields().items():
            for champ in champs:
                assert champ.label != champ.key, (
                    f"« {endpoint}.{champ.key} » est affiché sous son nom technique."
                )
                assert champ.label[0].isupper(), (
                    f"« {endpoint}.{champ.key} » : le libellé doit être une phrase, "
                    f"pas un identifiant ({champ.label!r})."
                )

    def test_chaque_champ_dit_ce_qu_il_implique(self):
        for endpoint, champs in finding_details.all_detail_fields().items():
            for champ in champs:
                implication = champ.implication_pour("Raccoon")
                assert len(implication) > 40, (
                    f"« {endpoint}.{champ.key} » n'explique pas ce que la valeur implique : "
                    f"{implication!r}"
                )


class TestCouvertureEditoriale:
    """Partie D : tous les types de fuite, la même exigence."""

    def test_chaque_type_de_fuite_dit_ce_que_c_est_ce_que_ca_implique_et_quoi_faire(self):
        for cle, entree in plain_language.all_explanations().items():
            for attendue in plain_language.REQUIRED_KEYS:
                assert entree.get(attendue), f"« {cle} » n'a pas de « {attendue} »."
                assert len(entree[attendue]) > 60, (
                    f"« {cle}.{attendue} » est trop court pour dire quelque chose : "
                    f"{entree[attendue]!r}"
                )

    def test_les_sous_types_tiennent_la_meme_exigence(self):
        for cle, entree in plain_language.all_subtype_explanations().items():
            for attendue in plain_language.REQUIRED_KEYS:
                assert entree.get(attendue), f"« {cle} » n'a pas de « {attendue} »."

    def test_chaque_point_d_entree_a_ses_champs_restitues(self):
        """Un endpoint sans champ restitué retomberait sur un écran vide —
        exactement l'état que la V2-2 corrige."""
        sans_details = [
            endpoint
            for endpoint in CHARGES
            if not finding_details.all_detail_fields().get(endpoint)
        ]
        assert sans_details == [], f"Points d'entrée sans restitution : {sans_details}"


class TestNonRegressionSurLesErreurs:
    """Le balayage d'origine reste : un chemin d'échec ne doit pas rouvrir la
    porte que le chemin normal vient de fermer."""

    def test_l_echec_d_analyse_ne_nomme_pas_la_source(self, tenant, website_asset):
        from apps.threat_intelligence import tasks
        from apps.threat_intelligence.models import BreachScanJob
        from apps.threat_intelligence.providers.breachsense.client import (
            BreachsenseBadRequestError,
        )

        job = BreachScanJob.all_objects.create(
            tenant=tenant, triggered_by=services.TriggeredBy.MANUAL
        )
        erreur = BreachsenseBadRequestError("Breachsense a répondu 400 : missing parameters")
        with patch.object(services, "execute_scan", side_effect=erreur):
            tasks.run_breach_scan_task.apply(
                kwargs={
                    "tenant_id": str(tenant.id),
                    "triggered_by": services.TriggeredBy.MANUAL,
                    "job_id": job.id,
                }
            )

        job.refresh_from_db()
        _verifier(job.error_message, "job.error_message")
