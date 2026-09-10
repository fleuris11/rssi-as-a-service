from rest_framework import serializers

from . import subjects
from .models import AccessRequest


class AccessRequestSerializer(serializers.ModelSerializer):
    requested_by_email = serializers.SerializerMethodField()
    handled_by_email = serializers.SerializerMethodField()
    subject_type_label = serializers.SerializerMethodField()
    # Le libellé plutôt que la valeur brute : « Client contacté » se lit,
    # « contacted » se devine.
    status_label = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()

    class Meta:
        model = AccessRequest
        fields = [
            "id",
            "subject_type",
            "subject_type_label",
            "subject_key",
            "subject_label",
            "reason",
            "status",
            "status_label",
            "is_open",
            "response",
            "requested_by_email",
            "created_at",
            "handled_by_email",
            "handled_at",
        ]
        read_only_fields = fields

    def get_requested_by_email(self, demande):
        return demande.requested_by.email if demande.requested_by_id else None

    def get_handled_by_email(self, demande):
        return demande.handled_by.email if demande.handled_by_id else None

    def get_subject_type_label(self, demande):
        subject = subjects.get(demande.subject_type)
        return subject.label if subject else demande.subject_type

    def get_status_label(self, demande):
        return demande.get_status_display()

    def get_is_open(self, demande) -> bool:
        return demande.is_open


class ConsoleAccessRequestSerializer(AccessRequestSerializer):
    """La même demande, vue de la console : avec le client qui la porte."""

    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta(AccessRequestSerializer.Meta):
        fields = [*AccessRequestSerializer.Meta.fields, "tenant_id", "tenant_name"]
        read_only_fields = fields


class CreateAccessRequestSerializer(serializers.Serializer):
    subject_type = serializers.ChoiceField(choices=subjects.all_keys())
    subject_key = serializers.CharField(max_length=100)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class HandleAccessRequestSerializer(serializers.Serializer):
    """L'étape suivante du suivi (V2-6).

    La liste des choix exclut ``pending`` et ``cancelled`` : la console ne
    replace pas une demande en « nouvelle » après l'avoir travaillée, et elle
    n'annule pas au nom du client. Ces deux exclusions valent règle métier —
    le service les redemande, pour qu'un appel direct rencontre le même refus.
    """

    status = serializers.ChoiceField(
        choices=[
            AccessRequest.Status.CONTACTED,
            AccessRequest.Status.PROPOSAL,
            AccessRequest.Status.GRANTED,
            AccessRequest.Status.DECLINED,
        ]
    )
    response = serializers.CharField(required=False, allow_blank=True, default="")
