from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.threat_intelligence.views import BreachsenseWebhookView

from .views import healthz, healthz_worker

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
    path("healthz/worker", healthz_worker, name="healthz-worker"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/tenants/", include("apps.tenants.urls")),
    path("api/v1/assessments/", include("apps.assessments.urls")),
    path("api/v1/actions/", include("apps.actions.urls")),
    path("api/v1/monitoring/", include("apps.monitoring.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/ai/", include("apps.ai_assistant.urls")),
    path("api/v1/threat-intelligence/", include("apps.threat_intelligence.urls")),
    # Site vitrine public : demande de démonstration (endpoint non
    # authentifié) et sa consultation en back-office plateforme.
    path("api/v1/", include("apps.marketing.urls")),
    # Back-office plateforme (Phase 10) : abonnements, offres, ressources
    # rares, santé. Garde IsAdminUser, jamais les permissions de tenant.
    path("api/v1/platform/", include("apps.platform_admin.urls")),
    path(
        "api/v1/platform/access-requests/",
        include("apps.access_requests.console_urls"),
    ),
    # Veille reglementaire (V2-7) : console UNIQUEMENT. Sous le namespace
    # plateforme, jamais sous un namespace client — une suggestion non triee
    # n'a rien a faire sous les yeux d'un client.
    path("api/v1/platform/watch/", include("apps.regulatory_watch.urls")),
    path("api/v1/billing/", include("apps.billing.urls")),
    path("api/v1/reporting/", include("apps.reporting.urls")),
    # Demandes d'un client a l'exploitant. Le meme modele sert des deux cotes :
    # ici le depot et le suivi (permissions de tenant), plus bas dans le
    # namespace plateforme la file et les reponses (permissions de console).
    path("api/v1/access-requests/", include("apps.access_requests.urls")),
    # Hors du namespace tenant-scopé habituel : pas de JWT/X-Tenant-Id côté
    # Breachsense, authentification HTTP Basic dédiée (ADR-013 §7).
    path(
        "api/v1/webhooks/breachsense",
        BreachsenseWebhookView.as_view(),
        name="breachsense-webhook",
    ),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
