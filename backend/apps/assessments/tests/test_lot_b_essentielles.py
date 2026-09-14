"""« Les 10 mesures essentielles » sur une installation NEUVE.

Le défaut que ces tests épinglent, trouvé en relisant l'ordre de démarrage
des conteneurs et non par un test : ``migrate`` s'exécute AVANT
``load_anssi_referential``. Sur une base neuve, la migration 0005 cherche un
référentiel ANSSI qui n'existe pas encore et ne pose rien ; le chargeur, lui,
ne savait rien de la composition. Elle n'existait qu'en production, où l'ANSSI
était déjà là — et aucune installation neuve, CI comprise, ne la recevait.

La base de test est précisément une base neuve : la migration 0005 y a été
jouée sans ANSSI. C'est ce qui rend ces tests fidèles au défaut.
"""

import importlib

import pytest
from django.core.management import call_command

from apps.assessments import essentielles
from apps.assessments.models import MeasureSubset

pytestmark = pytest.mark.django_db


def _composition():
    return MeasureSubset.objects.filter(slug=essentielles.SLUG).first()


def _codes(composition):
    return list(composition.items.order_by("order").values_list("measure__code", flat=True))


class TestInstallationNeuve:
    def test_une_base_neuve_recoit_les_dix_essentielles(self):
        # Précondition POSÉE : la migration n'a rien créé sur cette base.
        MeasureSubset.objects.filter(slug=essentielles.SLUG).delete()

        call_command("load_anssi_referential")

        composition = _composition()
        assert composition is not None
        assert _codes(composition) == essentielles.CODES
        assert composition.owner_tenant_id is None

    def test_rejouer_le_chargement_ne_duplique_rien(self):
        call_command("load_anssi_referential")
        call_command("load_anssi_referential")

        assert MeasureSubset.objects.filter(slug=essentielles.SLUG).count() == 1
        assert _composition().items.count() == len(essentielles.CODES)

    def test_une_composition_ajustee_depuis_la_console_n_est_pas_reecrite(self):
        call_command("load_anssi_referential")
        _composition().items.exclude(measure__code="2").delete()

        # Chaque déploiement rejoue le chargeur : il ne doit pas défaire le
        # travail de l'exploitant.
        call_command("load_anssi_referential")

        assert _codes(_composition()) == ["2"]


class TestTexteServiAuClient:
    def test_la_description_est_accentuee(self):
        call_command("load_anssi_referential")

        assert _composition().description.startswith("Par où commencer.")

    def test_corrige_le_texte_sans_accents_pose_par_la_migration(self):
        """Le texte de la migration 0005 est affiché au client sans accents.
        Le chargeur, rejoué à chaque déploiement, le corrige."""
        call_command("load_anssi_referential")
        MeasureSubset.objects.filter(slug=essentielles.SLUG).update(
            description=essentielles.DESCRIPTION_SANS_ACCENTS
        )

        call_command("load_anssi_referential")

        assert _composition().description == essentielles.DESCRIPTION

    def test_une_description_retouchee_depuis_la_console_est_conservee(self):
        call_command("load_anssi_referential")
        MeasureSubset.objects.filter(slug=essentielles.SLUG).update(
            description="Texte choisi par l'exploitant."
        )

        call_command("load_anssi_referential")

        assert _composition().description == "Texte choisi par l'exploitant."


class TestDeuxCopiesQuiNeDivergentPas:
    def test_la_migration_et_le_module_portent_les_memes_codes(self):
        """La migration garde sa copie figée (elle ne lit pas le code vivant) ;
        ce test empêche les deux listes de diverger en silence."""
        migration = importlib.import_module(
            "apps.assessments.migrations.0005_dix_mesures_essentielles"
        )

        assert migration.CODES_ESSENTIELS == essentielles.CODES
