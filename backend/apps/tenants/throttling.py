"""Per-tenant throttling (cadrage §6: "rate limiting (Redis) ... par
tenant"). Keyed on ``request.tenant`` (set by ``TenantScopingMiddleware``)
rather than on the user or the IP: several members of the same tenant
sharing a budget is the behaviour that matches how tenants actually use the
API (and how AI token quotas are tracked — ``apps.ai_assistant.models.
AIUsageQuota`` is per tenant, not per user).

Both classes silently skip throttling when no tenant is resolved
(``get_cache_key`` returns ``None``, which ``SimpleRateThrottle`` treats as
"don't throttle") — safe to register globally, since pre-tenant-resolution
requests (register, login, the tenant list itself) are covered instead by
``apps.accounts.throttling.AuthRateThrottle`` or simply don't need it.
"""

from rest_framework.throttling import SimpleRateThrottle


class TenantRateThrottle(SimpleRateThrottle):
    """Default throttle for the general tenant-scoped API — generous, it
    exists to catch runaway clients/bugs, not to constrain normal usage."""

    scope = "tenant"

    def get_cache_key(self, request, view):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": tenant.id}


class TenantAIRateThrottle(TenantRateThrottle):
    """Stricter throttle for the AI job-creation endpoints (document
    generation, assistant messages) — deliberately loose relative to
    ``AIUsageQuota`` (cadrage: "aligné sur les quotas"): the monthly token
    quota is the real ceiling on volume (apps.ai_assistant.services.
    ensure_quota_available), this throttle only guards against a client
    bursting requests faster than a human (or the 30-60s job itself) could
    plausibly produce."""

    scope = "tenant_ai"
