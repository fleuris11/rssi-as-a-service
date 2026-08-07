from django.urls import path

from .views import (
    BreachFindingDetailView,
    BreachFindingListView,
    BreachScanJobDetailView,
    BreachScanTriggerView,
    MonitoredAssetDetailView,
    MonitoredAssetListCreateView,
    ThreatIntelligenceAdminStatusView,
    ThreatIntelligenceStatusView,
)

urlpatterns = [
    path("findings/", BreachFindingListView.as_view(), name="breach-finding-list"),
    path(
        "findings/<int:finding_id>/",
        BreachFindingDetailView.as_view(),
        name="breach-finding-detail",
    ),
    path("monitored-assets/", MonitoredAssetListCreateView.as_view(), name="monitored-asset-list"),
    path(
        "monitored-assets/<int:asset_id>/",
        MonitoredAssetDetailView.as_view(),
        name="monitored-asset-detail",
    ),
    path("scans/", BreachScanTriggerView.as_view(), name="breach-scan-trigger"),
    path("scans/<int:job_id>/", BreachScanJobDetailView.as_view(), name="breach-scan-job-detail"),
    path("status/", ThreatIntelligenceStatusView.as_view(), name="threat-intelligence-status"),
    path(
        "admin/status/",
        ThreatIntelligenceAdminStatusView.as_view(),
        name="threat-intelligence-admin-status",
    ),
]
