from django.urls import path

from .views import AccessRequestDetailView, AccessRequestListView

urlpatterns = [
    path("", AccessRequestListView.as_view(), name="access-request-list"),
    path("<int:request_id>/", AccessRequestDetailView.as_view(), name="access-request-detail"),
]
