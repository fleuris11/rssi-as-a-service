import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.tenants.services import create_tenant_with_owner

User = get_user_model()


@pytest.fixture(autouse=True)
def _fast_password_hashing(settings):
    # PBKDF2 (the production default) is deliberately slow; tests create
    # many users and don't need that cost.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _clear_cache():
    # DRF throttling (apps.accounts/apps.tenants throttling.py) and the
    # account+IP lockout (apps.accounts.services) both key off the shared
    # Django cache (Redis) — without this, one test's failed-login or
    # throttle counters would bleed into the next (every test client shares
    # the same "127.0.0.1" remote address).
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory(db):
    def make(**kwargs):
        kwargs.setdefault("email", f"user-{User.objects.count()}@example.com")
        password = kwargs.pop("password", "Str0ng!Passw0rd123")
        return User.objects.create_user(password=password, **kwargs)

    return make


@pytest.fixture
def tenant_factory(db):
    def make(owner, name="Entreprise Test", **kwargs):
        return create_tenant_with_owner(name=name, owner=owner, **kwargs)

    return make
