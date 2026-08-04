from rest_framework import serializers

from .models import Membership, Tenant


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug", "sector", "headcount", "is_active", "created_at"]
        read_only_fields = fields


class MembershipSummarySerializer(serializers.Serializer):
    """A user's role in one tenant — used to build the "my companies" list."""

    tenant_id = serializers.UUIDField(source="tenant.id")
    tenant_name = serializers.CharField(source="tenant.name")
    tenant_slug = serializers.CharField(source="tenant.slug")
    role = serializers.CharField()


class MembershipSerializer(serializers.ModelSerializer):
    """A tenant's member — used to build the team list within a tenant."""

    user_id = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user_id", "email", "first_name", "last_name", "role", "created_at"]
        read_only_fields = fields
