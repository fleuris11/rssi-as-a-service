from django.urls import path

from .views import DemoRequestAdminDetailView, DemoRequestAdminListView, DemoRequestCreateView

urlpatterns = [
    path("public/demo-requests/", DemoRequestCreateView.as_view(), name="demo-request-create"),
    path(
        "admin/demo-requests/",
        DemoRequestAdminListView.as_view(),
        name="demo-request-admin-list",
    ),
    path(
        "admin/demo-requests/<int:demo_request_id>/",
        DemoRequestAdminDetailView.as_view(),
        name="demo-request-admin-detail",
    ),
]
