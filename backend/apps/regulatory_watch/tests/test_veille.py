"""Veille réglementaire (V2-7, ADR-034).

La famille de tests qui compte le plus est ``TestAucuneModificationAutomatique``.
La consigne le demande explicitement : *vérifier qu'aucune suggestion ne peut
modifier un référentiel sans validation explicite*. Ces tests attaquent la
règle par les trois chemins par lesquels elle pourrait céder — la collecte, le
tri, et l'intégration elle-même.

Les flux de test reproduisent les particularités des VRAIS flux, pas des flux
idéaux : marque d'ordre des octets et encodage HTTP menteur pour l'Atom du
NIST, entités doublement échappées pour le RSS de la CNIL. Les deux ont cassé
le parseur au premier essai contre le réseau.
"""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.assessments.models import Measure
from apps.platform_admin.models import PlatformAdminProfile
from apps.regulatory_watch import feeds, services, sources
from apps.regulatory_watch.models import WatchSource, WatchUpdate

pytestmark = pytest.mark.django_db


RSS = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
  <title>Actualites</title>
  <item>
    <title>Recommandations de securite pour un systeme d'IA generative</title>
    <guid>publication-4242</guid>
    <link>https://exemple-autorite.test/publications/ia-generative</link>
    <pubDate>Wed, 09 Sep 2026 14:00:00 +0200</pubDate>
    <description>&amp;amp;nbsp;Un guide en
      &amp;lt;b&amp;gt;dix mesures&amp;lt;/b&amp;gt;.</description>
  </item>
  <item>
    <title>Deliberation sur les violations de donnees</title>
    <guid>publication-4243</guid>
    <link>https://exemple-autorite.test/publications/violations</link>
    <pubDate>Mon, 07 Sep 2026 09:00:00 +0200</pubDate>
    <description>Ce que le registre doit contenir.</description>
  </item>
</channel></rss>"""

# BOM en tete, comme le flux reel du NIST.
ATOM = (
    b"\xef\xbb\xbf"
    b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Draft Publications</title>
  <entry>
    <id>https://exemple-normalisation.test/pubs/sp/800/53/r6</id>
    <title>SP 800-53 Rev. 6 (Initial Public Draft)</title>
    <link rel="alternate" href="https://exemple-normalisation.test/pubs/sp/800/53/r6"/>
    <published>2026-09-03T00:00:00-04:00</published>
    <summary>Proposed updates to the security and privacy controls.</summary>
  </entry>
</feed>"""
)


class _Reponse:
    """Le minimum de ``requests.Response`` dont ``poll_source`` a besoin.

    ``encoding`` vaut ISO-8859-1 par defaut, comme le devine ``requests``
    quand l'en-tete HTTP ne declare pas de charset — c'est exactement ce qui
    a casse le parseur sur le flux du NIST.
    """

    def __init__(self, content=b"", status_code=200, encoding="ISO-8859-1"):
        self.content = content
        self.status_code = status_code
        self.encoding = encoding

    @property
    def text(self):
        return self.content.decode(self.encoding, errors="replace")


