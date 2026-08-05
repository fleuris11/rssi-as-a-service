"""Per-IP throttling for the unauthenticated/pre-auth endpoints (register,
login, token refresh, 2FA verification) — cadrage §6: "rate limiting
(Redis) par IP". Deliberately per-IP, not per-account: at this point in the
flow we may not have a valid account yet (register, wrong email at login),
so per-user throttling is not available.

Separate from — and complementary to — the account+IP progressive lockout
in ``services.py``: this throttle caps raw request volume regardless of
whether credentials are valid (protects the auth infrastructure itself),
while the lockout specifically slows down credential-guessing against one
account.
"""

from rest_framework.throttling import SimpleRateThrottle


class AuthRateThrottle(SimpleRateThrottle):
    scope = "auth"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
