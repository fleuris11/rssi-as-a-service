"""Taches Celery de la veille (V2-7).

Orchestration seulement : la logique vit dans ``services.py``.

File ``monitoring`` — la veille est une collecte periodique passive, pas une
operation d'IA (le resume, lui, est declenche a la main depuis la console).
La file n'est PAS declaree ici : elle vient de ``CELERY_TASK_ROUTES``
(``config/settings.py``), seul endroit qui route les taches du projet.

Cette docstring a affirme cette file pendant toute la V2-7 alors qu'aucune
route ne l'etablissait : la tache partait dans ``default``, que le worker ne
consomme pas, et le passage hebdomadaire ne s'executait jamais. Une phrase
qui decrit une intention se lit comme un constat — d'ou le test
``config/tests/test_files_celery.py``, qui verifie la file reellement
resolue plutot que ce qu'on en ecrit.
"""

import logging

from celery import shared_task

from . import services

logger = logging.getLogger(__name__)


@shared_task
def poll_sources_task():
    """Passage hebdomadaire sur les sources actives.

    Naturellement idempotente : une seconde execution le meme jour retrouve
    les memes publications et n'en cree aucune, la contrainte d'unicite
    (source, external_id) faisant foi. Une redelivrance est donc sans effet.
    """
    rapport = services.poll_all_sources()
    if rapport["failed"]:
        logger.warning(
            "Veille : %s source(s) en echec sur %s (%s)",
            len(rapport["failed"]),
            rapport["sources"],
            ", ".join(rapport["failed"]),
        )
    return rapport
