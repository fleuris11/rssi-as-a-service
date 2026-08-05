import pytest


@pytest.fixture(autouse=True)
def _ai_pseudonymization_key(settings):
    # Fixed, valid Fernet key so tests don't depend on AI_PSEUDONYMIZATION_KEY
    # being set in the environment — mirrors the production requirement
    # (services.store_mapping raises without one) while staying deterministic.
    settings.AI_PSEUDONYMIZATION_KEY = "wdnStF9mSlY1ADOjw5Tc_M8-nLQw_ay8TUFePY6rNpo="


@pytest.fixture
def other_tenant(user_factory, tenant_factory):
    owner = user_factory(email="other-tenant-owner@example.com")
    return tenant_factory(owner, name="Autre Entreprise")
