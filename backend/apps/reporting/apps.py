from django.apps import AppConfig


class ReportingConfig(AppConfig):
    """App sans modèle : elle compose les indicateurs des autres (ADR-028).

    Elle existe parce qu'aucune app métier n'était le bon endroit — la
    restitution de comité traverse le diagnostic, le plan d'action, la
    surveillance et le renseignement. La loger dans l'une d'elles aurait été
    arbitraire, et y aurait fait entrer les trois autres.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reporting"
    verbose_name = "Restitution et indicateurs"
