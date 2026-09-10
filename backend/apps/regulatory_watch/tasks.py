"""Taches Celery de la veille (V2-7).

Orchestration seulement : la logique vit dans ``services.py``. File
``monitoring`` — la veille est une collecte periodique passive, pas une
operation d'IA (le resume, lui, est declenche a la main depuis la console).
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
