from rest_framework import serializers

from .models import AIJob, Conversation, GeneratedDocument, Message


class GeneratedDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedDocument
        fields = [
            "id",
            "type",
            "status",
            "version",
            "content_markdown",
            "created_at",
            "updated_at",
            "validated_at",
        ]
        read_only_fields = fields


class GeneratedDocumentCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=GeneratedDocument.DocumentType.choices)


class DocumentContentUpdateSerializer(serializers.Serializer):
    content_markdown = serializers.CharField()


class AIJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIJob
        fields = [
            "id",
            "use_case",
            "status",
            "result_ref",
            "error_message",
            "created_at",
            "finished_at",
        ]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "created_at", "updated_at"]
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "created_at"]
        read_only_fields = fields


class MessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=4000, trim_whitespace=True)

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le message ne peut pas être vide.")
        return value
