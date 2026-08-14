from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.tenants.serializers import MembershipSummarySerializer
from apps.tenants.services import create_tenant_with_owner, list_user_memberships

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "date_joined",
            "is_staff",
            "memberships",
        ]
        read_only_fields = fields

    def get_memberships(self, user):
        return MembershipSummarySerializer(list_user_memberships(user), many=True).data


class RegisterSerializer(serializers.Serializer):
    """US-1.1: creates the user's account and their company's tenant together."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    company_name = serializers.CharField(max_length=200)

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=value).exists():
            # Message générique délibérément — ne pas confirmer qu'un compte
            # existe déjà avec cet email (cadrage §6 : "messages d'erreur
            # non énumérants"). Le risque résiduel (le champ en erreur, le
            # code 400) est documenté dans docs/security_review.md (A07) et
            # atténué par le rate limiting sur cet endpoint (apps.accounts.
            # throttling.AuthRateThrottle).
            raise serializers.ValidationError(
                "Impossible de créer un compte avec ces informations."
            )
        return value

    def create(self, validated_data):
        from apps.billing.capacity import PlatformCapacityError

        company_name = validated_data.pop("company_name")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        try:
            create_tenant_with_owner(name=company_name, owner=user)
        except PlatformCapacityError:
            # La licence de renseignement plafonne la plateforme entière. Une
            # inscription de plus engagerait des emplacements qui n'existent
            # pas : on refuse explicitement plutôt que de livrer un compte
            # dont toutes les fonctions se bloqueraient ensuite. Le détail du
            # plafond ne regarde pas un visiteur non authentifié — il est
            # tracé côté serveur et visible dans le back-office.
            user.delete()
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Les inscriptions sont momentanément fermées, faute de capacité "
                        "disponible. Écrivez-nous pour être prévenu de leur réouverture."
                    )
                }
            ) from None
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class TwoFactorSetupResponseSerializer(serializers.Serializer):
    secret = serializers.CharField()
    otpauth_uri = serializers.CharField()
    qr_code = serializers.CharField()


class TwoFactorConfirmSerializer(serializers.Serializer):
    code = serializers.RegexField(
        r"^\d{6}$", error_messages={"invalid": "Code à 6 chiffres attendu."}
    )


class TwoFactorDisableSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)


class TwoFactorVerifySerializer(serializers.Serializer):
    challenge_token = serializers.CharField()
    code = serializers.CharField(required=False, allow_blank=True, default="")
    recovery_code = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("code") and not attrs.get("recovery_code"):
            raise serializers.ValidationError(
                "Fournissez un code de vérification ou de récupération."
            )
        return attrs
