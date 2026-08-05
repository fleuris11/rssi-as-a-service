from django.conf import settings


def test_django_security_and_request_loggers_are_configured():
    # Regression guard (A09 gap fix, see docs/security_review.md) — without
    # this, django.security events (lockouts, DisallowedHost) and server
    # errors go nowhere actionable in production.
    assert "django.security" in settings.LOGGING["loggers"]
    assert "django.request" in settings.LOGGING["loggers"]
    assert settings.LOGGING["loggers"]["django.security"]["handlers"] == ["console"]
