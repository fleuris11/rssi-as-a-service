"""La bibliothèque de cours : son contenu, et sa commande de chargement.

Ce fichier teste d'abord des DONNÉES, ce qui est inhabituel et voulu. Un cours
mal écrit ne casse rien : il se charge, se publie, et enseigne quelque chose de
faux à un salarié. Aucun test d'intégration ne l'attrape. Les garde-fous ici
sont donc ceux d'une relecture qu'on automatise : une question sans bonne
réponse, un renvoi vers un écran inexistant, un choix unique à deux bonnes
réponses, un quiz trop court pour que son seuil veuille dire quelque chose.
"""

import pytest
from django.core.management import call_command

from apps.training import catalogue
from apps.training.models import (
    QUESTIONS_MINIMUM_POUR_UN_SEUIL,
    Course,
    CourseAssignment,
    Question,
)

pytestmark = pytest.mark.django_db


TOUS = [pytest.param(cours, id=cours["slug"]) for cours in catalogue.COURS]


# --- Le contenu ------------------------------------------------------------


def test_les_slugs_sont_uniques_et_ne_recouvrent_pas_le_cours_de_f1():
    slugs = [cours["slug"] for cours in catalogue.COURS]
    assert len(slugs) == len(set(slugs))
    # « hameconnage » est chargé par seed_training_demo et porte déjà des
    # inscriptions : le reprendre ici créerait deux cours du même sujet.
    assert "hameconnage" not in slugs


@pytest.mark.parametrize("cours", TOUS)
def test_un_cours_a_de_quoi_soutenir_son_seuil(cours):
    assert len(cours["questions"]) >= QUESTIONS_MINIMUM_POUR_UN_SEUIL, (
        f"{cours['slug']} : en deçà de {QUESTIONS_MINIMUM_POUR_UN_SEUIL} questions, une "
        "seule erreur fait basculer le résultat."
    )
    assert len(cours["ecrans"]) >= 3


@pytest.mark.parametrize("cours", TOUS)
def test_les_questions_sont_numerotees_sans_trou_et_visent_un_ecran_reel(cours):
    ordres = [question[0] for question in cours["questions"]]
    assert ordres == list(range(1, len(ordres) + 1))

    for ordre, vise, *_ in cours["questions"]:
        assert 1 <= vise <= len(cours["ecrans"]), (
            f"{cours['slug']} Q{ordre} renvoie à l'écran {vise}, qui n'existe pas. Sans "
            "écran valide, « revoir ce que vous avez raté » n'a aucune source."
        )


@pytest.mark.parametrize("cours", TOUS)
def test_chaque_question_a_une_explication_et_des_choix_utilisables(cours):
    for ordre, _vise, enonce, genre, explication, choix in cours["questions"]:
        ou = f"{cours['slug']} Q{ordre}"
        assert enonce.strip(), f"{ou} : énoncé vide."
        # L'explication est la seule partie du quiz qui forme : un « faux » sec
        # n'apprend rien. On exige une phrase, pas un mot.
        assert len(explication.strip()) >= 80, f"{ou} : explication trop courte."
        assert len(choix) >= 3, f"{ou} : moins de trois choix."

        textes = [texte.strip() for texte, _ in choix]
        assert all(textes), f"{ou} : un choix vide."
        assert len(set(textes)) == len(textes), f"{ou} : deux choix identiques."

        justes = [texte for texte, correct in choix if correct]
        assert justes, f"{ou} : aucune bonne réponse — le studio refuserait de publier."
        if genre == Question.Kind.SINGLE:
            assert len(justes) == 1, f"{ou} : choix unique avec {len(justes)} bonnes réponses."
        else:
            assert len(justes) >= 2, (
                f"{ou} : un choix multiple avec une seule bonne réponse se comporte comme "
                "un choix unique, et déroute."
            )
        assert len(justes) < len(choix), f"{ou} : tous les choix sont justes."


@pytest.mark.parametrize("cours", TOUS)
def test_le_contenu_des_ecrans_respecte_le_schema_des_blocs(cours):
    from apps.training import blocks as blocs_de_contenu

    for rang, ecran in enumerate(cours["ecrans"], start=1):
        assert ecran["title"].strip()
        assert ecran["seconds"] > 0
        # La même validation que ``Screen.save()`` : un écran mal formé doit
        # être refusé ici, pas découvert par un salarié dans le train. La
        # fonction lève ``BlocInvalide`` — c'est elle qui porte l'assertion.
        try:
            blocs_de_contenu.valider(ecran["content"])
        except blocs_de_contenu.BlocInvalide as erreur:
            pytest.fail(f"{cours['slug']}, écran {rang} : {erreur}")


# --- La commande -----------------------------------------------------------


def test_la_commande_charge_publie_et_ne_double_rien():
    call_command("seed_catalogue_formation", verbosity=0)

    for donnees in catalogue.COURS:
        cours = Course.objects.get(slug=donnees["slug"])
        assert cours.est_de_la_bibliotheque, "un cours de bibliothèque n'appartient à personne"
        version = cours.published_version
        assert version is not None, f"{cours.slug} n'est pas publié"
        assert version.screens.count() == len(donnees["ecrans"])
        assert version.questions.count() == len(donnees["questions"])

    # Rejouée, elle ne recrée rien : c'est la propriété qui permet de la lancer
    # en production sans inventaire préalable.
    avant = (Course.objects.count(), Question.objects.count())
    call_command("seed_catalogue_formation", verbosity=0)
    assert (Course.objects.count(), Question.objects.count()) == avant


def test_reset_reprend_le_contenu_sans_supprimer_la_version_publiee():
    call_command("seed_catalogue_formation", verbosity=0)
    cours = Course.objects.get(slug=catalogue.COURS[0]["slug"])
    version_avant = cours.published_version.id

    call_command("seed_catalogue_formation", "--reset", verbosity=0)

    cours.refresh_from_db()
    # La MÊME version : une inscription pointe dessus, la supprimer casserait
    # le parcours d'un salarié en cours de route.
    assert cours.published_version.id == version_avant
    assert cours.published_version.screens.count() == len(catalogue.COURS[0]["ecrans"])


def test_attribution_a_un_client(tenant):
    call_command("seed_catalogue_formation", "--tenant", tenant.slug, verbosity=0)

    attribues = set(
        CourseAssignment.all_objects.filter(tenant=tenant).values_list("course__slug", flat=True)
    )
    assert {cours["slug"] for cours in catalogue.COURS} <= attribues


def test_un_seul_cours_a_la_fois():
    slug = catalogue.COURS[1]["slug"]
    call_command("seed_catalogue_formation", "--slug", slug, verbosity=0)

    assert Course.objects.filter(slug=slug).exists()
    assert not Course.objects.filter(slug=catalogue.COURS[0]["slug"]).exists()
