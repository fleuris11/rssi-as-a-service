from django.conf import settings


def test_x_tenant_id_is_an_allowed_cors_header():
    # Regression guard (found via Playwright E2E, not by any Django-test-
    # client-based test — see config/settings.py:CORS_ALLOW_HEADERS): without
    # this, the browser blocks every tenant-scoped request client-side after
    # a CORS preflight, with zero server-side trace.
    assert "x-tenant-id" in settings.CORS_ALLOW_HEADERS
