"""Deux préfixes, et la séparation est intentionnelle.

``session/`` est **non authentifié** : le client HTTP du frontend n'y joint ni
jeton JWT ni en-tête d'entreprise (voir ``UNAUTHENTICATED_PATHS``). Le préfixe
est donc ce qui distingue, d'un coup d'œil dans les journaux comme dans le
code, ce qui est ouvert de ce qui ne l'est pas.
"""

from django.urls import path

from .studio_views import (
    CoursDetailView,
    CoursListView,
    DuplicationView,
    EcransView,
    OrdreEcransView,
    PublicationView,
    QuestionsView,
    VersionView,
)
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
    # Le studio (F2). Même préfixe pour l'exploitant et pour un client : c'est
    # la même mécanique, et seul le propriétaire du cours change.
    path("studio/cours/", CoursListView.as_view(), name="formation-studio-cours"),
    path(
        "studio/cours/<uuid:course_id>/",
        CoursDetailView.as_view(),
        name="formation-studio-cours-detail",
    ),
    path(
        "studio/cours/<uuid:course_id>/dupliquer/",
        DuplicationView.as_view(),
        name="formation-studio-dupliquer",
    ),
    path(
        "studio/versions/<uuid:version_id>/",
        VersionView.as_view(),
        name="formation-studio-version",
    ),
    path(
        "studio/versions/<uuid:version_id>/publier/",
        PublicationView.as_view(),
        name="formation-studio-publier",
    ),
    path(
        "studio/versions/<uuid:version_id>/ecrans/",
        EcransView.as_view(),
        name="formation-studio-ecrans",
    ),
    path(
        "studio/versions/<uuid:version_id>/ecrans/ordre/",
        OrdreEcransView.as_view(),
        name="formation-studio-ordre",
    ),
    path(
        "studio/versions/<uuid:version_id>/ecrans/<uuid:screen_id>/",
        EcransView.as_view(),
        name="formation-studio-ecran",
    ),
    path(
        "studio/versions/<uuid:version_id>/questions/",
        QuestionsView.as_view(),
        name="formation-studio-questions",
    ),
    path(
        "studio/versions/<uuid:version_id>/questions/<uuid:question_id>/",
        QuestionsView.as_view(),
        name="formation-studio-question",
    ),
]
