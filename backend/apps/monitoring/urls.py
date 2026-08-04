from django.urls import path

from .views import (
    AssetCheckHistoryView,
    AssetDetailView,
    AssetListCreateView,
    DashboardView,
    OpenAlertListView,
)

urlpatterns = [
    path("assets/", AssetListCreateView.as_view(), name="asset-list"),
    path("assets/<int:asset_id>/", AssetDetailView.as_view(), name="asset-detail"),
    path(
        "assets/<int:asset_id>/checks/",
        AssetCheckHistoryView.as_view(),
        name="asset-check-history",
    ),
    path("dashboard/", DashboardView.as_view(), name="monitoring-dashboard"),
    path("alerts/", OpenAlertListView.as_view(), name="monitoring-open-alerts"),
]
