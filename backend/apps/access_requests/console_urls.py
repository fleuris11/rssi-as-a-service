from django.urls import path

from .views import ConsoleAccessRequestDetailView, ConsoleAccessRequestListView

urlpatterns = [
    path("", ConsoleAccessRequestListView.as_view(), name="console-access-request-list"),
    path(
        "<int:request_id>/",
        ConsoleAccessRequestDetailView.as_view(),
        name="console-access-request-detail",
    ),
]
