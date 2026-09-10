"""Fixtures partagées par les tests de la veille réglementaire.

Elles sont définies dans ``test_veille.py``, où elles sont nées avec les
premiers tests. Les ré-exposer ici plutôt que de les importer d'un module de
test à l'autre : pytest les résout alors par le mécanisme normal des
``conftest``, sans redéfinition de nom — un import direct oblige à parsemer
les signatures de ``noqa: F811``, ce qui finit par masquer de vraies
redéfinitions.
"""

from .test_veille import (  # noqa: F401 - ré-export de fixtures pour pytest
    exploitant,
    source_page,
    source_rss,
    suggestion,
)
