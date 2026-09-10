from django.apps import AppConfig


class RegulatoryWatchConfig(AppConfig):
    """Veille sur l'evolution des referentiels et des exigences (V2-7).

    App separee et non un module d'``assessments``, parce que la separation
    est exactement ce qui garantit la regle : la veille SUGGERE, elle ne
    modifie pas. Un module range dans l'app des referentiels aurait eu la
    main sur leurs modeles ; ici, le seul chemin vers une mesure passe par
    ``assessments.services``, avec un relecteur nomme.

    Non scopee par tenant : la veille est une activite de l'exploitant, et le
    catalogue qu'elle alimente est partage (ADR-029).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.regulatory_watch"
    verbose_name = "Veille reglementaire"
