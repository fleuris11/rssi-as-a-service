import pytest


@pytest.fixture(autouse=True)
def _totp_encryption_key(settings):
    # Fixed, valid Fernet key so tests don't depend on TOTP_ENCRYPTION_KEY
    # being set in the environment.
    settings.TOTP_ENCRYPTION_KEY = "wdnStF9mSlY1ADOjw5Tc_M8-nLQw_ay8TUFePY6rNpo="
