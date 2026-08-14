import uuid

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'email est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superutilisateur doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superutilisateur doit avoir is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Platform-wide identity. Not tenant data — a user can belong to
    several tenants via apps.tenants.models.Membership."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_short_name(self):
        return self.first_name or self.email


class AccessInvitation(models.Model):
    """Jeton à usage unique pour définir ou réinitialiser un mot de passe.

    Raison d'être (phase 11) : un administrateur plateforme crée des comptes
    pour ses clients, et **ne doit jamais manipuler leur mot de passe** — ni le
    choisir, ni le lire, ni le transmettre. Il émet un lien à durée limitée ;
    seule la personne destinataire fixe son mot de passe.

    Le jeton n'est stocké que **haché**, exactement comme un mot de passe : une
    fuite de cette table ne doit pas permettre de prendre la main sur des
    comptes. La valeur en clair n'existe qu'une fois, dans la réponse HTTP qui
    suit immédiatement sa création.
    """

    class Purpose(models.TextChoices):
        INVITATION = "invitation", "Première connexion"
        RESET = "reset", "Réinitialisation de mot de passe"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="access_invitations"
    )
    purpose = models.CharField(max_length=12, choices=Purpose.choices)
    token_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    # Qui a émis le lien. Un lien de réinitialisation émis par un
    # administrateur et un lien demandé par l'utilisateur lui-même ne se lisent
    # pas de la même façon dans un journal.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "purpose"])]

    def __str__(self):
        return f"{self.get_purpose_display()} — {self.user_id}"

    @property
    def is_usable(self) -> bool:
        from django.utils import timezone as _timezone

        return self.used_at is None and self.expires_at > _timezone.now()


class TwoFactorCredential(models.Model):
    """US-1.3 (2FA TOTP). One per user, platform-wide (not tenant-scoped —
    login happens before any tenant is selected). ``encrypted_secret`` is
    the base32 TOTP secret, Fernet-encrypted at rest (cadrage §6) with a
    key dedicated to this app (``TOTP_ENCRYPTION_KEY``, distinct from
    ``AI_PSEUDONYMIZATION_KEY`` — compromising one must not compromise the
    other). ``confirmed=False`` rows are enrollments in progress: a user
    who starts setup but never confirms is not yet 2FA-protected."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="two_factor"
    )
    encrypted_secret = models.BinaryField()
    confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        state = "confirmé" if self.confirmed else "en attente de confirmation"
        return f"2FA — {self.user_id} ({state})"


class RecoveryCode(models.Model):
    """One-time-use fallback codes issued when 2FA is confirmed (US-1.3).
    Stored hashed (Django's password hasher) exactly like a password —
    never recoverable in plaintext once issued."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recovery_codes"
    )
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        state = "utilisé" if self.used_at else "disponible"
        return f"Code de récupération — {self.user_id} ({state})"
