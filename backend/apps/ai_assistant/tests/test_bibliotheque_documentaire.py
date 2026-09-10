"""La bibliothèque documentaire (V2-5, ADR-032).

Trois familles de tests, et la troisième est celle que la consigne réclame
explicitement : « relis chaque modèle en te demandant s'il est utilisable tel
quel par une PME ». On ne peut pas tester le style d'un document, mais on peut
tester ce qui le rend inutilisable : qu'il ignore les données du client, qu'il
invente ce qu'il ne sait pas, ou qu'il recopie des identifiants qui ne doivent
pas circuler.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.ai_assistant import services
from apps.ai_assistant.documents import registry
from apps.ai_assistant.models import GeneratedDocument

pytestmark = pytest.mark.django_db

TYPES_COMPOSES = [
    spec.type for spec in registry.all_specs() if spec.source == registry.SOURCE_COMPOSED
]


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
def client_equipe(tenant, tenant_owner, referential):
    """Un client comme on en a en vrai : une fiche remplie, un actif déclaré,
    un diagnostic terminé et un plan d'action qui en découle."""
    from apps.actions import services as actions_services
    from apps.assessments import services as assessments_services
    from apps.monitoring import services as monitoring_services
    from apps.monitoring.models import Asset

    tenant.sector = "Menuiserie"
    tenant.headcount = 12
    tenant.contact_email = "direction@menuiserie-test.fr"
    tenant.contact_phone = "01 23 45 67 89"
    tenant.save(update_fields=["sector", "headcount", "contact_email", "contact_phone"])

    monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://menuiserie-test.fr",
        ownership_confirmed=True,
    )

    assessment = assessments_services.start_or_resume_assessment(
        tenant=tenant, user=tenant_owner, referential=referential
    )
    mesures = assessments_services.get_assessment_measures(assessment)
    for position, mesure in enumerate(mesures):
        assessments_services.submit_answer(
            assessment=assessment, measure=mesure, value="yes" if position == 0 else "no"
        )
    assessments_services.complete_assessment(assessment)
    actions_services.generate_action_plan(assessment)
    return tenant


# --- Le catalogue -----------------------------------------------------------


class TestCatalogue:
    def test_annonce_les_sept_documents(self, api_client, tenant, tenant_owner):
        response = api_client.get(
            reverse("ai-document-catalog"), **_auth(api_client, tenant_owner, tenant)
        )

        assert response.status_code == status.HTTP_200_OK
        types = {entree["type"] for entree in response.data}
        assert types == {
            "security_policy",
            "it_charter",
            "incident_procedure",
            "incident_register",
            "continuity_plan",
            "awareness_sheet",
            "committee_report",
        }

    def test_dit_lequel_passe_par_l_ia(self, api_client, tenant, tenant_owner):
        response = api_client.get(
            reverse("ai-document-catalog"), **_auth(api_client, tenant_owner, tenant)
        )

        par_type = {entree["type"]: entree for entree in response.data}
        assert par_type["it_charter"]["source"] == "ai"
        # Six sur sept sont composés : c'est la décision d'ADR-032, et elle
        # doit rester visible.
        assert sum(1 for e in response.data if e["source"] == "composed") == 6

    def test_previent_avant_la_generation_de_ce_qui_manque(self, api_client, tenant, tenant_owner):
        """Un plan de continuité sans actif déclaré n'est pas faux : il est
        vide. Le client doit l'apprendre du bouton, pas du document."""
        response = api_client.get(
            reverse("ai-document-catalog"), **_auth(api_client, tenant_owner, tenant)
        )

        par_type = {entree["type"]: entree for entree in response.data}
        assert par_type["continuity_plan"]["ready"] is False
        assert any("actif" in manque for manque in par_type["continuity_plan"]["missing"])

    def test_ne_signale_plus_rien_quand_le_client_est_equipe(
        self, api_client, client_equipe, tenant_owner
    ):
        response = api_client.get(
            reverse("ai-document-catalog"), **_auth(api_client, tenant_owner, client_equipe)
        )

        assert all(entree["ready"] for entree in response.data)


# --- La composition ---------------------------------------------------------


