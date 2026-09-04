"""Aucun message d'erreur, dans AUCUNE app, ne nomme l'intérieur du produit.

Ce test généralise une garde qui existait déjà pour la seule app
`threat_intelligence` — et qui n'a donc rien vu quand la même faute vivait
ailleurs. C'est la leçon de la session du 04/09/2026, apprise deux fois dans
la même journée :

    Auditer une CATÉGORIE de code (« les messages d'erreur du renseignement »)
    laisse passer la même faute partout ailleurs. Ce qu'il faut tenir, c'est
    une SURFACE : tout ce qu'un client peut lire.

Ce balayage a trouvé, après le premier correctif :
``TOTP_ENCRYPTION_KEY n'est pas configurée : impossible de chiffrer le secret
2FA.`` — remontée telle quelle au client par ``TwoFactorConfirmView``.

`platform_admin` est délibérément hors périmètre : ses vues sont réservées à
l'exploitant (`is_staff`), et le détail y est utile — c'est même à cela qu'il
sert. Le test ne dit donc pas « ce vocabulaire est interdit partout », il dit
« il est interdit là où un client peut le lire ».
"""

import pathlib
import re

# Apps dont les messages peuvent atteindre un client. `platform_admin` est
# exclue à dessein (back-office `is_staff`), et `config` n'expose rien.
APPS_CLIENT = (
    "accounts",
    "actions",
    "ai_assistant",
    "assessments",
    "billing",
    "monitoring",
    "notifications",
    "tenants",
    "threat_intelligence",
    "marketing",
)

# Fragments qui n'ont rien à faire sous les yeux d'un client. Volontairement
# large : mieux vaut refuser une formulation innocente que laisser passer un
# nom de fournisseur ou une variable d'environnement.
VOCABULAIRE_INTERNE = (
    "breachsense",
    "anthropic",
    "claude",
    "celery",
    "redis",
    "postgres",
    "weasyprint",
    "fernet",
    "traceback",
    "localhost",
    "api_key",
    "apikey",
    "_encryption_key",
    "_license_key",
    "django_",
    # Instructions d'exploitation. Ajoutées après une trouvaille que la
    # première version du balayage laissait passer : le diagnostic répondait
    # au client, en 503, « Aucun référentiel actif : lancez
    # `manage.py load_anssi_referential` ». On demandait à un dirigeant de PME
    # de lancer une commande Django sur un serveur auquel il n'a pas accès.
    "manage.py",
    "docker compose",
    "sudo ",
    "npm run",
    "python manage",
    "variable d'environnement",
)

# Deux formes atteignent un client : une exception métier (rendue par les vues
# en `detail`) et un `detail` écrit en dur.
MOTIFS = (
    re.compile(r'raise \w*Error\(\s*\n?\s*f?"([^"]{12,300})"'),
    re.compile(r'"detail":\s*\n?\s*f?"([^"]{12,300})"'),
)

RACINE = pathlib.Path(__file__).resolve().parents[2] / "apps"


def _messages_client() -> list[tuple[str, int, str]]:
    trouves = []
    for app in APPS_CLIENT:
        dossier = RACINE / app
        if not dossier.exists():
            continue
        for chemin in dossier.rglob("*.py"):
            # Les commandes d'administration sont des outils d'EXPLOITATION :
            # elles s'adressent à qui a un accès au serveur, et leur détail y
            # est utile — « BREACHSENSE_LICENSE_KEY absente » est exactement
            # ce qu'on veut y lire.
            if (
                "tests" in chemin.parts
                or "migrations" in chemin.parts
                or "commands" in chemin.parts
                # Couche fournisseur : ses exceptions ne sortent JAMAIS telles
                # quelles. `services` les traduit toutes en message client
                # (voir `except ProviderPoolFullError` / `ProviderNotConfigured`
                # dans threat_intelligence/services.py), et cette traduction
                # est elle-même testée par
                # threat_intelligence/tests/test_client_facing_messages.py.
                # Leur détail — « BREACHSENSE_LICENSE_KEY absente » — est ce
                # qu'un exploitant doit lire dans les journaux.
                or "providers" in chemin.parts
                or chemin.name == "throttle.py"
            ):
                continue
            texte = open(chemin, encoding="utf-8").read()
            for motif in MOTIFS:
                for m in motif.finditer(texte):
                    ligne = texte[: m.start()].count("\n") + 1
                    trouves.append((str(chemin.relative_to(RACINE)), ligne, m.group(1)))
    return trouves


class TestBalayageDesMessagesClient:
    def test_le_balayage_trouve_bien_des_messages(self):
        """Garde de la garde : si les expressions cessaient de correspondre
        (refactorisation, autre façon de lever), ce fichier passerait au vert
        en ne vérifiant plus rien."""
        messages = _messages_client()
        assert len(messages) > 20, (
            f"Seulement {len(messages)} message(s) trouvé(s) : les motifs de "
            "détection ne correspondent probablement plus au code."
        )

    def test_aucun_message_client_ne_nomme_l_interieur_du_produit(self):
        fautifs = []
        for fichier, ligne, message in _messages_client():
            bas = message.lower()
            for terme in VOCABULAIRE_INTERNE:
                if terme in bas:
                    fautifs.append(f"{fichier}:{ligne} [{terme}] {message[:110]}")
                    break

        assert not fautifs, (
            "Des messages destinés au client nomment l'intérieur du produit :\n  - "
            + "\n  - ".join(fautifs)
            + "\n\nJournalisez le détail (l'exploitant en a besoin), et laissez au "
            "client une phrase qui dit ce qui n'a pas marché, si c'est temporaire, "
            "et ce qu'il peut faire."
        )
