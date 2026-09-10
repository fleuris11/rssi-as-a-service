from django.urls import path

from .views import (
    WatchQueueView,
    WatchSourceDetailView,
    WatchSourceListView,
    WatchSourcePollView,
    WatchUpdateIntegrateView,
    WatchUpdateReviewView,
    WatchUpdateSummaryView,
)

urlpatterns = [
    path("", WatchQueueView.as_view(), name="watch-queue"),
    path("sources/", WatchSourceListView.as_view(), name="watch-source-list"),
    path("sources/<slug:slug>/", WatchSourceDetailView.as_view(), name="watch-source-detail"),
    path("sources/<slug:slug>/poll/", WatchSourcePollView.as_view(), name="watch-source-poll"),
    path(
        "updates/<int:update_id>/review/",
        WatchUpdateReviewView.as_view(),
        name="watch-update-review",
    ),
    path(
        "updates/<int:update_id>/integrate/",
        WatchUpdateIntegrateView.as_view(),
        name="watch-update-integrate",
    ),
    path(
        "updates/<int:update_id>/summary/",
        WatchUpdateSummaryView.as_view(),
        name="watch-update-summary",
    ),
]
