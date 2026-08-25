"""Surcouche de production (`config/settings_production.py`, Phase 5, cadrage §6).

Ce module n'est pas `DJANGO_SETTINGS_MODULE` pendant la suite de tests
(`config.settings` l'est) : on l'importe donc directement, en lui fournissant
son environnement à la main.

**Fournir cet environnement n'est pas une formalité.** La surcouche lit des
variables SANS valeur par défaut, à dessein : une production mal configurée
doit refuser de démarrer plutôt que retomber sur un réglage permissif. Un test
qui hérite silencieusement d'un `backend/.env` local passe sur le poste du
développeur et échoue en intégration continue — c'est précisément ce qui s'est
produit ici, et pour la même raison que la clé 2FA (voir `backend/conftest.py`).
La précondition est donc **déclarée**, jamais empruntée à l'ambiance.

Les clés Fernet ne se posent pas par variable d'environnement : `settings.py`
les a déjà lues au démarrage de la suite, et `from .settings import *` recopie
ces valeurs-là. On surcharge donc le module de base.
"""

import importlib
import sys

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from config import settings as base

DOMAINES = "rssiasservice.online,www.rssiasservice.online"

# Variables lues par la surcouche elle-même, à l'import.
ENVIRONNEMENT = {
    "DJANGO_ALLOWED_HOSTS": DOMAINES,
    # "replay" et non "live" : aucun test ne doit pouvoir consommer du quota
    # Breachsense réel (ADR-015). Ce qui est vérifié ici est que la variable
    # est *exigée*, pas la valeur qu'elle porte.
    "BREACHSENSE_MODE": "replay",
}

# Trois clés distinctes : le garde-fou de démarrage refuse la réutilisation
# d'une clé d'un usage à l'autre (ADR-005/009/014).
CLES_FERNET = {
    "AI_PSEUDONYMIZATION_KEY": Fernet.generate_key().decode(),
    "TOTP_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "BREACH_SECRET_ENCRYPTION_KEY": Fernet.generate_key().decode(),
}


def _charger(monkeypatch, cles=None, **surcharges):
    """(Re)charge la surcouche depuis un état propre.

    `importlib.reload` ne convient pas : quand l'exécution d'un module échoue,
    Python le retire de `sys.modules`. Le test suivant, qui croyait recharger
    un module en cache, le réimportait en réalité — et son exception, levée à
    l'import et non au rechargement, échappait au bloc censé la capturer. Le
    résultat dépendait donc de l'ORDRE des tests, et le test « échoue
    bruyamment » ne prouvait rien dès que son voisin échouait avant lui.

    Une surcharge à `None` supprime la variable : c'est ainsi qu'on vérifie
    qu'une variable manquante est refusée.
    """
    for nom, valeur in {**ENVIRONNEMENT, **surcharges}.items():
        if valeur is None:
            monkeypatch.delenv(nom, raising=False)
        else:
            monkeypatch.setenv(nom, valeur)

    for nom, valeur in {**CLES_FERNET, **(cles or {})}.items():
        monkeypatch.setattr(base, nom, valeur)
    monkeypatch.setattr(base, "BREACH_SECRET_ENCRYPTION_KEYS", [])

    sys.modules.pop("config.settings_production", None)
    return importlib.import_module("config.settings_production")


def test_production_overlay_hardens_the_base_settings(monkeypatch):
    module = _charger(monkeypatch)

    assert module.DEBUG is False
    assert module.ALLOWED_HOSTS == ["rssiasservice.online", "www.rssiasservice.online"]
    assert module.SESSION_COOKIE_SECURE is True
    assert module.CSRF_COOKIE_SECURE is True
    assert module.SESSION_COOKIE_HTTPONLY is True
    assert module.SECURE_SSL_REDIRECT is True
    assert module.SECURE_HSTS_SECONDS > 0
    assert module.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert module.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert module.X_FRAME_OPTIONS == "DENY"
    assert module.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert module.CORS_ALLOW_ALL_ORIGINS is False
    assert module.BREACHSENSE_MODE == "replay"


def test_missing_allowed_hosts_fails_loudly(monkeypatch):
    # Sans domaines déclarés, Django accepte n'importe quel en-tête Host :
    # retomber sur localhost serait le pire des comportements, puisque le
    # déploiement aurait l'air d'avoir réussi.
    with pytest.raises(ImproperlyConfigured):
        _charger(monkeypatch, DJANGO_ALLOWED_HOSTS=None)


def test_missing_cti_mode_fails_loudly(monkeypatch):
    # La surcouche affirme dans son propre commentaire qu'« un .env incomplet
    # ne doit pas basculer silencieusement en live ». Rien ne le vérifiait :
    # le test passait sur les postes où la variable traînait dans
    # l'environnement, c'est-à-dire partout sauf en intégration continue.
    with pytest.raises(ImproperlyConfigured):
        _charger(monkeypatch, BREACHSENSE_MODE=None)


def test_a_reused_fernet_key_blocks_startup(monkeypatch):
    # Le garde-fou est testé unitairement (test_startup_checks.py) ; ce qui est
    # vérifié ici est qu'il est bien BRANCHÉ à l'import de la surcouche — donc
    # avant que Gunicorn ne serve la moindre requête.
    partagee = Fernet.generate_key().decode()

    with pytest.raises(ImproperlyConfigured, match="réutilise la même clé"):
        _charger(
            monkeypatch,
            cles={"AI_PSEUDONYMIZATION_KEY": partagee, "TOTP_ENCRYPTION_KEY": partagee},
        )
