"""Smoke test for config/settings_production.py (Phase 5, cadrage §6): the
module isn't DJANGO_SETTINGS_MODULE during the test run (config.settings
is), so it's imported directly rather than exercised through Django."""

import importlib


def test_production_overlay_hardens_the_base_settings(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "rssiasservice.online,www.rssiasservice.online")

    module = importlib.import_module("config.settings_production")
    importlib.reload(module)

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


def test_missing_allowed_hosts_fails_loudly(monkeypatch):
    monkeypatch.delenv("DJANGO_ALLOWED_HOSTS", raising=False)

    module = importlib.import_module("config.settings_production")
    import environ

    try:
        importlib.reload(module)
    except environ.ImproperlyConfigured:
        return
    # django-environ's env.list() without a default raises ImproperlyConfigured
    # when the variable is unset — if it didn't, ALLOWED_HOSTS must not have
    # silently fallen back to something permissive.
    assert module.ALLOWED_HOSTS != ["localhost", "127.0.0.1"]
