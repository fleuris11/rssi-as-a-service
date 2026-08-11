from django.urls import path

from .views import (
    BreachFindingDetailView,
    BreachFindingListView,
    BreachFindingRevealView,
    BreachScanJobDetailView,
    BreachScanTriggerView,
    ExposureFeedView,
    ExposureSynthesisRefreshView,
    MonitoredAssetDetailView,
    MonitoredAssetListCreateView,
    PreIncidentRadarView,
    SecretRevealAuditListView,
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
    path(
        "findings/<int:finding_id>/reveal/",
        BreachFindingRevealView.as_view(),
        name="breach-finding-reveal",
    ),
    path("exposure-feed/", ExposureFeedView.as_view(), name="breach-exposure-feed"),
    path(
        "exposure-feed/synthesis/",
        ExposureSynthesisRefreshView.as_view(),
        name="breach-exposure-synthesis-refresh",
    ),
    path("pre-incident/", PreIncidentRadarView.as_view(), name="breach-pre-incident"),
    path("audit/reveals/", SecretRevealAuditListView.as_view(), name="breach-reveal-audit-list"),
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
