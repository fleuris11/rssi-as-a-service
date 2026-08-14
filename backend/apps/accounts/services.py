"""Public interface of the accounts app for authentication hardening
(cadrage §6, US-1.3): progressive account+IP lockout (Redis-backed via
Django's cache) and TOTP two-factor authentication (enrollment,
verification, recovery codes, MFA login challenge).

Like apps.monitoring/apps.ai_assistant, this module is deliberately the
only place that touches ``TwoFactorCredential``/``RecoveryCode`` directly —
views and other apps go through these functions.
"""

import base64
import hashlib
import io
import logging
import secrets
from datetime import timedelta

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.utils import timezone

from .models import RecoveryCode, TwoFactorCredential

# Same channel Django's own SuspiciousOperation handling uses (A09 — see
# docs/security_review.md) — a real LOGGING config (config/settings.py) makes
# this actionable rather than a console line nobody watches.
security_logger = logging.getLogger("django.security")


class AccountsError(Exception):
    """Base class for business-rule violations raised by this module."""


class LockedOutError(AccountsError):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = max(1, retry_after_seconds)
        super().__init__("Trop de tentatives. Réessayez plus tard.")


# --- Verrouillage progressif compte + IP (cadrage §6) -----------------------
#
# Deux compteurs indépendants (par compte, par IP) : un attaquant qui change
# d'IP reste bloqué par le compteur du compte visé ; un attaquant qui teste
# de nombreux comptes depuis une même IP reste bloqué par le compteur IP.
# (seuil d'échecs, durée de verrouillage en secondes) — la durée augmente
# avec le nombre d'échecs (verrouillage "progressif").
_LOCKOUT_LADDER = [(5, 60), (10, 5 * 60), (15, 15 * 60), (20, 60 * 60)]
_ATTEMPT_WINDOW_SECONDS = 15 * 60


def _hashed_ident(ident: str) -> str:
    # Ni l'email ni l'IP ne doivent apparaître en clair dans les clés Redis.
    return hashlib.sha256(ident.strip().lower().encode()).hexdigest()


def _failure_key(kind: str, ident: str) -> str:
    return f"login_fail:{kind}:{_hashed_ident(ident)}"


def _lock_key(kind: str, ident: str) -> str:
    return f"login_lock:{kind}:{_hashed_ident(ident)}"


def _lockout_seconds_for(failures: int) -> int | None:
    duration = None
    for threshold, seconds in _LOCKOUT_LADDER:
        if failures >= threshold:
            duration = seconds
    return duration


def check_not_locked_out(*, email: str, ip: str) -> None:
    """Raises LockedOutError if either the account or the IP is currently
    locked out. Checked BEFORE authenticate() so a locked-out account never
    even reaches password comparison."""
    for kind, ident in (("account", email), ("ip", ip)):
        if not ident:
            continue
        locked_until = cache.get(_lock_key(kind, ident))
        if locked_until:
            remaining = locked_until - timezone.now().timestamp()
            if remaining > 0:
                raise LockedOutError(int(remaining))


def record_failed_attempt(*, email: str, ip: str) -> None:
    for kind, ident in (("account", email), ("ip", ip)):
        if not ident:
            continue
        key = _failure_key(kind, ident)
        try:
            failures = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=_ATTEMPT_WINDOW_SECONDS)
            failures = 1
        lockout_seconds = _lockout_seconds_for(failures)
        if lockout_seconds:
            cache.set(
                _lock_key(kind, ident),
                timezone.now().timestamp() + lockout_seconds,
                timeout=lockout_seconds,
            )
            # Hashed identifier only (never the raw email/IP, same rule as
            # the cache keys above) — actionable signal without logging PII.
            security_logger.warning(
                "Verrouillage progressif déclenché (%s, %d échecs, %ds) : %s",
                kind,
                failures,
                lockout_seconds,
                _hashed_ident(ident)[:12],
            )


def clear_failed_attempts(*, email: str, ip: str) -> None:
    for kind, ident in (("account", email), ("ip", ip)):
        if not ident:
            continue
        cache.delete(_failure_key(kind, ident))
        cache.delete(_lock_key(kind, ident))


