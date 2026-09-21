"""Formes d'entrée du module Formation.

Ces sérialiseurs ne valident QUE la forme. Les règles métier — essais
épuisés, cours non parcouru, salarié déjà inscrit — vivent dans
``services.py`` et y restent : elles doivent tenir aussi quand l'appel vient
de la commande de chargement ou d'un test, pas seulement du réseau.
"""

from rest_framework import serializers


class LearnerSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()


class EnrollmentSerializer(serializers.Serializer):
    learner_id = serializers.UUIDField()
    course_slug = serializers.SlugField()
    # L'échéance de la campagne : c'est elle qui commande la durée de vie du
    # lien. Obligatoire — un lien sans échéance serait un lien perpétuel.
    due_date = serializers.DateField()


class ScreenDoneSerializer(serializers.Serializer):
    screen_id = serializers.UUIDField()


class QuizSubmissionSerializer(serializers.Serializer):
    """{identifiant de question: [identifiants de choix]}.

    ``allow_empty=False`` sur la liste interne : une question présente avec une
    liste vide est une question sans réponse, et le service la refuse avec un
    message clair. La laisser passer ici la ferait compter comme fausse, ce qui
    n'est pas la même chose — on ne se trompe pas quand on n'a pas répondu.
    """

    answers = serializers.DictField(
        child=serializers.ListField(child=serializers.UUIDField(), allow_empty=False),
        allow_empty=False,
    )


class GrantAttemptsSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=1, max_value=5, default=1)


# --- Studio (F2) ------------------------------------------------------------


class CourseSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    summary = serializers.CharField(max_length=2000, allow_blank=True, required=False)


class DuplicationSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, allow_blank=True, required=False)


class NouvelleVersionSerializer(serializers.Serializer):
    change_note = serializers.CharField(max_length=300, allow_blank=True, required=False)


class ScreenSerializer(serializers.Serializer):
    screen_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=200)
    # Le CONTENU n'est pas validé ici : son schéma vit dans blocks.py, et il
    # s'applique à tous les chemins d'écriture, pas seulement au réseau.
    # Dupliquer la règle dans un sérialiseur la ferait diverger au premier
    # ajout de bloc.
    content = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    estimated_seconds = serializers.IntegerField(min_value=5, max_value=900, required=False)


class OrdreEcransSerializer(serializers.Serializer):
    order = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class ChoixSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500)
    is_correct = serializers.BooleanField(default=False)


class QuestionSerializer(serializers.Serializer):
    question_id = serializers.UUIDField(required=False, allow_null=True)
    text = serializers.CharField(max_length=2000)
    kind = serializers.ChoiceField(choices=["single", "multiple"])
    # Obligatoire et non vide : c'est la seule partie du quiz qui forme.
    explanation = serializers.CharField(max_length=2000)
    screen_id = serializers.UUIDField()
    choices = ChoixSerializer(many=True)
