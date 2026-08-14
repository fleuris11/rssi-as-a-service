from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView

from .views import (
    InvitationView,
    LoginView,
    MeView,
    RegisterView,
    ThrottledTokenRefreshView,
    TwoFactorConfirmView,
    TwoFactorDisableView,
    TwoFactorSetupView,
    TwoFactorStatusView,
    TwoFactorVerifyView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("token/", LoginView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", ThrottledTokenRefreshView.as_view(), name="token-refresh"),
    path("token/blacklist/", TokenBlacklistView.as_view(), name="token-blacklist"),
    path("token/verify-2fa/", TwoFactorVerifyView.as_view(), name="token-verify-2fa"),
    path("me/", MeView.as_view(), name="auth-me"),
    path(
        "invitation/<str:token>/",
        InvitationView.as_view(),
        name="auth-invitation",
    ),
    path("2fa/status/", TwoFactorStatusView.as_view(), name="2fa-status"),
    path("2fa/setup/", TwoFactorSetupView.as_view(), name="2fa-setup"),
    path("2fa/confirm/", TwoFactorConfirmView.as_view(), name="2fa-confirm"),
    path("2fa/disable/", TwoFactorDisableView.as_view(), name="2fa-disable"),
]