class TestComposition:
    @pytest.mark.parametrize("document_type", TYPES_COMPOSES)
    def test_chaque_document_compose_se_genere_sans_ia(
        self, client_equipe, tenant_owner, document_type
    ):
        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type=document_type
        )

        assert document.status == GeneratedDocument.Status.DRAFT
        assert document.source == GeneratedDocument.Source.COMPOSED
        assert len(document.content_markdown) > 500

    @pytest.mark.parametrize("document_type", TYPES_COMPOSES)
    def test_chaque_document_nomme_l_entreprise(self, client_equipe, tenant_owner, document_type):
        """Le point 5 de la consigne : le client ne ressaisit pas ce que la
        plateforme sait déjà."""
        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type=document_type
        )
        assert client_equipe.name in document.content_markdown

    @pytest.mark.parametrize("document_type", TYPES_COMPOSES)
    def test_chaque_document_est_reproductible(self, client_equipe, tenant_owner, document_type):
        """Composé, donc déterministe : deux générations sur les mêmes données
        donnent le même texte. C'est ce que l'IA ne peut pas promettre, et
        c'est ce qui permet de défendre un document devant un auditeur."""
        premier = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type=document_type
        )
        second = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type=document_type
        )

        # Seule la version diffère, et elle figure dans l'en-tête.
        assert premier.content_markdown.replace("v1", "vN") == second.content_markdown.replace(
            "v2", "vN"
        )

    def test_les_versions_s_incrementent_par_type(self, client_equipe, tenant_owner):
        services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="incident_register"
        )
        second = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="incident_register"
        )
        autre = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="continuity_plan"
        )

        assert second.version == 2
        # Un type ne pousse pas la version d'un autre.
        assert autre.version == 1

    def test_une_composition_qui_echoue_ne_laisse_pas_un_document_fantome(
        self, client_equipe, tenant_owner, monkeypatch
    ):
        """Le pire état serait « génération en cours » pour toujours."""

        def _casse(*args, **kwargs):
            raise RuntimeError("panne de composition")

        # ``DocumentSpec`` est un dataclass figé : on remplace l'entrée du
        # registre plutôt que d'écrire dans l'instance.
        spec = registry.get("incident_register")
        monkeypatch.setitem(
            registry.REGISTRY,
            "incident_register",
            registry.DocumentSpec(
                type=spec.type,
                label=spec.label,
                purpose=spec.purpose,
                source=spec.source,
                build=_casse,
            ),
        )

        with pytest.raises(RuntimeError):
            services.compose_document(
                tenant=client_equipe, user=tenant_owner, document_type="incident_register"
            )

        document = GeneratedDocument.all_objects.get(tenant=client_equipe)
        assert document.status == GeneratedDocument.Status.FAILED


# --- Utilisable tel quel par une PME ----------------------------------------


