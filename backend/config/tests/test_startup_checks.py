"""Garde-fou de configuration de production (Phase 8D).

Ce qui est protégé ici n'est pas une fonctionnalité mais une **posture** : la
séparation des clés Fernet (ADR-005/009/014) repose entièrement sur le fait
que trois variables d'environnement portent trois valeurs différentes. Rien,
au moment du déploiement, n'empêche de copier-coller la même clé dans les
trois — et l'application fonctionnerait parfaitement, en ayant silencieusement
annulé la garantie « compromettre l'une ne compromet pas les autres ».
"""

from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from config.startup_checks import collect_production_errors, validate_production_settings

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()
KEY_C = Fernet.generate_key().decode()


def _settings(**overrides):
    base = {
        "AI_PSEUDONYMIZATION_KEY": KEY_A,
        "TOTP_ENCRYPTION_KEY": KEY_B,
        "BREACH_SECRET_ENCRYPTION_KEY": KEY_C,
        "BREACH_SECRET_ENCRYPTION_KEYS": [],
        "DEBUG": False,
        "ALLOWED_HOSTS": ["rssiasservice.online"],
        "SECRET_KEY": "une-vraie-cle-secrete-generee-aleatoirement-xyz",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestValidConfiguration:
    def test_a_correct_production_configuration_passes(self):
        assert collect_production_errors(_settings()) == []

    def test_validate_does_not_raise_on_a_correct_configuration(self):
        validate_production_settings(_settings())  # ne doit pas lever


class TestMissingOrInvalidKeys:
    @pytest.mark.parametrize(
        "name",
        ["AI_PSEUDONYMIZATION_KEY", "TOTP_ENCRYPTION_KEY", "BREACH_SECRET_ENCRYPTION_KEY"],
    )
    def test_a_missing_key_is_reported(self, name):
        errors = collect_production_errors(_settings(**{name: ""}))
        assert any(name in error and "absente" in error for error in errors)

    @pytest.mark.parametrize(
        "name",
        ["AI_PSEUDONYMIZATION_KEY", "TOTP_ENCRYPTION_KEY", "BREACH_SECRET_ENCRYPTION_KEY"],
    )
    def test_a_malformed_key_is_reported(self, name):
        errors = collect_production_errors(_settings(**{name: "pas-une-cle-fernet"}))
        assert any(name in error and "Fernet" in error for error in errors)

    def test_startup_refuses_to_boot_on_a_missing_key(self):
        with pytest.raises(ImproperlyConfigured, match="TOTP_ENCRYPTION_KEY"):
            validate_production_settings(_settings(TOTP_ENCRYPTION_KEY=""))


class TestKeyReuse:
    """Le défaut le plus facile à introduire au déploiement, et le plus
    coûteux : la même clé copiée dans plusieurs variables."""

    def test_the_same_key_used_twice_is_rejected(self):
        errors = collect_production_errors(_settings(TOTP_ENCRYPTION_KEY=KEY_A))
        assert any("réutilise la même clé" in error for error in errors)

    def test_the_same_key_used_everywhere_is_rejected(self):
        errors = collect_production_errors(
            _settings(
                AI_PSEUDONYMIZATION_KEY=KEY_A,
                TOTP_ENCRYPTION_KEY=KEY_A,
                BREACH_SECRET_ENCRYPTION_KEY=KEY_A,
            )
        )
        assert len([e for e in errors if "réutilise la même clé" in e]) == 2

    def test_startup_refuses_to_boot_on_key_reuse(self):
        with pytest.raises(ImproperlyConfigured, match="réutilise"):
            validate_production_settings(_settings(BREACH_SECRET_ENCRYPTION_KEY=KEY_A))

    def test_rotation_list_is_validated_on_its_current_key(self):
        """En rotation (ADR-014 §5), c'est la première clé de la liste qui
        chiffre : c'est elle qui doit être distincte des autres usages."""
        errors = collect_production_errors(
            _settings(BREACH_SECRET_ENCRYPTION_KEY="", BREACH_SECRET_ENCRYPTION_KEYS=[KEY_C, KEY_A])
        )
        assert errors == []

    def test_rotation_list_reusing_another_purpose_key_is_rejected(self):
        errors = collect_production_errors(
            _settings(BREACH_SECRET_ENCRYPTION_KEY="", BREACH_SECRET_ENCRYPTION_KEYS=[KEY_A])
        )
        assert any("réutilise la même clé" in error for error in errors)


class TestDevelopmentLeftovers:
    def test_debug_enabled_is_rejected(self):
        errors = collect_production_errors(_settings(DEBUG=True))
        assert any("DEBUG" in error for error in errors)

    def test_empty_allowed_hosts_is_rejected(self):
        errors = collect_production_errors(_settings(ALLOWED_HOSTS=[]))
        assert any("ALLOWED_HOSTS" in error for error in errors)

    def test_wildcard_allowed_hosts_is_rejected(self):
        errors = collect_production_errors(_settings(ALLOWED_HOSTS=["*"]))
        assert any("*" in error for error in errors)

    def test_placeholder_secret_key_is_rejected(self):
        errors = collect_production_errors(
            _settings(SECRET_KEY="change-me-to-a-random-value")
        )
        assert any("SECRET_KEY" in error for error in errors)


class TestErrorReporting:
    def test_every_problem_is_reported_at_once(self):
        """Un déploiement mal configuré doit pouvoir être corrigé en une
        passe, pas en découvrant les erreurs une par une à chaque redémarrage."""
        errors = collect_production_errors(
            _settings(DEBUG=True, ALLOWED_HOSTS=[], TOTP_ENCRYPTION_KEY="")
        )
        assert len(errors) >= 3

    def test_the_exception_message_lists_the_problems(self):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            validate_production_settings(_settings(DEBUG=True, ALLOWED_HOSTS=[]))
        message = str(exc_info.value)
        assert "DEBUG" in message
        assert "ALLOWED_HOSTS" in message
