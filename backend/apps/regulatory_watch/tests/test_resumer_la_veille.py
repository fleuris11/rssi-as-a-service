"""La commande de résumé en lot.

Elle existe pour vider une file de plusieurs dizaines d'entrées sans ouvrir
chacune. Ce qui est testé n'est donc pas qu'elle résume — c'est qu'elle reste
bornée, qu'un échec n'arrête pas la boucle, et qu'elle ne décide rien : le
statut et la qualification d'une publication ne sont pas de son ressort.
"""

from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.platform_admin.models import PlatformAdminProfile
from apps.regulatory_watch.models import WatchSource, WatchUpdate

pytestmark = pytest.mark.django_db

USAGE = {
    "model": "claude-haiku-4-5",
    "tokens_input": 300,
    "tokens_output": 40,
    "duration_ms": 900,
}


@pytest.fixture
def exploitant(user_factory):
    user = user_factory(email="veille-lot@example.com", is_staff=True)
    PlatformAdminProfile.objects.create(user=user, level=PlatformAdminProfile.Level.FULL)
    return user


@pytest.fixture
def source(db):
    return WatchSource.objects.create(
        slug="autorite-lot",
        name="Publications",
        publisher="Autorité de test",
        url="https://exemple-autorite.test/publications",
        format=WatchSource.Format.RSS,
    )


@pytest.fixture
def publications(source):
    return [
        WatchUpdate.objects.create(
            source=source,
            external_id=f"pub-{rang}",
            title=f"Publication {rang}",
            url=f"https://exemple-autorite.test/p/{rang}",
            source_excerpt=f"Le texte source de la publication {rang}.",
        )
        for rang in range(1, 4)
    ]


def _resume_factice(*_args, **_kwargs):
    return "Un résumé en trois phrases.", USAGE


# --- Les refus --------------------------------------------------------------


def test_refuse_un_compte_inconnu(publications):
    with pytest.raises(CommandError, match="Aucun compte"):
        call_command("resumer_la_veille", "--acteur", "personne@exemple.test", verbosity=0)


def test_refuse_un_compte_qui_n_est_pas_d_exploitation(user_factory, publications):
    client = user_factory(email="client@exemple.test")
    with pytest.raises(CommandError, match="exploitation"):
        call_command("resumer_la_veille", "--acteur", client.email, verbosity=0)


def test_la_simulation_n_appelle_pas_l_ia(exploitant, publications):
    with patch("apps.ai_assistant.services.summarize_public_document") as appel:
        call_command("resumer_la_veille", "--acteur", exploitant.email, dry_run=True, verbosity=0)

    appel.assert_not_called()
    assert not WatchUpdate.objects.exclude(ai_summary="").exists()


# --- Le travail -------------------------------------------------------------


def test_resume_les_publications_ouvertes_sans_resume(exploitant, publications):
    with patch(
        "apps.ai_assistant.services.summarize_public_document", side_effect=_resume_factice
    ) as appel:
        call_command("resumer_la_veille", "--acteur", exploitant.email, verbosity=0)

    assert appel.call_count == 3
    for publication in publications:
        publication.refresh_from_db()
        assert publication.ai_summary == "Un résumé en trois phrases."
        # Le texte source reste la référence : le résumé vient à côté.
        assert publication.source_excerpt


def test_ne_paie_jamais_deux_fois_le_meme_resume(exploitant, publications):
    with patch("apps.ai_assistant.services.summarize_public_document", side_effect=_resume_factice):
        call_command("resumer_la_veille", "--acteur", exploitant.email, verbosity=0)

    with patch("apps.ai_assistant.services.summarize_public_document") as appel:
        call_command("resumer_la_veille", "--acteur", exploitant.email, verbosity=0)

    appel.assert_not_called()


def test_la_limite_borne_le_nombre_d_appels(exploitant, publications):
    with patch(
        "apps.ai_assistant.services.summarize_public_document", side_effect=_resume_factice
    ) as appel:
        call_command("resumer_la_veille", "--acteur", exploitant.email, limite=1, verbosity=0)

    assert appel.call_count == 1


def test_une_publication_sans_texte_source_est_ignoree(exploitant, source):
    WatchUpdate.objects.create(
        source=source,
        external_id="sans-texte",
        title="Sans extrait",
        url="https://exemple-autorite.test/p/vide",
        source_excerpt="",
    )
    with patch("apps.ai_assistant.services.summarize_public_document") as appel:
        call_command("resumer_la_veille", "--acteur", exploitant.email, verbosity=0)

    appel.assert_not_called()


def test_un_echec_n_arrete_pas_la_boucle(exploitant, publications):
    reponses = [RuntimeError("l'API a répondu 529"), _resume_factice(), _resume_factice()]

    with patch(
        "apps.ai_assistant.services.summarize_public_document", side_effect=reponses
    ) as appel:
        call_command("resumer_la_veille", "--acteur", exploitant.email, verbosity=0)

    assert appel.call_count == 3
    assert WatchUpdate.objects.exclude(ai_summary="").count() == 2


def test_elle_ne_decide_rien(exploitant, publications):
    """Résumer n'est pas qualifier. Le statut et le genre restent intacts —
    retenir ou écarter est un geste humain, posé depuis la console."""
    with patch("apps.ai_assistant.services.summarize_public_document", side_effect=_resume_factice):
        call_command("resumer_la_veille", "--acteur", exploitant.email, verbosity=0)

    for publication in publications:
        publication.refresh_from_db()
        assert publication.status == WatchUpdate.Status.NEW
        assert publication.kind == WatchUpdate.Kind.UNQUALIFIED
        assert publication.reviewed_at is None
        assert publication.target_referential_id is None


def test_une_publication_ecartee_n_est_pas_resumee(exploitant, source):
    """Personne ne l'ouvrira : payer son résumé serait de la dépense pure."""
    WatchUpdate.objects.create(
        source=source,
        external_id="ecartee",
        title="Écartée",
        url="https://exemple-autorite.test/p/ecartee",
        source_excerpt="Un texte.",
        status=WatchUpdate.Status.DISMISSED,
    )
    with patch("apps.ai_assistant.services.summarize_public_document") as appel:
        call_command("resumer_la_veille", "--acteur", exploitant.email, verbosity=0)

    appel.assert_not_called()
