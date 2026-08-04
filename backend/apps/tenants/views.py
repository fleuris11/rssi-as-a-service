from rest_framework import generics, permissions

from . import services
from .permissions import IsTenantMember
from .serializers import MembershipSerializer, TenantSerializer


class MyTenantListView(generics.ListAPIView):
    """Companies the authenticated user belongs to — no X-Tenant-Id needed,
    this is what lets the frontend build a tenant switcher before one is picked."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TenantSerializer

    def get_queryset(self):
        return [
            membership.tenant for membership in services.list_user_memberships(self.request.user)
        ]


class TenantMemberListView(generics.ListAPIView):
    """Members of the tenant selected via the X-Tenant-Id header."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    serializer_class = MembershipSerializer

    def get_queryset(self):
        return services.list_tenant_members(self.request.tenant)
