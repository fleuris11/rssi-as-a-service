from django.contrib.auth import authenticate
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from . import services
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    TwoFactorConfirmSerializer,
    TwoFactorDisableSerializer,
    TwoFactorVerifySerializer,
    UserSerializer,
)
from .throttling import AuthRateThrottle

GENERIC_AUTH_ERROR = "Identifiants invalides."
LOCKOUT_ERROR = "Trop de tentatives. Réessayez plus tard."


def _client_ip(request) -> str:
    # Trusts X-Forwarded-For because the only path to this app in
    # production is behind Caddy (deploy/Caddyfile), which sets it — never
    # trust this header on a directly internet-facing Django process.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def _tokens_for_user(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Replaces simplejwt's stock TokenObtainPairView: same request shape
    and the same direct {access, refresh} response when 2FA is off (US-1.3
    backward compatibility), but adds the account+IP lockout check and a
    two-step challenge when the user has confirmed TOTP 2FA."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        ip = _client_ip(request)

        try:
            services.check_not_locked_out(email=email, ip=ip)
        except services.LockedOutError:
            return Response({"detail": LOCKOUT_ERROR}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        user = authenticate(request, email=email, password=password)
        if user is None or not user.is_active:
            services.record_failed_attempt(email=email, ip=ip)
            return Response({"detail": GENERIC_AUTH_ERROR}, status=status.HTTP_401_UNAUTHORIZED)

        services.clear_failed_attempts(email=email, ip=ip)

        if services.is_totp_enabled(user):
            challenge_token = services.create_mfa_challenge(user)
            return Response({"mfa_required": True, "challenge_token": challenge_token})

        return Response(_tokens_for_user(user))


class TwoFactorVerifyView(APIView):
    """Second step of login when 2FA is enabled: exchanges a short-lived
    challenge_token (from LoginView) + a TOTP code or recovery code for
    real tokens. Never authenticated by a JWT — the challenge_token IS the
    proof of the first factor already having passed."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = TwoFactorVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["challenge_token"]
        ip = _client_ip(request)

        user = services.resolve_mfa_challenge(token)
        if user is None:
            return Response(
                {"detail": "Session de connexion expirée, reconnectez-vous."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            services.check_not_locked_out(email=user.email, ip=ip)
        except services.LockedOutError:
            return Response({"detail": LOCKOUT_ERROR}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        code = serializer.validated_data.get("code")
        recovery_code = serializer.validated_data.get("recovery_code")
        credential = services.get_confirmed_credential(user)

        verified = bool(credential and code and services.verify_totp_code(credential, code))
        if not verified and recovery_code:
            verified = services.consume_recovery_code(user, recovery_code)

        if not verified:
            services.record_failed_attempt(email=user.email, ip=ip)
            return Response({"detail": "Code invalide."}, status=status.HTTP_401_UNAUTHORIZED)

        services.clear_failed_attempts(email=user.email, ip=ip)
        services.consume_mfa_challenge(token)
        return Response(_tokens_for_user(user))


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [AuthRateThrottle]


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class TwoFactorStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"enabled": services.is_totp_enabled(request.user)})


class TwoFactorSetupView(APIView):
    """Starts (or restarts) enrollment: generates a fresh secret, returns
    the QR code — 2FA is NOT active until TwoFactorConfirmView validates a
    code generated from it."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        _credential, secret = services.start_totp_enrollment(request.user)
        otpauth_uri = services.build_otpauth_uri(request.user, secret)
        qr_code = services.build_qr_code_data_uri(otpauth_uri)
        return Response({"secret": secret, "otpauth_uri": otpauth_uri, "qr_code": qr_code})


class TwoFactorConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TwoFactorConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            recovery_codes = services.confirm_totp_enrollment(
                request.user, serializer.validated_data["code"]
            )
        except services.AccountsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"recovery_codes": recovery_codes}, status=status.HTTP_201_CREATED)


class TwoFactorDisableView(APIView):
    """Requires the current password (not just an authenticated session) —
    disabling 2FA is a sensitive action a stolen access token alone
    shouldn't be able to perform."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TwoFactorDisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["password"]):
            return Response(
                {"detail": "Mot de passe incorrect."}, status=status.HTTP_400_BAD_REQUEST
            )
        services.disable_totp(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
