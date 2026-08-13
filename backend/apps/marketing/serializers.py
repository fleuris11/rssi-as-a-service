from rest_framework import serializers

from .models import DemoRequest

# Domaines de messagerie grand public : on demande une adresse
# professionnelle, mais on REFUSE seulement les cas évidents. Un artisan à son
# compte peut légitimement n'avoir qu'une adresse gmail — bloquer trop large
# écarterait de vrais prospects, ce qui coûte plus cher qu'un formulaire
# rempli avec une adresse personnelle.
FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "yahoo.fr",
    "hotmail.com",
    "hotmail.fr",
    "outlook.com",
    "outlook.fr",
    "live.fr",
    "icloud.com",
    "aol.com",
    "protonmail.com",
    "yopmail.com",
    "mailinator.com",
}

# Adresses jetables : celles-là, on refuse — une demande de démonstration
# depuis une boîte temporaire n'a aucune valeur commerciale et signale
# généralement un test automatisé.
DISPOSABLE_EMAIL_DOMAINS = {"yopmail.com", "mailinator.com", "guerrillamail.com", "temp-mail.org"}


class DemoRequestSerializer(serializers.Serializer):
    """Formulaire public. ``website`` est un champ honeypot : invisible pour
    un humain, souvent rempli par un robot qui remplit tout ce qu'il trouve.
    Son nom est délibérément banal (« website ») plutôt que « honeypot »."""

    full_name = serializers.CharField(max_length=120, trim_whitespace=True)
    company = serializers.CharField(max_length=160, trim_whitespace=True)
    role = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    email = serializers.EmailField()
    company_size = serializers.ChoiceField(
        choices=DemoRequest.CompanySize.choices, required=False, allow_blank=True, default=""
    )
    preferred_slot = serializers.ChoiceField(
        choices=DemoRequest.Slot.choices, required=False, allow_blank=True, default=""
    )
    message = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, default="", trim_whitespace=True
    )
    website = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_full_name(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Merci d'indiquer votre nom.")
        return value.strip()

    def validate_company(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Merci d'indiquer le nom de votre société.")
        return value.strip()

    def validate_email(self, value):
        domain = value.rsplit("@", 1)[-1].lower()
        if domain in DISPOSABLE_EMAIL_DOMAINS:
            raise serializers.ValidationError("Merci d'utiliser une adresse email professionnelle.")
        return value.lower()

    def validate(self, attrs):
        if attrs.get("website"):
            # Honeypot rempli : on lève une erreur de validation générique.
            # Le message ne dit PAS que le piège a fonctionné — un robot qui
            # apprendrait quel champ le trahit contournerait le filtre au
            # prochain passage.
            raise serializers.ValidationError(
                {"detail": "Votre demande n'a pas pu être envoyée. Réessayez."}
            )
        return attrs


class DemoRequestAdminSerializer(serializers.ModelSerializer):
    """Vue back-office plateforme."""

    company_size_label = serializers.CharField(source="get_company_size_display", read_only=True)
    preferred_slot_label = serializers.CharField(
        source="get_preferred_slot_display", read_only=True
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DemoRequest
        fields = [
            "id",
            "full_name",
            "company",
            "role",
            "email",
            "company_size",
            "company_size_label",
            "preferred_slot",
            "preferred_slot_label",
            "message",
            "status",
            "status_label",
            "created_at",
        ]
        read_only_fields = [f for f in fields if f != "status"]


class DemoRequestStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=DemoRequest.Status.choices)
