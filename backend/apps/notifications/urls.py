from django.urls import path

from .views import (
    NotificationCountView,
    NotificationInboxView,
    NotificationPreferencesView,
    NotificationReadView,
)

urlpatterns = [
    path("preferences/", NotificationPreferencesView.as_view(), name="notification-preferences"),
    # Lot C, point 20 : le centre de notifications. « count/ » et « read/ »
    # avant tout motif plus général qui les capturerait.
    path("inbox/count/", NotificationCountView.as_view(), name="notification-inbox-count"),
    path("inbox/read/", NotificationReadView.as_view(), name="notification-inbox-read"),
    path("inbox/", NotificationInboxView.as_view(), name="notification-inbox"),
]
