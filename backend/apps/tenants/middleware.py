import uuid

from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, TokenError

from .context import reset_current_tenant, set_current_tenant
from .models import Membership

TENANT_HEADER = "HTTP_X_TENANT_ID"


class TenantScopingMiddleware:
    """Resolves the tenant for the current request and scopes queries to it.

    A request may declare which tenant it acts on via the ``X-Tenant-Id``
    header. When present, the header is checked against the requesting
    user's memberships (unscoped lookup — this is the one place allowed to
    bypass tenant scoping, since it's what resolves the tenant in the first
    place) and, on success, the tenant is exposed as ``request.tenant`` /
    ``request.membership`` and set in the context var that
    ``TenantScopedManager`` reads for the duration of the request.

    Requests without the header simply get no tenant context — views that
    require one enforce it via ``IsTenantMember`` and return 401/403, they
    don't get silently scoped to the wrong thing.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None
        request.membership = None
        token = None

        user = self._authenticate(request)
        tenant_id = request.META.get(TENANT_HEADER)

        if user is not None and tenant_id:
            membership = self._resolve_membership(user, tenant_id)
            if membership is None:
                return JsonResponse({"detail": "Aucun accès à cette entreprise."}, status=403)
            request.tenant = membership.tenant
            request.membership = membership
            token = set_current_tenant(str(membership.tenant_id))

        try:
            response = self.get_response(request)
        finally:
            if token is not None:
                reset_current_tenant(token)

        return response

    @staticmethod
    def _authenticate(request):
        try:
            result = JWTAuthentication().authenticate(request)
        except (TokenError, AuthenticationFailed):
            return None
        if result is None:
            return None
        user, _ = result
        return user

    @staticmethod
    def _resolve_membership(user, tenant_id):
        try:
            uuid.UUID(str(tenant_id))
        except ValueError:
            return None
        return (
            Membership.all_objects.select_related("tenant")
            .filter(tenant_id=tenant_id, user=user)
            .first()
        )
