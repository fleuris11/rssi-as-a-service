from django.urls import path

from .views import (
    AdminAuditRawView,
    AdminAuditView,
    AdminDemoRequestConvertView,
    AdminDemoRequestListView,
    AdminPlanDetailView,
    AdminPlanListView,
    AdminSubscriptionActionView,
    AdminTenantDetailView,
    AdminTenantListView,
    PlatformCapacityView,
    PlatformConfigurationView,
    PlatformHealthView,
)

urlpatterns = [
    path("capacity/", PlatformCapacityView.as_view(), name="platform-capacity"),
    path("tenants/", AdminTenantListView.as_view(), name="platform-tenant-list"),
    path(
        "tenants/<uuid:tenant_id>/", AdminTenantDetailView.as_view(), name="platform-tenant-detail"
    ),
    path(
        "tenants/<uuid:tenant_id>/subscription/",
        AdminSubscriptionActionView.as_view(),
        name="platform-subscription-action",
    ),
    path("plans/", AdminPlanListView.as_view(), name="platform-plan-list"),
    path("plans/<slug:plan_code>/", AdminPlanDetailView.as_view(), name="platform-plan-detail"),
    path("demo-requests/", AdminDemoRequestListView.as_view(), name="platform-demo-request-list"),
    path(
        "demo-requests/<int:demo_request_id>/",
        AdminDemoRequestListView.as_view(),
        name="platform-demo-request-detail",
    ),
    path(
        "demo-requests/<int:demo_request_id>/convert/",
        AdminDemoRequestConvertView.as_view(),
        name="platform-demo-request-convert",
    ),
    path("health/", PlatformHealthView.as_view(), name="platform-health"),
    path("configuration/", PlatformConfigurationView.as_view(), name="platform-configuration"),
    path("audit/", AdminAuditView.as_view(), name="platform-audit"),
    path("audit/admin-actions/", AdminAuditRawView.as_view(), name="platform-audit-admin"),
]
