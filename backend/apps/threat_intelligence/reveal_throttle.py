"""DRF request throttling for the privileged secret-reveal endpoint
(ADR-014, mise à jour) — distinct from ``throttle.py`` (the Redis token
bucket serializing *outbound* calls to Breachsense): this one caps *inbound*
reveal requests, per user and per IP, so that even a compromised admin
account (or a single IP hammering several admin accounts) can't mass-extract
secrets. Both throttles must independently allow the request — either one
tripping is enough to deny (registered together as ``throttle_classes`` on
the view, where DRF requires all of them to pass).
"""

from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class RevealUserRateThrottle(UserRateThrottle):
    scope = "breach_secret_reveal_user"


class RevealIPRateThrottle(SimpleRateThrottle):
    scope = "breach_secret_reveal_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
