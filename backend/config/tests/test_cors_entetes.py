"""Tout en-tête personnalisé envoyé par le frontend doit être autorisé en CORS.

## Le défaut que ce fichier existe pour empêcher

Le client de test de Django **n'applique pas CORS**. Un en-tête personnalisé
absent de ``CORS_ALLOW_HEADERS`` laisse donc passer la totalité des tests
serveur — pendant que le navigateur, lui, refuse la requête au contrôle
préalable, avant même de l'envoyer. Le symptôme côté client est un appel qui
« ne part pas », sans trace serveur : le pire cas de figure à diagnostiquer.

C'est arrivé une fois avec ``x-tenant-id`` (voir le commentaire de
``config/settings.py``), et une seconde fois en F1 avec
``x-formation-token`` : l'espace apprenant passait ses 20 tests d'API et
n'aurait rien affiché dans un navigateur.

## Pourquoi lire le code du frontend plutôt que lister des noms

Une liste d'en-têtes écrite ici en dur dirait seulement que quelqu'un a pensé
à l'écrire deux fois. Ce test lit les en-têtes **réellement posés par le code
du frontend** et vérifie que chacun est autorisé : ajouter un en-tête sans
l'autoriser fait rougir le test, sans que personne ait à y penser.
"""

import re

import pytest
from django.conf import settings

#: Les fichiers du frontend qui posent des en-têtes sur les appels d'API.
FICHIERS = ("frontend/src/api/client.js", "frontend/src/api/endpoints.js")

#: Les DEUX formes qu'un en-tête prend dans ce code, et il a fallu les deux :
#:
#: - `{ 'X-Formation-Token': jeton }` — littéral d'objet, suivi de deux-points ;
#: - `config.headers['X-Tenant-Id'] = tenantId` — écriture par crochets.
#:
#: La première version de cette expression ne connaissait que les deux-points,
#: et manquait donc `x-tenant-id` : le garde-fou passait à côté de l'en-tête
#: même dont l'oubli avait motivé son écriture. C'est le test de contrôle
#: ci-dessous qui l'a signalé — d'où son existence.
#:
#: Les en-têtes standard (Authorization, Content-Type) ne sont pas cherchés :
#: ils sont déjà dans la liste par défaut de django-cors-headers.
ENTETE = re.compile(r"['\"](X-[A-Za-z-]+)['\"]\s*(?::|\])")


def _entetes_du_frontend() -> set[str]:
    racine = settings.BASE_DIR.parent
    trouves = set()
    manquants = []
    for chemin in FICHIERS:
        fichier = racine / chemin
        if not fichier.exists():
            manquants.append(str(fichier))
            continue
        trouves |= {nom.lower() for nom in ENTETE.findall(fichier.read_text(encoding="utf-8"))}
    if manquants:
        pytest.skip(f"Frontend non monté sur cet environnement : {manquants[0]}")
    return trouves


def test_le_frontend_pose_bien_des_entetes_personnalises():
    """Garde-fou du garde-fou : si l'expression régulière cesse de trouver quoi
    que ce soit, le test suivant passerait au vert sans rien vérifier."""
    entetes = _entetes_du_frontend()
    assert entetes, "Aucun en-tête personnalisé trouvé — l'analyse du frontend a cessé de marcher."
    assert "x-tenant-id" in entetes


def test_chaque_entete_du_frontend_est_autorise_en_cors():
    autorises = {nom.lower() for nom in settings.CORS_ALLOW_HEADERS}
    absents = sorted(entete for entete in _entetes_du_frontend() if entete not in autorises)
    assert not absents, (
        "En-tête(s) posés par le frontend mais absents de CORS_ALLOW_HEADERS : "
        + ", ".join(absents)
        + ". Le navigateur refusera ces appels au contrôle préalable, alors que "
        "tous les tests serveur continueront de passer."
    )
