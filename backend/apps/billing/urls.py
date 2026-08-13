from django.urls import path

from .views import EntitlementsView, PublicPlanListView

urlpatterns = [
    # Public (site vitrine) : le catalogue publié, sans authentification.
    path("plans/", PublicPlanListView.as_view(), name="public-plan-list"),
    # Client connecté : ce que comprend son offre, et ce qui n'y est pas.
    path("entitlements/", EntitlementsView.as_view(), name="tenant-entitlements"),
]
