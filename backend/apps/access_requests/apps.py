from django.apps import AppConfig


class AccessRequestsConfig(AppConfig):
    """« Je voudrais ça » — le mécanisme, pas le sujet.

    Une app à part, et non un modèle rangé dans ``assessments``, parce que la
    demande d'un client à son exploitant n'a rien de propre aux référentiels :
    V2-4 s'en sert pour demander ISO 27001, V2-6 s'en servira pour d'autres
    fonctionnalités. Un ``ReferentialRequest`` aurait été à réécrire au premier
    autre usage — et un second modèle presque identique serait apparu à côté.

    Ce que l'app connaît : un sujet (``subjects.py``), un demandeur, une
    raison, un état, une réponse. Ce qu'elle ne connaît pas : ce qu'attribuer
    veut dire — chaque sujet le déclare.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.access_requests"
    verbose_name = "Demandes d'accès"
