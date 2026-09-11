"""La veille cote client : un seul point d'entree, en lecture seule.

Fichier separe des routes de console, et ce n'est pas cosmetique : la
console est montee sous ``/api/v1/platform/``, reservee a l'exploitant.
Melanger les deux dans un meme fichier reviendrait a faire dependre la
separation d'une relecture attentive plutot que de la structure.
"""

from django.urls import path

from .views import PublicWatchFeedView

urlpatterns = [
    path("", PublicWatchFeedView.as_view(), name="client-watch-feed"),
]
