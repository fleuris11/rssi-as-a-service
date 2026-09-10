"""Bibliotheque documentaire (V2-5, ADR-032).

Le modele ``GeneratedDocument`` et sa machinerie de versionnement et d'export
vivent dans ``apps.ai_assistant`` depuis la phase 4. Ce sous-paquet y ajoute
la COMPOSITION : les documents assembles a partir des donnees de la
plateforme, sans appel d'IA.

Le nom de l'app n'est plus tout a fait juste — elle contient desormais plus de
deterministe que d'IA. Deplacer le modele dans une app ``documents`` aurait
demande de migrer une table qui porte, en production, les documents de vrais
clients. Le nom est une dette assumee ; les donnees passent avant.
"""

from . import composers, context, editable, registry  # noqa: F401
