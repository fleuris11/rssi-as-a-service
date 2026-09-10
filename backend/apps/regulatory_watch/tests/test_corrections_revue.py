"""Les quatre incohérences relevées par la revue de fin de phase V2-7.

Ces tests ne couvrent pas une fonctionnalité : ils épinglent quatre défauts
que la suite d'origine laissait passer, chacun trouvé en attaquant la règle
par le côté qu'aucun test ne regardait.

- **D2** — « intégrée » est un état terminal. La garde d'origine interdisait
  de POSER ce statut, jamais de le RETIRER : une suggestion repassée en
  « écartée » laissait la mesure dans le référentiel, le lien
  ``integrated_measures`` en place, et ``target_referential`` effacé. La
  traçabilité se contredisait.
- **D3** — ``review_update`` écrasait ``target_referential`` même quand
  l'appelant n'en disait rien.
- **D4** — ``integrate_as_measure`` n'était pas transactionnelle. C'est le
  seul chemin par lequel la veille écrit dans le cœur métier.
- **D5** — la migration de données importait le module vivant.

Les fixtures viennent de ``test_veille.py`` (suggestion, source, exploitant)
et de ``apps/conftest.py`` (referential).
"""

import importlib
import pathlib
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.assessments.models import Measure
from apps.regulatory_watch import services
from apps.regulatory_watch.models import WatchUpdate

from .test_veille import _auth

pytestmark = pytest.mark.django_db


@pytest.fixture
def integree(suggestion, referential, exploitant):
    """Une suggestion réellement intégrée — pas un statut posé à la main."""
    services.integrate_as_measure(
        suggestion,
        reviewer=exploitant,
        referential=referential,
        domain_code="domaine-a",
        code="T.1",
        official_title="Intitulé rédigé par un humain",
        plain_language="Énoncé rédigé en langage clair.",
    )
    suggestion.refresh_from_db()
    return suggestion