def _login(api_client, email, password="Str0ng!Passw0rd123"):
    response = api_client.post(
        reverse("token-obtain-pair"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    return response.data["access"]


def _auth(api_client, user):
    return {"HTTP_AUTHORIZATION": f"Bearer {_login(api_client, user.email)}"}


@pytest.fixture
def exploitant(user_factory):
    user = user_factory(email="veille@example.com", is_staff=True)
    PlatformAdminProfile.objects.create(user=user, level=PlatformAdminProfile.Level.FULL)
    return user


@pytest.fixture
def source_rss(db):
    return WatchSource.objects.create(
        slug="autorite-test",
        name="Publications",
        publisher="Autorité de test",
        url="https://exemple-autorite.test/publications",
        feed_url="https://exemple-autorite.test/rss.xml",
        format=WatchSource.Format.RSS,
    )


@pytest.fixture
def source_page(db):
    return WatchSource.objects.create(
        slug="page-sans-flux",
        name="Guides et recommandations",
        publisher="Agence de test",
        url="https://exemple-agence.test/guides",
        format=WatchSource.Format.PAGE,
    )


@pytest.fixture
def suggestion(source_rss):
    with patch("apps.regulatory_watch.services.safe_get", return_value=_Reponse(RSS)):
        services.poll_source(source_rss)
    return WatchUpdate.objects.get(external_id="publication-4242")


# --- Le cadrage : les sources -----------------------------------------------


class TestSources:
    def test_la_liste_de_depart_est_installee(self):
        """Les sources vivent en base pour être corrigées sans redéploiement,
        mais le point de départ est posé par une migration."""
        installees = {source.slug for source in services.list_sources()}
        assert {spec["slug"] for spec in sources.SOURCES} <= installees

    def test_chaque_source_declare_son_format_et_sa_fiabilite(self):
        for source in services.list_sources():
            assert source.publisher, f"{source.slug} sans éditeur"
            assert source.url, f"{source.slug} sans adresse lisible"
            assert source.scope_note, f"{source.slug} sans note de périmètre"
            if source.format != WatchSource.Format.PAGE:
                # Une source à flux peut être livrée sans adresse (EUR-Lex,
                # à configurer), mais alors elle est inactive : on ne laisse
                # pas une source active promettre une collecte impossible.
                assert source.feed_url or not source.is_active, source.slug

    def test_une_source_a_configurer_est_signalee_comme_telle(self):
        """Et non comme une panne : elle n'a jamais été branchée."""
        sante = services.sources_health()
        a_configurer = {ligne["slug"] for ligne in sante["unconfigured"]}

        assert "eurlex-cyber" in a_configurer
        assert all(ligne["slug"] not in a_configurer for ligne in sante["failing"])

    def test_la_promesse_ne_survend_pas(self):
        """Consigne V2-7 §8 : ni « exhaustive », ni « temps réel ». Le test
        épingle les deux mots qu'on ne tiendrait pas."""
        promesse = sources.PROMESSE.lower()

        assert "exhaustive" not in promesse or "n'est ni exhaustive" in promesse
        assert "temps réel" not in promesse
        assert "publications officielles" in promesse

    def test_les_exclusions_sont_documentees(self):
        """Une liste de sources sans ses exclusions se relit mal : on ne sait
        pas si un manque est un oubli ou une décision."""
        motifs = dict(sources.EXCLUES)

        assert any("CERT-FR" in nom for nom in motifs)
        assert any("Blogs" in nom for nom in motifs)
        for motif in motifs.values():
            assert len(motif) > 80, "une exclusion sans motif lisible"


# --- La collecte ------------------------------------------------------------


class TestCollecte:
    def test_lit_un_flux_rss_et_cree_une_suggestion_par_publication(self, source_rss):
        with patch("apps.regulatory_watch.services.safe_get", return_value=_Reponse(RSS)):
            rapport = services.poll_source(source_rss)

        assert rapport["created"] == 2
        suggestion = WatchUpdate.objects.get(external_id="publication-4242")
        assert suggestion.status == WatchUpdate.Status.NEW
        assert suggestion.url == "https://exemple-autorite.test/publications/ia-generative"
        assert suggestion.published_at.year == 2026

    def test_lit_un_flux_atom_malgre_le_bom_et_un_encodage_menteur(self, source_rss):
        """Défaut trouvé contre le vrai flux du NIST : marque d'ordre des
        octets en tête, et en-tête HTTP annonçant ISO-8859-1 pour un document
        UTF-8. Le texte décodé par ``requests`` ne se parsait plus."""
        source_rss.format = WatchSource.Format.ATOM
        source_rss.save(update_fields=["format"])

        with patch("apps.regulatory_watch.services.safe_get", return_value=_Reponse(ATOM)):
            rapport = services.poll_source(source_rss)

        assert rapport["created"] == 1
        assert WatchUpdate.objects.get().title.startswith("SP 800-53")

    def test_conserve_le_texte_source_lisible(self, suggestion):
        """Le texte source est la RÉFÉRENCE (consigne V2-7 §7). Les entités
        doublement échappées du flux de la CNIL laissaient « &nbsp; » en clair
        dans l'extrait conservé."""
        assert "&nbsp;" not in suggestion.source_excerpt
        assert "&lt;" not in suggestion.source_excerpt
        assert "dix mesures" in suggestion.source_excerpt

    def test_un_second_passage_ne_recree_rien(self, source_rss):
        with patch("apps.regulatory_watch.services.safe_get", return_value=_Reponse(RSS)):
            services.poll_source(source_rss)
            rapport = services.poll_source(source_rss)

        assert rapport["created"] == 0
        assert WatchUpdate.objects.count() == 2

    def test_une_publication_ecartee_ne_revient_pas_dans_la_file(
        self, source_rss, suggestion, exploitant
    ):
        """Le fournisseur republie son flux entier à chaque fois. Une
        suggestion déjà triée ne doit pas redevenir « à examiner »."""
        services.review_update(suggestion, status=WatchUpdate.Status.DISMISSED, reviewer=exploitant)

        with patch("apps.regulatory_watch.services.safe_get", return_value=_Reponse(RSS)):
            services.poll_source(source_rss)

        suggestion.refresh_from_db()
        assert suggestion.status == WatchUpdate.Status.DISMISSED

    def test_une_page_sans_flux_ne_signale_rien_au_premier_passage(self, source_page):
        """Signaler « cette page a changé » alors qu'on ne l'a jamais lue
        serait faux, et remplirait la file au déploiement."""
        with patch(
            "apps.regulatory_watch.services.safe_get",
            return_value=_Reponse(b"<html><body>Guide A</body></html>"),
        ):
            rapport = services.poll_source(source_page)

        assert rapport["created"] == 0
        source_page.refresh_from_db()
        assert source_page.content_fingerprint

    def test_une_page_qui_change_produit_une_suggestion_honnete(self, source_page):
        """On sait QUE la page a changé, pas QUOI : la file le dit tel quel."""
        with patch(
            "apps.regulatory_watch.services.safe_get",
            return_value=_Reponse(b"<html><body>Guide A</body></html>"),
        ):
            services.poll_source(source_page)
        with patch(
            "apps.regulatory_watch.services.safe_get",
            return_value=_Reponse(b"<html><body>Guide A, Guide B</body></html>"),
        ):
            rapport = services.poll_source(source_page)

        assert rapport["created"] == 1
        assert "Mise à jour de la page" in WatchUpdate.objects.get().title

    def test_une_page_inchangee_ne_signale_rien(self, source_page):
        """Un identifiant de session ou un espace en trop ne doit pas faire
        « changer » la page à chaque passage."""
        with patch(
            "apps.regulatory_watch.services.safe_get",
            return_value=_Reponse(b"<html><body>Guide A</body></html>"),
        ):
            services.poll_source(source_page)
        with patch(
            "apps.regulatory_watch.services.safe_get",
            return_value=_Reponse(b"<html>  <body>Guide   A</body>  </html>"),
        ):
            rapport = services.poll_source(source_page)

        assert rapport["created"] == 0

    def test_une_source_en_echec_est_comptee_et_signalee(self, source_rss):
        with patch(
            "apps.regulatory_watch.services.safe_get", return_value=_Reponse(b"", status_code=503)
        ):
            for _ in range(services.FAILURE_THRESHOLD):
                with pytest.raises(services.WatchError):
                    services.poll_source(source_rss)

        source_rss.refresh_from_db()
        assert source_rss.consecutive_failures == services.FAILURE_THRESHOLD
        assert "503" in source_rss.last_error
        # Une source qui échoue en silence est pire qu'une source absente.
        assert any(
            ligne["slug"] == source_rss.slug for ligne in services.sources_health()["failing"]
        )

    def test_une_source_en_echec_ne_fait_pas_tomber_les_autres(self, source_rss, source_page):
        """Même règle que les analyses d'actifs, apprise le 06/09/2026."""

        def _reponse(url, **kwargs):
            if url == source_rss.feed_url:
                raise services.CheckNetworkError("délai dépassé")
            return _Reponse(b"<html><body>Guide A</body></html>")

        with patch("apps.regulatory_watch.services.safe_get", side_effect=_reponse):
            rapport = services.poll_all_sources()

        # La source en echec est signalee, et celle qui va bien a bien ete
        # relevee. On n'epingle pas le TOTAL : les sources de depart
        # installees par la migration sont elles aussi dans le lot, et lier ce
        # test a leur nombre le ferait rougir au prochain ajout de source.
        assert source_rss.slug in rapport["failed"]
        assert source_page.slug not in rapport["failed"]
        source_page.refresh_from_db()
        assert source_page.content_fingerprint

    def test_la_collecte_passe_par_la_garde_ssrf(self, source_rss):
        """Les adresses de sources sont saisies en base : sans garde, elles
        permettraient d'atteindre un service interne depuis notre serveur."""
        with patch("apps.regulatory_watch.services.safe_get") as fetch:
            fetch.return_value = _Reponse(RSS)
            services.poll_source(source_rss)

        # `safe_get` valide le SSRF à chaque saut de redirection : le test
        # vérifie qu'on passe bien par lui, et non par `requests.get`.
        fetch.assert_called_once()
        assert fetch.call_args.args[0] == source_rss.feed_url

    def test_la_tache_est_idempotente(self, source_rss):
        from apps.regulatory_watch.tasks import poll_sources_task

        with patch("apps.regulatory_watch.services.safe_get", return_value=_Reponse(RSS)):
            premier = poll_sources_task()
            second = poll_sources_task()

        assert premier["created"] >= 2
        assert second["created"] == 0


# --- La garantie centrale ---------------------------------------------------


class TestAucuneModificationAutomatique:
    """*Vérifier qu'aucune suggestion ne peut modifier un référentiel sans
    validation explicite* — la vérification demandée par la consigne."""

    def test_la_collecte_ne_touche_aucun_referentiel(self, source_rss, referential):
        avant = list(Measure.objects.filter(referential=referential).values_list("code", flat=True))

        with patch("apps.regulatory_watch.services.safe_get", return_value=_Reponse(RSS)):
            services.poll_source(source_rss)

        apres = list(Measure.objects.filter(referential=referential).values_list("code", flat=True))
        assert avant == apres
        assert WatchUpdate.objects.count() == 2

    def test_retenir_une_suggestion_ne_cree_aucune_mesure(
        self, suggestion, referential, exploitant
    ):
        """« Retenir » dit « ceci nous concerne ». En tirer une exigence est
        un second geste, volontairement séparé."""
        avant = Measure.objects.filter(referential=referential).count()

        services.review_update(
            suggestion,
            status=WatchUpdate.Status.KEPT,
            reviewer=exploitant,
            target_referential=referential,
        )

        assert Measure.objects.filter(referential=referential).count() == avant
        assert suggestion.integrated_measures.count() == 0

    def test_une_decision_sans_relecteur_est_refusee(self, suggestion):
        """Une suggestion qui change d'état sans qu'on sache qui l'a lue n'est
        pas une décision, c'est un effet de bord."""
        with pytest.raises(services.ReviewRequiredError):
            services.review_update(suggestion, status=WatchUpdate.Status.KEPT, reviewer=None)

    def test_l_integration_sans_relecteur_est_refusee(self, suggestion, referential):
        with pytest.raises(services.ReviewRequiredError):
            services.integrate_as_measure(
                suggestion,
                reviewer=None,
                referential=referential,
                domain_code="domaine-a",
                code="X.1",
                official_title="Un titre",
                plain_language="Une question ?",
            )
        assert not Measure.objects.filter(code="X.1").exists()

    def test_le_statut_integre_ne_se_pose_pas_a_la_main(self, suggestion, exploitant):
        """« Intégrée » est la conséquence d'une intégration réelle, pas une
        case qu'on coche."""
        with pytest.raises(services.WatchError):
            services.review_update(
                suggestion, status=WatchUpdate.Status.INTEGRATED, reviewer=exploitant
            )

    def test_l_api_de_tri_n_expose_pas_le_statut_integre(self, api_client, suggestion, exploitant):
        response = api_client.post(
            reverse("watch-update-review", args=[suggestion.id]),
            {"status": "integrated"},
            format="json",
            **_auth(api_client, exploitant),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_une_mesure_ne_se_cree_pas_avec_un_contenu_recopie(
        self, suggestion, referential, exploitant
    ):
        """Une exigence rédigée par copie d'un titre de communiqué serait
        illisible pour un dirigeant, et fausserait le score."""
        with pytest.raises(services.WatchError):
            services.integrate_as_measure(
                suggestion,
                reviewer=exploitant,
                referential=referential,
                domain_code="domaine-a",
                code="X.1",
                official_title="",
                plain_language="",
            )


class TestIntegration:
    def test_cree_la_mesure_avec_sa_source(self, suggestion, referential, exploitant):
        """« On ne livre pas ce qu'on ne peut pas sourcer » : la mesure garde
        le lien vers la publication officielle."""
        mesure = services.integrate_as_measure(
            suggestion,
            reviewer=exploitant,
            referential=referential,
            domain_code="domaine-a",
            code="IA.1",
            official_title="Encadrer l'usage des systèmes d'IA générative",
            plain_language="Avez-vous encadré l'usage des outils d'IA par vos équipes ?",
        )

        assert mesure.source_url == suggestion.url
        assert "Autorité de test" in mesure.source_reference
        assert "09/09/2026" in mesure.source_reference

    def test_marque_la_suggestion_comme_integree_et_garde_le_lien(
        self, suggestion, referential, exploitant
    ):
        mesure = services.integrate_as_measure(
            suggestion,
            reviewer=exploitant,
            referential=referential,
            domain_code="domaine-a",
            code="IA.1",
            official_title="Encadrer l'usage des systèmes d'IA générative",
            plain_language="Avez-vous encadré l'usage des outils d'IA ?",
        )

        suggestion.refresh_from_db()
        assert suggestion.status == WatchUpdate.Status.INTEGRATED
        assert suggestion.reviewed_by == exploitant
        assert list(suggestion.integrated_measures.all()) == [mesure]

    def test_la_mesure_se_range_a_la_fin_de_son_domaine(self, suggestion, referential, exploitant):
        """Une mesure ajoutée en cours de vie ne se glisse pas au milieu d'une
        numérotation que des évaluations en cours utilisent déjà."""
        rang_max = max(
            Measure.objects.filter(domain__code="domaine-a").values_list("order", flat=True)
        )

        mesure = services.integrate_as_measure(
            suggestion,
            reviewer=exploitant,
            referential=referential,
            domain_code="domaine-a",
            code="IA.1",
            official_title="Un intitulé",
            plain_language="Une question ?",
        )

        assert mesure.order == rang_max + 1

    def test_un_domaine_inconnu_est_refuse(self, suggestion, referential, exploitant):
        from apps.assessments import services as assessments_services

        with pytest.raises(assessments_services.MeasureNotInReferentialError):
            services.integrate_as_measure(
                suggestion,
                reviewer=exploitant,
                referential=referential,
                domain_code="domaine-inexistant",
                code="IA.1",
                official_title="Un intitulé",
                plain_language="Une question ?",
            )

    def test_un_code_deja_pris_est_refuse(self, suggestion, referential, exploitant):
        from apps.assessments import services as assessments_services

        with pytest.raises(assessments_services.MeasureNotInReferentialError):
            services.integrate_as_measure(
                suggestion,
                reviewer=exploitant,
                referential=referential,
                domain_code="domaine-a",
                code="1",  # déjà utilisé par le référentiel de test
                official_title="Un intitulé",
                plain_language="Une question ?",
            )

    def test_la_mesure_integree_entre_dans_le_questionnaire(
        self, suggestion, referential, exploitant, tenant
    ):
        """Le bout du chemin : ce qui est validé se retrouve réellement dans
        le diagnostic des clients."""
        from apps.assessments import services as assessments_services

        services.integrate_as_measure(
            suggestion,
            reviewer=exploitant,
            referential=referential,
            domain_code="domaine-a",
            code="IA.1",
            official_title="Encadrer l'usage des systèmes d'IA générative",
            plain_language="Avez-vous encadré l'usage des outils d'IA ?",
        )

        structure = assessments_services.get_referential_structure(referential, tenant=tenant)
        codes = [m.code for bloc in structure for m in bloc["measures"]]
        assert "IA.1" in codes


# --- Le résumé par IA -------------------------------------------------------


class TestResumeParIA:
    def test_le_resume_ne_remplace_jamais_le_texte_source(self, suggestion, exploitant):
        with patch(
            "apps.ai_assistant.services.summarize_public_document",
            return_value=(
                "Un résumé en trois phrases.",
                {
                    "model": "claude-haiku-4-5",
                    "tokens_input": 300,
                    "tokens_output": 40,
                    "duration_ms": 900,
                },
            ),
        ):
            services.summarize_update(suggestion, reviewer=exploitant)

        suggestion.refresh_from_db()
        assert suggestion.ai_summary == "Un résumé en trois phrases."
        # Le texte source est la référence : il reste, intact, à côté.
        assert "dix mesures" in suggestion.source_excerpt
        assert suggestion.ai_summary_at is not None
        assert suggestion.ai_summary_model == "claude-haiku-4-5"

    def test_le_resume_n_est_pas_declenche_par_la_collecte(self, source_rss):
        """Sobriété : on ne paie pas un résumé pour une publication que
        personne n'ouvrira."""
        with (
            patch("apps.regulatory_watch.services.safe_get", return_value=_Reponse(RSS)),
            patch("apps.ai_assistant.services.summarize_public_document") as resumer,
        ):
            services.poll_source(source_rss)

        resumer.assert_not_called()
        assert all(not update.ai_summary for update in WatchUpdate.objects.all())

    def test_le_prompt_interdit_de_conclure(self):
        """Consigne V2-7 §7 : elle résume et ne conclut pas."""
        from apps.ai_assistant import prompts

        prompt = prompts.REGULATORY_SUMMARY_SYSTEM_PROMPT
        assert "tu ne conclus pas" in prompt.lower()
        assert "n'ajoute aucun fait" in prompt.lower()

    def test_sans_texte_source_il_n_y_a_rien_a_resumer(self, suggestion, exploitant):
        suggestion.source_excerpt = ""
        suggestion.save(update_fields=["source_excerpt"])

        with pytest.raises(services.WatchError):
            services.summarize_update(suggestion, reviewer=exploitant)


# --- La console -------------------------------------------------------------


class TestConsole:
    def test_la_file_montre_ce_qui_a_change_et_le_lien_officiel(
        self, api_client, suggestion, exploitant
    ):
        response = api_client.get(reverse("watch-queue"), **_auth(api_client, exploitant))

        assert response.status_code == status.HTTP_200_OK
        ligne = next(item for item in response.data["results"] if item["id"] == suggestion.id)
        assert ligne["url"] == suggestion.url
        assert ligne["source_publisher"] == "Autorité de test"
        assert ligne["source_excerpt"]
        assert response.data["summary"]["promise"] == sources.PROMESSE

    def test_la_file_remonte_l_etat_des_sources(self, api_client, exploitant):
        """Avant de faire confiance à une file vide, il faut savoir si les
        sources répondent."""
        response = api_client.get(reverse("watch-queue"), **_auth(api_client, exploitant))

        assert "failing" in response.data["health"]
        assert "unconfigured" in response.data["health"]

    def test_l_integration_depuis_la_console(self, api_client, suggestion, referential, exploitant):
        response = api_client.post(
            reverse("watch-update-integrate", args=[suggestion.id]),
            {
                "referential": referential.slug,
                "domain_code": "domaine-a",
                "code": "IA.1",
                "official_title": "Encadrer l'usage des systèmes d'IA générative",
                "plain_language": "Avez-vous encadré l'usage des outils d'IA ?",
            },
            format="json",
            **_auth(api_client, exploitant),
        )

        assert response.status_code == status.HTTP_201_CREATED
        mesure = Measure.objects.get(code="IA.1")
        assert mesure.source_url == suggestion.url

    def test_l_integration_est_journalisee(self, api_client, suggestion, referential, exploitant):
        """Ajouter une exigence au produit est un acte de gestion : il se
        retrouve dans le journal d'audit, avec le lien vers sa source."""
        from apps.platform_admin.models import AdminAuditLog

        api_client.post(
            reverse("watch-update-integrate", args=[suggestion.id]),
            {
                "referential": referential.slug,
                "domain_code": "domaine-a",
                "code": "IA.1",
                "official_title": "Un intitulé",
                "plain_language": "Une question ?",
            },
            format="json",
            **_auth(api_client, exploitant),
        )

        ligne = AdminAuditLog.objects.filter(target__contains="IA.1").first()
        assert ligne is not None
        assert suggestion.url in ligne.detail

    def test_configurer_une_source_sans_redeploiement(self, api_client, exploitant):
        """C'est ce qui permet d'installer le flux EUR-Lex ciblé : la source
        est livrée inactive et sans adresse, précisément pour être branchée
        ici."""
        response = api_client.patch(
            reverse("watch-source-detail", args=["eurlex-cyber"]),
            {
                "feed_url": "https://eur-lex.europa.eu/EN/display-feed.rss?rssId=999",
                "is_active": True,
            },
            format="json",
            **_auth(api_client, exploitant),
        )

        assert response.status_code == status.HTTP_200_OK
        source = services.get_source(slug="eurlex-cyber")
        assert source.is_active is True
        assert source.feed_url.endswith("rssId=999")


class TestAccesConsoleUniquement:
    """La veille alimente le catalogue partagé : une suggestion non triée n'a
    rien à faire sous les yeux d'un client."""

    @pytest.mark.parametrize(
        "url_name,args",
        [("watch-queue", []), ("watch-source-list", [])],
    )
    def test_un_client_n_atteint_pas_la_veille(
        self, api_client, tenant, tenant_owner, url_name, args
    ):
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {_login(api_client, tenant_owner.email)}",
            "HTTP_X_TENANT_ID": str(tenant.id),
        }
        response = api_client.get(reverse(url_name, args=args), **headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_un_commercial_lit_mais_ne_decide_pas(self, api_client, suggestion, user_factory):
        """Trier la veille, c'est décider de ce que le produit exigera de ses
        clients demain."""
        commercial = user_factory(email="commercial-veille@example.com", is_staff=True)
        PlatformAdminProfile.objects.create(
            user=commercial, level=PlatformAdminProfile.Level.COMMERCIAL
        )
        headers = _auth(api_client, commercial)

        lecture = api_client.get(reverse("watch-queue"), **headers)
        decision = api_client.post(
            reverse("watch-update-review", args=[suggestion.id]),
            {"status": "dismissed"},
            format="json",
            **headers,
        )

        assert lecture.status_code == status.HTTP_200_OK
        assert decision.status_code == status.HTTP_403_FORBIDDEN


class TestParseurs:
    """Les parseurs, isolés de la base et du réseau."""

    def test_une_entree_sans_identifiant_reste_stable(self):
        xml = b"""<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Sans guid</title><link>https://exemple.test/a</link></item>
        </channel></rss>"""

        premier = feeds.parse(xml, fmt="rss")[0].external_id
        second = feeds.parse(xml, fmt="rss")[0].external_id

        # Sinon chaque passage recréerait la même publication.
        assert premier == second

    def test_une_date_illisible_ne_perd_pas_la_publication(self):
        xml = b"""<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Date cassee</title><link>https://exemple.test/a</link>
        <pubDate>pas une date</pubDate></item>
        </channel></rss>"""

        entrees = feeds.parse(xml, fmt="rss")

        assert len(entrees) == 1
        assert entrees[0].published_at is None

    def test_un_flux_illisible_leve_une_erreur_plutot_que_de_deviner(self):
        with pytest.raises(feeds.FeedError):
            feeds.parse(b"<html>ceci n'est pas un flux", fmt="rss")
