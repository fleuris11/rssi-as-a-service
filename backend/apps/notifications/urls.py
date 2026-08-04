from django.urls import path

from .views import NotificationPreferencesView

urlpatterns = [
    path("preferences/", NotificationPreferencesView.as_view(), name="notification-preferences"),
]
