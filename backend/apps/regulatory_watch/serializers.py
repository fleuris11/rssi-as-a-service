from rest_framework import serializers

from .models import WatchSource, WatchUpdate


class WatchSourceSerializer(serializers.ModelSerializer):
    format_label = serializers.CharField(source="get_format_display", read_only=True)
    is_healthy = serializers.BooleanField(read_only=True)
    #: Une source à flux sans adresse de flux n'est pas cassée : elle n'a
    #: jamais été configurée. La console doit pouvoir le dire autrement qu'en
    #: la comptant comme une panne.
    needs_configuration = serializers.SerializerMethodField()

    class Meta:
        model = WatchSource
        fields = [
            "id",
            "slug",
            "name",
            "publisher",
            "url",
            "feed_url",
            "format",
            "format_label",
            "expected_frequency",
            "scope_note",
            "is_active",
            "is_healthy",
            "needs_configuration",
            "last_polled_at",
            "last_success_at",
            "last_error",
            "consecutive_failures",
        ]
        read_only_fields = [
            "id",
            "slug",
            "format_label",
            "is_healthy",
            "needs_configuration",
            "last_polled_at",
            "last_success_at",
            "last_error",
            "consecutive_failures",
        ]

    def get_needs_configuration(self, source) -> bool:
        return source.format != WatchSource.Format.PAGE and not source.feed_url


class WatchUpdateSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", read_only=True)
    source_publisher = serializers.CharField(source="source.publisher", read_only=True)
    source_format = serializers.CharField(source="source.format", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    reviewed_by_email = serializers.SerializerMethodField()
    referential_name = serializers.CharField(
        source="target_referential.name", read_only=True, default=None
    )
    integrated_measures = serializers.SerializerMethodField()

    class Meta:
        model = WatchUpdate
        fields = [
            "id",
            "source",
            "source_name",
            "source_publisher",
            "source_format",
            "title",
            # L'URL de la publication OFFICIELLE : c'est elle qu'on ouvre
            # avant de décider, et elle reste la référence.
            "url",
            "published_at",
            "detected_at",
            "source_excerpt",
            "status",
            "status_label",
            "kind",
            "kind_label",
            "review_note",
            "reviewed_by_email",
            "reviewed_at",
            "target_referential",
            "referential_name",
            "integrated_measures",
            # Le résumé machine, toujours à côté du texte source, jamais à sa
            # place — et daté, pour qu'on sache ce qu'il a résumé.
            "ai_summary",
            "ai_summary_model",
            "ai_summary_at",
        ]
        read_only_fields = fields

    def get_reviewed_by_email(self, update):
        return update.reviewed_by.email if update.reviewed_by_id else None

    def get_integrated_measures(self, update):
        return [
            {
                "id": mesure.id,
                "code": mesure.code,
                "official_title": mesure.official_title,
                "referential": mesure.referential.name,
            }
            for mesure in update.integrated_measures.select_related("referential")
        ]


class ReviewUpdateSerializer(serializers.Serializer):
    """La décision d'un humain sur une suggestion.

    ``integrated`` est absent des choix : ce statut n'est pas une décision
    qu'on pose, c'est la conséquence d'une intégration réelle, qui passe par
    l'endpoint dédié et exige un contenu saisi.

    ``referential`` n'a **pas** de valeur par défaut : son absence du corps de
    la requête doit rester distinguable d'une chaîne vide. Absent, le
    rattachement existant est conservé ; vide, il est retiré (D3).
    """

    status = serializers.ChoiceField(
        choices=[WatchUpdate.Status.NEW, WatchUpdate.Status.KEPT, WatchUpdate.Status.DISMISSED]
    )
    kind = serializers.ChoiceField(choices=WatchUpdate.Kind.choices, required=False, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")
    referential = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        """Deuxième garde de l'état terminal, indépendante du service (D2).

        Le service refuse déjà de re-trier une suggestion intégrée. On le
        refuse aussi ici, sur le même modèle que l'exclusion d'``integrated``
        des choix : deux couches qui ne partagent pas leur code, pour que
        neutraliser l'une laisse l'autre debout.
        """
        update = self.context.get("update")
        if update is not None and update.status == WatchUpdate.Status.INTEGRATED:
            raise serializers.ValidationError(
                {
                    "status": (
                        "Cette publication a déjà donné lieu à une mesure : son statut "
                        "n'est plus modifiable."
                    )
                }
            )
        return attrs


class IntegrateMeasureSerializer(serializers.Serializer):
    """Le contenu de la mesure est SAISI, jamais repris automatiquement de la
    publication : un titre de communiqué ne fait pas une exigence lisible."""

    referential = serializers.CharField()
    domain_code = serializers.CharField(max_length=100)
    code = serializers.CharField(max_length=40)
    official_title = serializers.CharField(max_length=300)
    plain_language = serializers.CharField(max_length=2000)
    level = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    weight = serializers.FloatField(required=False, default=1.0, min_value=0.01)
    effort = serializers.ChoiceField(
        choices=["low", "medium", "high"], required=False, default="medium"
    )
    impact = serializers.ChoiceField(
        choices=["low", "medium", "high"], required=False, default="medium"
    )
