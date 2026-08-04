from django.urls import path

from .views import (
    AnswerView,
    AssessmentDetailView,
    AssessmentListView,
    CompleteAssessmentView,
    CurrentAssessmentView,
    ReferentialView,
    ScoresView,
    StartAssessmentView,
)

urlpatterns = [
    path("referential/", ReferentialView.as_view(), name="assessment-referential"),
    path("start/", StartAssessmentView.as_view(), name="assessment-start"),
    path("current/", CurrentAssessmentView.as_view(), name="assessment-current"),
    path("", AssessmentListView.as_view(), name="assessment-list"),
    path("<int:assessment_id>/", AssessmentDetailView.as_view(), name="assessment-detail"),
    path(
        "<int:assessment_id>/answers/<int:measure_id>/",
        AnswerView.as_view(),
        name="assessment-answer",
    ),
    path(
        "<int:assessment_id>/complete/",
        CompleteAssessmentView.as_view(),
        name="assessment-complete",
    ),
    path("<int:assessment_id>/scores/", ScoresView.as_view(), name="assessment-scores"),
]
