from django.urls import path

from .views import (
    AnswerView,
    AssessmentDetailView,
    AssessmentListView,
    CompleteAssessmentView,
    ConsolidatedScoresView,
    CurrentAssessmentView,
    MeasureOverrideListView,
    MeasureOverrideView,
    ReferentialDetailView,
    ReferentialListView,
    ScoresView,
    StartAssessmentView,
    SubsetListView,
)

urlpatterns = [
    # Conservé tel quel : c'est le référentiel PAR DÉFAUT du client (le
    # premier qui lui est attribué). Les clients d'API écrits avant V2-4
    # continuent de fonctionner sans savoir qu'il peut y en avoir plusieurs.
    path("referential/", ReferentialDetailView.as_view(), name="assessment-referential"),
    path("referentials/", ReferentialListView.as_view(), name="assessment-referential-list"),
    path(
        "referentials/<slug:slug>/",
        ReferentialDetailView.as_view(),
        name="assessment-referential-detail",
    ),
    path("subsets/", SubsetListView.as_view(), name="assessment-subset-list"),
    path("overrides/", MeasureOverrideListView.as_view(), name="assessment-override-list"),
    path(
        "measures/<int:measure_id>/override/",
        MeasureOverrideView.as_view(),
        name="assessment-measure-override",
    ),
    path("start/", StartAssessmentView.as_view(), name="assessment-start"),
    path("current/", CurrentAssessmentView.as_view(), name="assessment-current"),
    path(
        "scores/consolidated/",
        ConsolidatedScoresView.as_view(),
        name="assessment-scores-consolidated",
    ),
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