class TestUtilisableTelQuel:
    """La vérification demandée par la consigne, traduite en assertions."""

    @pytest.mark.parametrize("document_type", TYPES_COMPOSES)
    def test_ce_qui_n_est_pas_su_est_marque_a_completer_et_non_inventé(
        self, client_equipe, tenant_owner, document_type
    ):
        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type=document_type
        )
        # Chaque document porte au moins une décision qui n'appartient qu'au
        # client (qui valide, qui est référent, quel délai de reprise). Aucun
        # ne doit prétendre la connaître.
        assert "[à compléter]" in document.content_markdown

    @pytest.mark.parametrize("document_type", TYPES_COMPOSES)
    def test_chaque_document_dit_d_ou_il_vient(self, client_equipe, tenant_owner, document_type):
        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type=document_type
        )
        assert "D'où vient ce document" in document.content_markdown

    def test_la_politique_reprend_le_score_et_les_ecarts_reels(
        self, client_equipe, tenant_owner, referential
    ):
        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="security_policy"
        )

        assert referential.name in document.content_markdown
        # Trois des quatre mesures ont été répondues « non » : leurs intitulés
        # doivent apparaître comme ce qui reste à mettre en place.
        from apps.assessments.models import Measure

        en_ecart = Measure.objects.filter(referential=referential, code__in=["2", "3", "4"])
        for mesure in en_ecart:
            assert mesure.official_title in document.content_markdown

    def test_la_politique_couvre_les_dix_domaines_de_l_anssi(self, tenant, tenant_owner):
        """Le texte d'engagement de la politique est choisi par NOM de domaine.

        Si un nom du fichier ANSSI change, ou si les clés du composeur
        dérivent, la politique retombe silencieusement sur une phrase
        générique : le document reste plausible, et il perd exactement ce qui
        en faisait un document d'entreprise. Ce test compare les deux listes
        plutôt que d'espérer.
        """
        from django.core.management import call_command

        from apps.ai_assistant.documents import composers
        from apps.assessments.models import Domain

        call_command("load_anssi_referential")
        noms_anssi = set(
            Domain.objects.filter(referential__slug="anssi-hygiene-informatique").values_list(
                "name", flat=True
            )
        )

        assert noms_anssi == set(composers.POLITIQUE_DOMAINES)

    def test_la_possession_des_actifs_est_ecrite_en_francais(
        self, client_equipe, tenant_owner
    ):
        """« declared » dans un document lu par un dirigeant est un défaut,
        pas un détail — il a été trouvé en relisant la sortie réelle."""
        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="security_policy"
        )

        assert "déclarée sur l'honneur" in document.content_markdown
        assert "declared" not in document.content_markdown
        assert "to_review" not in document.content_markdown

    def test_le_plan_de_continuite_liste_les_actifs_declares(self, client_equipe, tenant_owner):
        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="continuity_plan"
        )
        assert "https://menuiserie-test.fr" in document.content_markdown

    def test_un_document_genere_sans_diagnostic_le_dit_en_tete(self, tenant, tenant_owner):
        """Générique n'est pas interdit — mentir sur le fait qu'il l'est,
        oui. Le lecteur qui reçoit le fichier sans avoir vu l'écran doit
        l'apprendre du document."""
        document = services.compose_document(
            tenant=tenant, user=tenant_owner, document_type="security_policy"
        )
        assert "n'a pas encore été personnalisé" in document.content_markdown

    def test_le_registre_ne_recopie_aucun_identifiant_fuite(self, client_equipe, tenant_owner):
        """Le registre s'imprime, se transmet, finit en pièce jointe. Les
        identifiants restent sur la plateforme."""
        from apps.monitoring.models import Asset
        from apps.threat_intelligence.models import BreachFinding

        asset = Asset.all_objects.filter(tenant=client_equipe).first()
        BreachFinding.all_objects.create(
            tenant=client_equipe,
            asset=asset,
            source_endpoint=BreachFinding.SourceEndpoint.CREDS,
            finding_type="credentials",
            severity=BreachFinding.Severity.HIGH,
            identifier_plain="comptable@menuiserie-test.fr",
            identifier_masked="c*******@menuiserie-test.fr",
            dedup_hash="test-hash-registre",
        )

        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="incident_register"
        )

        assert "comptable@menuiserie-test.fr" not in document.content_markdown
        assert "c*******@menuiserie-test.fr" not in document.content_markdown
        # La ligne existe quand même : c'est un incident à documenter.
        assert "à analyser" in document.content_markdown

    def test_le_registre_rappelle_ce_que_la_plateforme_ne_voit_pas(self, tenant, tenant_owner):
        document = services.compose_document(
            tenant=tenant, user=tenant_owner, document_type="incident_register"
        )
        assert "ne voit ni vos postes de travail" in document.content_markdown

    def test_la_fiche_de_sensibilisation_tient_sur_une_page(self, client_equipe, tenant_owner):
        """Une fiche de sensibilisation de six pages n'est pas lue. On borne
        grossièrement, mais on borne."""
        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="awareness_sheet"
        )
        mots = len(document.content_markdown.split())
        assert mots < 1200, f"{mots} mots : trop long pour une fiche d'une page"


# --- API, gardes et exports -------------------------------------------------


