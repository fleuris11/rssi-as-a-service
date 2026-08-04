from django.urls import path

from .views import ActionItemDetailView, ActionItemListView, ProjectedScoreView

urlpatterns = [
    path("", ActionItemListView.as_view(), name="action-item-list"),
    path("projected-score/", ProjectedScoreView.as_view(), name="action-projected-score"),
    path("<int:item_id>/", ActionItemDetailView.as_view(), name="action-item-detail"),
]