# --- Chiffrement du secret TOTP (cadrage §6) --------------------------------


def _fernet() -> Fernet:
    key = settings.TOTP_ENCRYPTION_KEY
    if not key:
        raise AccountsError(
            "TOTP_ENCRYPTION_KEY n'est pas configurée : impossible de chiffrer le secret 2FA."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def _encrypt_secret(secret: str) -> bytes:
    return _fernet().encrypt(secret.encode())


def _decrypt_secret(encrypted: bytes) -> str:
    try:
        return _fernet().decrypt(bytes(encrypted)).decode()
    except InvalidToken as exc:
        raise AccountsError("Secret 2FA illisible.") from exc


# --- Enrôlement 2FA (US-1.3) -------------------------------------------------


def start_totp_enrollment(user) -> tuple[TwoFactorCredential, str]:
    """Generates a fresh secret and stores it unconfirmed, replacing any
    previous unconfirmed attempt. Returns (credential, plaintext_secret) —
    the plaintext secret is only ever held in memory for building the QR
    code/otpauth URI, never persisted."""
    secret = pyotp.random_base32()
    credential, _created = TwoFactorCredential.objects.update_or_create(
        user=user,
        defaults={
            "encrypted_secret": _encrypt_secret(secret),
            "confirmed": False,
            "confirmed_at": None,
        },
    )
    return credential, secret


def build_otpauth_uri(user, secret: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="RSSI as a Service")


def build_qr_code_data_uri(otpauth_uri: str) -> str:
    image = qrcode.make(otpauth_uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def verify_totp_code(credential: TwoFactorCredential, code: str) -> bool:
    if not code:
        return False
    secret = _decrypt_secret(credential.encrypted_secret)
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def confirm_totp_enrollment(user, code: str) -> list[str]:
    try:
        credential = TwoFactorCredential.objects.get(user=user, confirmed=False)
    except TwoFactorCredential.DoesNotExist as exc:
        raise AccountsError("Aucun enrôlement 2FA en attente de confirmation.") from exc
    if not verify_totp_code(credential, code):
        raise AccountsError("Code invalide.")
    credential.confirmed = True
    credential.confirmed_at = timezone.now()
    credential.save(update_fields=["confirmed", "confirmed_at"])
    return generate_recovery_codes(user)


def disable_totp(user) -> None:
    TwoFactorCredential.objects.filter(user=user).delete()
    RecoveryCode.objects.filter(user=user).delete()


def is_totp_enabled(user) -> bool:
    return TwoFactorCredential.objects.filter(user=user, confirmed=True).exists()


def get_confirmed_credential(user) -> TwoFactorCredential | None:
    return TwoFactorCredential.objects.filter(user=user, confirmed=True).first()


# --- Codes de récupération (US-1.3) -----------------------------------------


def generate_recovery_codes(user, count: int = 10) -> list[str]:
    """Replaces any existing recovery codes — issued once, shown once (the
    view returns the plaintext list exactly once, at confirmation time)."""
    RecoveryCode.objects.filter(user=user).delete()
    plaintext_codes = []
    rows = []
    for _ in range(count):
        code = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
        plaintext_codes.append(code)
        rows.append(RecoveryCode(user=user, code_hash=make_password(code)))
    RecoveryCode.objects.bulk_create(rows)
    return plaintext_codes


def consume_recovery_code(user, code: str) -> bool:
    if not code:
        return False
    for recovery_code in RecoveryCode.objects.filter(user=user, used_at__isnull=True):
        if check_password(code, recovery_code.code_hash):
            recovery_code.used_at = timezone.now()
            recovery_code.save(update_fields=["used_at"])
            return True
    return False


# --- Challenge MFA à la connexion (US-1.3) ----------------------------------
#
# Un jeton opaque à durée de vie courte, stocké côté serveur (Redis) —
# jamais un JWT : ça évite tout risque qu'un jeton "en attente de 2FA" soit
# confondu avec un access token valide par erreur d'implémentation côté
# client ou serveur.

_MFA_CHALLENGE_TTL_SECONDS = 5 * 60


def create_mfa_challenge(user) -> str:
    token = secrets.token_urlsafe(32)
    cache.set(f"mfa_challenge:{token}", str(user.pk), timeout=_MFA_CHALLENGE_TTL_SECONDS)
    return token


def resolve_mfa_challenge(token: str):
    user_id = cache.get(f"mfa_challenge:{token}")
    if not user_id:
        return None
    return get_user_model().objects.filter(id=user_id).first()


def consume_mfa_challenge(token: str) -> None:
    cache.delete(f"mfa_challenge:{token}")


# --- Invitations et réinitialisations par lien (phase 11) -------------------
#
# Règle non négociable : un administrateur n'affiche, ne saisit ni ne transmet
# jamais le mot de passe d'un tiers. Il émet un lien à durée limitée ; la
# personne destinataire est la seule à choisir son mot de passe.
#
# Le jeton est stocké HACHÉ (même traitement qu'un mot de passe) : la valeur en
# clair n'existe que dans la réponse HTTP qui suit sa création. Une fuite de la
# table ne permet donc pas de prendre la main sur un compte.

INVITATION_TTL_HOURS = 72
RESET_TTL_HOURS = 2


class InvitationError(AccountsError):
    """Lien d'invitation invalide, expiré ou déjà utilisé."""


def _hash_token(raw: str) -> str:
    # SHA-256 et non un hacheur de mot de passe : le jeton fait 256 bits
    # d'entropie aléatoire, il n'est pas devinable par force brute — le coût
    # d'un hacheur lent n'apporterait rien et ralentirait chaque vérification.
    return hashlib.sha256(raw.encode()).hexdigest()


def create_access_invitation(*, user, purpose, actor=None, ttl_hours=None) -> tuple[object, str]:
    """Émet un lien. Renvoie (invitation, jeton en clair).

    Les liens antérieurs du même usage sont invalidés : sinon, révoquer l'accès
    d'un salarié parti n'aurait aucun effet tant qu'un ancien lien traîne dans
    sa boîte mail.
    """
    from .models import AccessInvitation

    AccessInvitation.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(
        used_at=timezone.now()
    )

    if ttl_hours is None:
        ttl_hours = (
            INVITATION_TTL_HOURS
            if purpose == AccessInvitation.Purpose.INVITATION
            else RESET_TTL_HOURS
        )

    raw_token = secrets.token_urlsafe(32)
    invitation = AccessInvitation.objects.create(
        user=user,
        purpose=purpose,
        token_hash=_hash_token(raw_token),
        expires_at=timezone.now() + timedelta(hours=ttl_hours),
        created_by=actor,
    )
    return invitation, raw_token


def resolve_access_invitation(raw_token: str):
    """Invitation utilisable correspondant au jeton, ou None.

    Ne distingue pas « inconnu » de « expiré » dans son retour : c'est
    l'appelant qui décide du message, et l'appelant (vue publique) doit donner
    le même dans les deux cas.
    """
    from .models import AccessInvitation

    invitation = (
        AccessInvitation.objects.filter(token_hash=_hash_token(raw_token))
        .select_related("user")
        .first()
    )
    if invitation is None or not invitation.is_usable:
        return None
    return invitation


def accept_access_invitation(*, raw_token: str, new_password: str):
    """Consomme le lien et fixe le mot de passe. Renvoie l'utilisateur."""
    invitation = resolve_access_invitation(raw_token)
    if invitation is None:
        raise InvitationError(
            "Ce lien n'est plus valable. Demandez-en un nouveau à votre administrateur."
        )

    user = invitation.user
    user.set_password(new_password)
    # Un compte invité n'est actif qu'une fois son mot de passe défini : tant
    # que le lien n'est pas utilisé, l'identité existe mais ne peut pas servir.
    user.is_active = True
    user.save(update_fields=["password", "is_active"])

    invitation.used_at = timezone.now()
    invitation.save(update_fields=["used_at"])

    # Le mot de passe vient de changer : on efface les compteurs d'échec, sinon
    # un utilisateur qui vient de le réinitialiser resterait verrouillé.
    clear_failed_attempts(email=user.email, ip="")
    return user


def invitation_url(raw_token: str) -> str:
    base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    return f"{base}/invitation/{raw_token}"