class TestApi:
    def test_composer_repond_tout_de_suite_sans_job(self, api_client, client_equipe, tenant_owner):
        response = api_client.post(
            reverse("ai-document-list"),
            {"type": "incident_procedure"},
            format="json",
            **_auth(api_client, tenant_owner, client_equipe),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["job"] is None
        assert response.data["document"]["status"] == "draft"
        assert response.data["document"]["content_markdown"]

    def test_la_charte_passe_toujours_par_un_job(self, api_client, client_equipe, tenant_owner):
        from unittest.mock import patch

        with patch("apps.ai_assistant.views.generate_document_task.delay") as delay:
            response = api_client.post(
                reverse("ai-document-list"),
                {"type": "it_charter"},
                format="json",
                **_auth(api_client, tenant_owner, client_equipe),
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["job"] is not None
        delay.assert_called_once()

    def test_couper_l_ia_ne_retire_que_la_charte(self, api_client, client_equipe, tenant_owner):
        """L'interrupteur d'IA (US-4.3) désactive ce qui appelle l'IA. Il ne
        reprend pas au client les documents qu'aucune IA ne rédige."""
        client_equipe.ai_enabled = False
        client_equipe.save(update_fields=["ai_enabled"])
        headers = _auth(api_client, tenant_owner, client_equipe)

        compose = api_client.post(
            reverse("ai-document-list"), {"type": "continuity_plan"}, format="json", **headers
        )
        charte = api_client.post(
            reverse("ai-document-list"), {"type": "it_charter"}, format="json", **headers
        )

        assert compose.status_code == status.HTTP_201_CREATED
        assert charte.status_code == status.HTTP_403_FORBIDDEN

    def test_couper_l_ia_laisse_lire_et_exporter(self, api_client, client_equipe, tenant_owner):
        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="incident_register"
        )
        client_equipe.ai_enabled = False
        client_equipe.save(update_fields=["ai_enabled"])
        headers = _auth(api_client, tenant_owner, client_equipe)

        liste = api_client.get(reverse("ai-document-list"), **headers)
        export = api_client.get(reverse("ai-document-export", args=[document.id]), **headers)

        assert liste.status_code == status.HTTP_200_OK
        assert export.status_code == status.HTTP_200_OK

    def test_la_garde_d_offre_porte_sur_le_type_et_non_sur_la_vue(
        self, api_client, client_equipe, tenant_owner
    ):
        """Sans cela, retirer « génération de charte » d'une offre retirerait
        aussi le registre des incidents, qui n'a rien à voir."""
        from apps.billing import entitlements

        abonnement = entitlements.get_subscription(client_equipe)
        abonnement.override_features = [
            cle for cle in abonnement.effective_features if cle != "charter_generation"
        ]
        abonnement.save(update_fields=["override_features"])
        headers = _auth(api_client, tenant_owner, client_equipe)

        charte = api_client.post(
            reverse("ai-document-list"), {"type": "it_charter"}, format="json", **headers
        )
        registre = api_client.post(
            reverse("ai-document-list"), {"type": "incident_register"}, format="json", **headers
        )

        assert charte.status_code == status.HTTP_402_PAYMENT_REQUIRED
        assert registre.status_code == status.HTTP_201_CREATED

    def test_le_lecteur_ne_genere_pas(self, api_client, client_equipe, user_factory):
        from apps.tenants.models import Membership

        lecteur = user_factory(email="lecteur-docs@example.com")
        Membership.all_objects.create(
            tenant=client_equipe, user=lecteur, role=Membership.Role.READER
        )

        response = api_client.post(
            reverse("ai-document-list"),
            {"type": "incident_register"},
            format="json",
            **_auth(api_client, lecteur, client_equipe),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestExportEditable:
    def test_produit_un_fichier_word(self, api_client, client_equipe, tenant_owner):
        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="incident_procedure"
        )

        response = api_client.get(
            reverse("ai-document-export-docx", args=[document.id]),
            **_auth(api_client, tenant_owner, client_equipe),
        )

        assert response.status_code == status.HTTP_200_OK
        # Un .docx est une archive ZIP : les deux premiers octets le disent.
        assert response.content[:2] == b"PK"
        assert "attachment" in response["Content-Disposition"]
        assert ".docx" in response["Content-Disposition"]

    def test_le_document_word_contient_le_texte_et_les_tableaux(self, client_equipe, tenant_owner):
        import io

        from docx import Document as DocxDocument

        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="continuity_plan"
        )
        rendu = DocxDocument(io.BytesIO(services.render_document_docx(document)))

        texte = "\n".join(p.text for p in rendu.paragraphs)
        assert "Plan de continuité" in texte
        # Les tableaux à remplir sont l'essentiel de ce document : s'ils
        # arrivaient en texte brut avec des barres verticales, il serait
        # inutilisable dans Word.
        assert len(rendu.tables) >= 3

    def test_un_document_vide_produit_quand_meme_un_fichier(self, client_equipe, tenant_owner):
        document = GeneratedDocument.all_objects.create(
            tenant=client_equipe,
            type="incident_register",
            source=GeneratedDocument.Source.COMPOSED,
            content_markdown="",
        )
        assert services.render_document_docx(document)[:2] == b"PK"


class TestEtancheite:
    def test_un_client_ne_voit_pas_les_documents_du_voisin(
        self, api_client, client_equipe, tenant_owner, tenant_factory, user_factory
    ):
        services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="incident_register"
        )
        voisin_owner = user_factory(email="voisin-docs@example.com")
        voisin = tenant_factory(voisin_owner, name="Voisin")

        response = api_client.get(
            reverse("ai-document-list"), **_auth(api_client, voisin_owner, voisin)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []

    def test_un_document_compose_ne_contient_que_les_donnees_de_son_client(
        self, client_equipe, tenant_owner, tenant_factory, user_factory
    ):
        from apps.monitoring import services as monitoring_services
        from apps.monitoring.models import Asset

        voisin_owner = user_factory(email="voisin2@example.com")
        voisin = tenant_factory(voisin_owner, name="Entreprise Voisine")
        monitoring_services.create_asset(
            tenant=voisin,
            user=voisin_owner,
            type=Asset.Type.WEBSITE,
            value="https://voisin-secret.fr",
            ownership_confirmed=True,
        )

        document = services.compose_document(
            tenant=client_equipe, user=tenant_owner, document_type="continuity_plan"
        )

        assert "voisin-secret.fr" not in document.content_markdown
        assert "Entreprise Voisine" not in document.content_markdown
