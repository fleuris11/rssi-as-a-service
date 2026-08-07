"""HTTP Basic auth check for the Breachsense webhook (ADR-013 §7). Not a
DRF/Django auth backend on purpose — these credentials don't map to a
Django user, they're a single shared secret configured on both sides
(``BREACHSENSE_WEBHOOK_USERNAME``/``PASSWORD`` here, ``/account?action=
add&creds=...`` on Breachsense's side)."""

import base64
import binascii
import hmac

from django.conf import settings
from django.http import HttpRequest


def is_valid_basic_auth(request: HttpRequest) -> bool:
    expected_username = settings.BREACHSENSE_WEBHOOK_USERNAME
    expected_password = settings.BREACHSENSE_WEBHOOK_PASSWORD
    if not expected_username or not expected_password:
        return False

    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Basic "):
        return False

    try:
        decoded = base64.b64decode(header[len("Basic ") :]).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False

    username, _, password = decoded.partition(":")
    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(
        password, expected_password
    )