class TestEtatTerminal:
    """D2 — « intégrée » ne se retire pas.

    Il n'existe volontairement AUCUN mécanisme de dé-intégration : si
    l'exploitant s'est trompé, il retire la mesure du référentiel. C'est un
    geste distinct, explicite et tracé, qui ne se déguise pas en changement
    de statut d'une suggestion.
    """

    def test_une_suggestion_integree_ne_change_plus_de_statut(self, integree, exploitant):
        with pytest.raises(services.WatchError):
            services.review_update(
                integree, status=WatchUpdate.Status.DISMISSED, reviewer=exploitant
            )

        integree.refresh_from_db()
        assert integree.status == WatchUpdate.Status.INTEGRATED

    def test_le_referentiel_et_le_lien_survivent_a_la_tentative(
        self, integree, referential, exploitant
    ):
        """Le défaut effaçait ``target_referential`` au passage."""
        with pytest.raises(services.WatchError):
            services.review_update(integree, status=WatchUpdate.Status.NEW, reviewer=exploitant)

        integree.refresh_from_db()
        assert integree.target_referential == referential
        assert integree.integrated_measures.count() == 1

    def test_l_api_refuse_aussi(self, api_client, integree, exploitant):
        """Deuxième couche, dans le sérialiseur, indépendante du service."""
        response = api_client.post(
            reverse("watch-update-review", args=[integree.id]),
            {"status": "dismissed"},
            format="json",
            **_auth(api_client, exploitant),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        integree.refresh_from_db()
        assert integree.status == WatchUpdate.Status.INTEGRATED

    def test_le_serialiseur_refuse_seul_sans_passer_par_le_service(self, integree):
        """Isole la DEUXIÈME couche.

        ``test_l_api_refuse_aussi`` ne la prouve pas : en neutralisant le
        sérialiseur, il reste vert, parce que le service refuse et que la vue
        traduit ce refus en 400. Un test qui ne distingue pas la couche qu'il
        garde ne garde pas cette couche — constaté en neutralisant (N2).
        Ici, aucun service n'est appelé : seul le sérialiseur tranche.
        """
        from apps.regulatory_watch.serializers import ReviewUpdateSerializer

        serialiseur = ReviewUpdateSerializer(
            data={"status": "dismissed"}, context={"update": integree}
        )

        assert not serialiseur.is_valid()
        assert "status" in serialiseur.errors

    def test_on_n_integre_pas_deux_fois_la_meme_publication(
        self, integree, referential, exploitant
    ):
        """Sinon une même publication produirait deux mesures, sans rien dire."""
        with pytest.raises(services.WatchError):
            services.integrate_as_measure(
                integree,
                reviewer=exploitant,
                referential=referential,
                domain_code="domaine-a",
                code="T.2",
                official_title="Un autre intitulé",
                plain_language="Un autre énoncé.",
            )

        assert integree.integrated_measures.count() == 1


class TestRattachementConserve:
    """D3 — « non fourni » et « vidé » sont deux gestes différents."""

    def test_re_trier_sans_preciser_le_referentiel_le_conserve(
        self, suggestion, referential, exploitant
    ):
        services.review_update(
            suggestion,
            status=WatchUpdate.Status.KEPT,
            reviewer=exploitant,
            target_referential=referential,
        )
        # Deuxième passage : on ne dit rien du référentiel.
        services.review_update(suggestion, status=WatchUpdate.Status.DISMISSED, reviewer=exploitant)

        suggestion.refresh_from_db()
        assert suggestion.target_referential == referential

    def test_passer_none_explicitement_detache(self, suggestion, referential, exploitant):
        services.review_update(
            suggestion,
            status=WatchUpdate.Status.KEPT,
            reviewer=exploitant,
            target_referential=referential,
        )
        services.review_update(
            suggestion,
            status=WatchUpdate.Status.KEPT,
            reviewer=exploitant,
            target_referential=None,
        )

        suggestion.refresh_from_db()
        assert suggestion.target_referential is None

    def test_l_api_conserve_le_rattachement_quand_le_champ_est_absent(
        self, api_client, suggestion, referential, exploitant
    ):
        headers = _auth(api_client, exploitant)
        api_client.post(
            reverse("watch-update-review", args=[suggestion.id]),
            {"status": "kept", "referential": referential.slug},
            format="json",
            **headers,
        )
        # Corps SANS la clé « referential ».
        api_client.post(
            reverse("watch-update-review", args=[suggestion.id]),
            {"status": "dismissed"},
            format="json",
            **headers,
        )

        suggestion.refresh_from_db()
        assert suggestion.target_referential == referential

    def test_l_api_detache_quand_le_champ_est_fourni_vide(
        self, api_client, suggestion, referential, exploitant
    ):
        headers = _auth(api_client, exploitant)
        api_client.post(
            reverse("watch-update-review", args=[suggestion.id]),
            {"status": "kept", "referential": referential.slug},
            format="json",
            **headers,
        )
        api_client.post(
            reverse("watch-update-review", args=[suggestion.id]),
            {"status": "kept", "referential": ""},
            format="json",
            **headers,
        )

        suggestion.refresh_from_db()
        assert suggestion.target_referential is None


class TestIntegrationTransactionnelle:
    """D4 — tout ou rien.

    Une mesure orpheline serait servie aux clients dans leur questionnaire
    sans qu'aucune suggestion ne la revendique.
    """

    def test_une_erreur_apres_la_creation_ne_laisse_pas_de_mesure_orpheline(
        self, suggestion, referential, exploitant
    ):
        avant = Measure.objects.filter(referential=referential).count()

        # L'échec survient APRÈS `add_measure`, au moment de marquer la
        # suggestion : exactement la fenêtre que la transaction referme.
        with (
            patch.object(WatchUpdate, "save", side_effect=RuntimeError("panne au pire moment")),
            pytest.raises(RuntimeError),
        ):
            services.integrate_as_measure(
                suggestion,
                reviewer=exploitant,
                referential=referential,
                domain_code="domaine-a",
                code="ORPH.1",
                official_title="Intitulé rédigé",
                plain_language="Énoncé rédigé.",
            )

        assert Measure.objects.filter(referential=referential).count() == avant
        assert not Measure.objects.filter(code="ORPH.1").exists()


class TestMigrationFigee:
    """D5 — une migration doit produire le même état quel que soit le jour."""

    def test_la_liste_des_sources_est_figee_dans_la_migration(self):
        migration = importlib.import_module(
            "apps.regulatory_watch.migrations.0002_sources_de_depart"
        )

        assert hasattr(migration, "SOURCES_GELEES")
        assert len(migration.SOURCES_GELEES) == 5
        assert {s["slug"] for s in migration.SOURCES_GELEES} == {
            "anssi-publications",
            "cnil-actualites",
            "nist-csrc-drafts",
            "eurlex-cyber",
            "enisa-publications",
        }

    def test_la_migration_n_importe_pas_le_module_vivant(self):
        """Lire le code d'aujourd'hui, c'est ne pas rejouer hier."""
        chemin = pathlib.Path(services.__file__).parent / "migrations" / "0002_sources_de_depart.py"
        texte = chemin.read_text(encoding="utf-8")

        assert "from apps.regulatory_watch.sources import" not in texte
        assert "from .sources import" not in texte
        assert "seed_sources" not in texte

    def test_eurlex_reste_livree_inactive(self):
        """Une source jamais configurée n'est pas une source en panne."""
        migration = importlib.import_module(
            "apps.regulatory_watch.migrations.0002_sources_de_depart"
        )
        eurlex = next(s for s in migration.SOURCES_GELEES if s["slug"] == "eurlex-cyber")

        assert eurlex["is_active"] is False
        assert eurlex["feed_url"] == ""
