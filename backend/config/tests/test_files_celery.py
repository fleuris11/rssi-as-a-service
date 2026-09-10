"""Aucune tâche du projet ne part dans une file que personne ne consomme.

Ce test ne garde pas la veille réglementaire : il garde **le prochain module**.

Ce qui s'est passé en V2-7 : ``apps.regulatory_watch.tasks`` a été écrite sans
entrée dans ``CELERY_TASK_ROUTES``. Elle est donc tombée dans
``CELERY_TASK_DEFAULT_QUEUE`` (« default »), que le worker ne consomme pas
(``-Q monitoring,emails,ai``). Chaque lundi à 06 h 15, le planificateur
publiait un message que rien ne dépilait. La veille ne veillait pas.

**Aucun test ne pouvait le voir**, parce que les tests appellent les tâches
directement (``poll_sources_task()``), jamais à travers le courtier. La suite
restait verte, la fonctionnalité était morte, et la docstring du module
affirmait le contraire.

La faute est structurelle, pas locale : *tout* nouveau module de tâches la
rejouera tant qu'ajouter une route restera une étape qu'on peut oublier. Ce
balayage rend l'oubli rouge.

Deux principes de construction :

1. **La liste des files consommées n'est pas recopiée ici.** Elle est lue dans
   la commande du worker, dans les fichiers ``docker-compose``. Une liste
   recopiée diverge de la réalité au premier changement — et un contrôle qui
   décrit un monde périmé ne contrôle rien. C'est la même leçon que le
   ``awk`` des fins de ligne dans ``verifier.sh``.
2. **On interroge le routeur de Celery**, pas le dictionnaire des réglages.
   C'est le routeur qui décide en production ; relire ``CELERY_TASK_ROUTES``
   reviendrait à vérifier une intention, ce qui est exactement l'erreur qu'on
   corrige.
"""

import pathlib
import re

import pytest
from django.conf import settings

from config.celery import app

#: La racine du dépôt : ``backend/config/tests/`` → trois crans au-dessus.
#: Les fichiers ``docker-compose`` vivent à la racine, pas dans ``backend``.
RACINE = pathlib.Path(__file__).resolve().parents[3]

#: Tâches fournies par des bibliothèques tierces (Celery lui-même). Elles ne
#: sont jamais publiées par ce projet : ni le planificateur ni le code ne les
#: appellent. Les exiger routées imposerait une file à du code qu'on ne
#: maîtrise pas.
PREFIXES_HORS_PROJET = ("celery.",)


def _files_consommees_par_le_worker() -> dict[str, set[str]]:
    """Les files réellement dépilées, lues dans la commande du worker.

    Renvoie ``{nom du fichier compose: {files}}``. On lit les DEUX fichiers :
    un worker de production qui consommerait moins de files que celui de
    développement ferait échouer en production ce qui passe en local, et
    personne ne le verrait avant la mise en ligne.
    """
    motif = re.compile(r"celery\s+-A\s+config\s+worker[^\n]*?-Q\s+([\w,]+)")
    trouve = {}
    for nom in ("docker-compose.yml", "docker-compose.prod.yml"):
        chemin = RACINE / nom
        if not chemin.exists():
            continue
        correspondances = motif.findall(chemin.read_text(encoding="utf-8"))
        assert correspondances, (
            f"{nom} ne déclare aucun worker Celery avec « -Q ». Si la commande "
            f"a changé de forme, c'est CE test qu'il faut corriger — sans quoi "
            f"il passerait au vert sans plus rien lire."
        )
        for liste in correspondances:
            trouve.setdefault(nom, set()).update(partie for partie in liste.split(",") if partie)
    assert trouve, "Aucun fichier docker-compose lisible : le test ne mesure rien."
    return trouve


def _taches_du_projet() -> list[str]:
    """Toutes les tâches déclarées par les apps du projet."""
    app.loader.import_default_modules()  # force l'autodécouverte
    return sorted(nom for nom in app.tasks if not nom.startswith(PREFIXES_HORS_PROJET))


def _file_de(nom_de_tache: str) -> str:
    """La file RÉELLEMENT résolue par le routeur, comme en production."""
    route = app.amqp.router.route({}, nom_de_tache)
    file = route.get("queue")
    if file is None:
        return settings.CELERY_TASK_DEFAULT_QUEUE
    # Selon la version, le routeur renvoie un objet Queue ou une chaîne.
    return getattr(file, "name", file)


def test_le_worker_declare_les_memes_files_partout():
    """Développement et production consomment le même jeu de files.

    Sinon une tâche correctement routée en local serait perdue en production
    — le défaut de la V2-7, déplacé d'un cran.
    """
    par_fichier = _files_consommees_par_le_worker()
    jeux = list(par_fichier.values())
    assert all(jeu == jeux[0] for jeu in jeux), (
        "Les workers ne consomment pas les mêmes files selon l'environnement : "
        f"{ {nom: sorted(files) for nom, files in par_fichier.items()} }"
    )


def test_aucune_tache_ne_part_dans_une_file_non_consommee():
    """LE test. Chaque tâche du projet doit atterrir dans une file dépilée."""
    consommees = set().union(*_files_consommees_par_le_worker().values())
    taches = _taches_du_projet()

    assert taches, "Aucune tâche découverte : le balayage ne mesure rien."

    perdues = {nom: _file_de(nom) for nom in taches if _file_de(nom) not in consommees}

    assert not perdues, (
        "Ces tâches partent dans une file qu'aucun worker ne consomme : elles "
        "s'empileront dans Redis sans jamais s'exécuter, en silence.\n"
        + "\n".join(f"  - {nom} → file « {file} »" for nom, file in sorted(perdues.items()))
        + f"\n\nFiles consommées par le worker : {sorted(consommees)}.\n"
        "Corriger en ajoutant une entrée dans CELERY_TASK_ROUTES "
        "(config/settings.py), et non en élargissant le « -Q » du worker sans "
        "y avoir réfléchi : les files sont séparées pour qu'un incident sur "
        "l'une ne retarde pas les autres (cadrage §4.4)."
    )


def test_chaque_tache_planifiee_existe_et_est_routee():
    """Le planificateur ne référence que des tâches réelles et dépilables.

    Une entrée de ``beat_schedule`` qui nomme une tâche inexistante échoue à
    l'exécution, dans le conteneur beat, là où personne ne regarde.
    """
    consommees = set().union(*_files_consommees_par_le_worker().values())
    connues = set(app.tasks)

    problemes = []
    for cle, entree in app.conf.beat_schedule.items():
        nom = entree["task"]
        if nom not in connues:
            problemes.append(f"  - « {cle} » planifie « {nom} », qui n'existe pas")
        elif _file_de(nom) not in consommees:
            problemes.append(
                f"  - « {cle} » planifie « {nom} » → file « {_file_de(nom)} », non consommée"
            )

    assert not problemes, "Entrées de planification inexploitables :\n" + "\n".join(problemes)


@pytest.mark.parametrize(
    "nom_de_tache",
    [
        "apps.regulatory_watch.tasks.poll_sources_task",
        "apps.monitoring.tasks.dispatch_due_checks",
    ],
)
def test_les_taches_periodiques_sensibles_sont_dans_monitoring(nom_de_tache):
    """Deux ancres explicites : si quelqu'un déroute ces tâches, il le lit ici.

    ``poll_sources_task`` y figure parce que c'est elle qui a été perdue.
    """
    assert _file_de(nom_de_tache) == "monitoring"
