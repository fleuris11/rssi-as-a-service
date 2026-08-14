from django.urls import path

from .console_views import (
    ClientActionView,
    ClientArchiveView,
    ClientCreateView,
    ClientDetailView,
    ClientMemberDetailView,
    ClientMemberListView,
    ClientMonitoredAssetView,
    ExportView,
    FollowUpBoardView,
    GlobalSearchView,
    MemberPasswordResetView,
    PlanDeleteView,
    PlanDuplicateView,
    PlanImpactView,
    PlanPreviewView,
    PlatformAdminDetailView,
    PlatformAdminListView,
    PlatformSettingResetView,
    PlatformSettingsView,
    ProspectDetailView,
    ProspectListView,
    ProspectNoteView,
    SubscriptionDetailView,
    TrashView,
)
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
    # --- Ressources rares ---------------------------------------------------
    path("capacity/", PlatformCapacityView.as_view(), name="platform-capacity"),
    # --- Clients ------------------------------------------------------------
    path("tenants/", AdminTenantListView.as_view(), name="platform-tenant-list"),
    path("clients/", ClientCreateView.as_view(), name="platform-client-create"),
    path(
        "tenants/<uuid:tenant_id>/", AdminTenantDetailView.as_view(), name="platform-tenant-detail"
    ),
    path(
        "clients/<uuid:tenant_id>/",
        ClientDetailView.as_view(),
        name="platform-client-detail",
    ),
    path(
        "clients/<uuid:tenant_id>/archive/",
        ClientArchiveView.as_view(),
        name="platform-client-archive",
    ),
    path(
        "clients/<uuid:tenant_id>/members/",
        ClientMemberListView.as_view(),
        name="platform-client-members",
    ),
    path(
        "clients/<uuid:tenant_id>/members/<int:membership_id>/",
        ClientMemberDetailView.as_view(),
        name="platform-client-member-detail",
    ),
    path(
        "clients/<uuid:tenant_id>/members/<int:membership_id>/reset-password/",
        MemberPasswordResetView.as_view(),
        name="platform-client-member-reset",
    ),
    path(
        "clients/<uuid:tenant_id>/subscription/",
        SubscriptionDetailView.as_view(),
        name="platform-client-subscription",
    ),
    path(
        "clients/<uuid:tenant_id>/monitored-assets/",
        ClientMonitoredAssetView.as_view(),
        name="platform-client-monitored-assets",
    ),
    path(
        "clients/<uuid:tenant_id>/actions/",
        ClientActionView.as_view(),
        name="platform-client-actions",
    ),
    path(
        "tenants/<uuid:tenant_id>/subscription/",
        AdminSubscriptionActionView.as_view(),
        name="platform-subscription-action",
    ),
    path("trash/", TrashView.as_view(), name="platform-trash"),
    # --- Catalogue ----------------------------------------------------------
    path("plans/", AdminPlanListView.as_view(), name="platform-plan-list"),
    # Les chemins spécifiques passent AVANT le détail : sans cela,
    # ``<slug:plan_code>`` capturerait « impact » comme un code d'offre.
    path("plans/<slug:plan_code>/delete/", PlanDeleteView.as_view(), name="platform-plan-delete"),
    path(
        "plans/<slug:plan_code>/duplicate/",
        PlanDuplicateView.as_view(),
        name="platform-plan-duplicate",
    ),
    path("plans/<slug:plan_code>/impact/", PlanImpactView.as_view(), name="platform-plan-impact"),
    path(
        "plans/<slug:plan_code>/preview/", PlanPreviewView.as_view(), name="platform-plan-preview"
    ),
    path("plans/<slug:plan_code>/", AdminPlanDetailView.as_view(), name="platform-plan-detail"),
    # --- Prospects ----------------------------------------------------------
    path("prospects/", ProspectListView.as_view(), name="platform-prospect-list"),
    path("prospects/follow-up/", FollowUpBoardView.as_view(), name="platform-prospect-follow-up"),
    path(
        "prospects/<int:prospect_id>/",
        ProspectDetailView.as_view(),
        name="platform-prospect-detail",
    ),
    path(
        "prospects/<int:prospect_id>/notes/",
        ProspectNoteView.as_view(),
        name="platform-prospect-note",
    ),
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
    # --- Plateforme ---------------------------------------------------------
    path("admins/", PlatformAdminListView.as_view(), name="platform-admin-list"),
    path(
        "admins/<uuid:user_id>/", PlatformAdminDetailView.as_view(), name="platform-admin-detail"
    ),
    path("settings/", PlatformSettingsView.as_view(), name="platform-settings"),
    path(
        "settings/<str:key>/reset/",
        PlatformSettingResetView.as_view(),
        name="platform-setting-reset",
    ),
    path("search/", GlobalSearchView.as_view(), name="platform-search"),
    path("export/<str:kind>/", ExportView.as_view(), name="platform-export"),
    path("health/", PlatformHealthView.as_view(), name="platform-health"),
    path("configuration/", PlatformConfigurationView.as_view(), name="platform-configuration"),
    path("audit/", AdminAuditView.as_view(), name="platform-audit"),
    path("audit/admin-actions/", AdminAuditRawView.as_view(), name="platform-audit-admin"),
]
