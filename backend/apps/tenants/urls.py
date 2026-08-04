from django.urls import path

from .views import MyTenantListView, TenantMemberListView

urlpatterns = [
    path("", MyTenantListView.as_view(), name="tenant-list"),
    path("members/", TenantMemberListView.as_view(), name="tenant-member-list"),
]
