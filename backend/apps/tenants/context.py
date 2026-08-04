"""Request-scoped storage for the tenant currently in context.

Uses ``contextvars`` (not thread-locals) so it stays correct under async
views and Django's async-capable request handling.
"""

import contextvars

_current_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_tenant_id", default=None
)


def get_current_tenant_id() -> str | None:
    return _current_tenant_id.get()


def set_current_tenant(tenant_id: str) -> contextvars.Token:
    return _current_tenant_id.set(tenant_id)


def reset_current_tenant(token: contextvars.Token) -> None:
    _current_tenant_id.reset(token)
