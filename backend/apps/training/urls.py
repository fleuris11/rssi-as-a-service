"""Deux préfixes, et la séparation est intentionnelle.

``session/`` est **non authentifié** : le client HTTP du frontend n'y joint ni
jeton JWT ni en-tête d'entreprise (voir ``UNAUTHENTICATED_PATHS``). Le préfixe
est donc ce qui distingue, d'un coup d'œil dans les journaux comme dans le
code, ce qui est ouvert de ce qui ne l'est pas.
"""

from django.urls import path

from .views import (
    AccessRequestView,
    CatalogueView,
    CertificateView,
    EnrollmentAttemptsView,
    EnrollmentDetailView,
    EnrollmentLinkView,
    EnrollmentsView,
    LearnersView,
    QuizView,
    ScreenDoneView,
    SessionView,
)

urlpatterns = [
    # L'apprenant, sur lien nominatif.
    path("session/", SessionView.as_view(), name="formation-session"),
    path("session/ecran/", ScreenDoneView.as_view(), name="formation-ecran"),
    path("session/quiz/", QuizView.as_view(), name="formation-quiz"),
    path("session/attestation/", CertificateView.as_view(), name="formation-attestation"),
    path("session/acces/", AccessRequestView.as_view(), name="formation-demande-acces"),
    # Le pilote, dans son espace client.
    path("pilotage/catalogue/", CatalogueView.as_view(), name="formation-catalogue"),
    path("pilotage/salaries/", LearnersView.as_view(), name="formation-salaries"),
    path("pilotage/inscriptions/", EnrollmentsView.as_view(), name="formation-inscriptions"),
    path(
        "pilotage/inscriptions/<uuid:enrollment_id>/",
        EnrollmentDetailView.as_view(),
        name="formation-inscription",
    ),
    path(
        "pilotage/inscriptions/<uuid:enrollment_id>/lien/",
        EnrollmentLinkView.as_view(),
        name="formation-lien",
    ),
    path(
        "pilotage/inscriptions/<uuid:enrollment_id>/essais/",
        EnrollmentAttemptsView.as_view(),
        name="formation-essais",
    ),
]
