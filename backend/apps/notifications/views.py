from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.permissions import IsTenantMemberReadOnlyForReader

from . import services
from .serializers import NotificationPreferencesSerializer


class NotificationPreferencesView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def get(self, request):
        prefs = services.get_or_create_preferences(request.tenant)
        return Response(NotificationPreferencesSerializer(prefs).data)

    def patch(self, request):
        serializer = NotificationPreferencesSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        prefs = services.update_preferences(request.tenant, **serializer.validated_data)
        return Response(NotificationPreferencesSerializer(prefs).data)
