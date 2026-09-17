"""Les courriels du module Formation.

Un seul aujourd'hui, et il ne part **pas** vers un salarié : il prévient les
administrateurs du client qu'un de leurs salariés demande à retrouver l'accès
à un cours.

Pourquoi ces envois ne passent pas par ``apps.notifications`` : ce journal-là
trace un canal précis — la météo cyber et les alertes, adressées aux
administrateurs d'une entreprise abonnée, avec une déduplication quotidienne
et un gabarit HTML. Une demande d'accès à un cours n'est rien de tout cela.
L'y faire entrer aurait demandé une valeur d'énumération, une migration et
deux gabarits pour un message de quatre lignes, et aurait mélangé deux canaux
qu'on veut pouvoir distinguer le jour où un client demandera « je ne veux plus
recevoir les alertes ».

La trace existe malgré tout, et ailleurs : ``Enrollment.access_requested_at``.
"""

from django.conf import settings
from django.core.mail import send_mail

from apps.tenants import services as tenants_services
from apps.tenants.models import Membership


def _administrateurs(tenant) -> list[str]:
    return list(
        tenants_services.list_members(tenant)
        .filter(role=Membership.Role.ADMIN)
        .values_list("user__email", flat=True)
    )


def envoyer_demande_dacces(enrollment) -> int:
    """Prévient les administrateurs qu'un salarié redemande l'accès.

    Le message ne contient **aucun lien d'accès** : rétablir l'accès est une
    décision de gestion (prolonger la campagne, réinscrire), pas quelque chose
    qu'un courriel automatique peut trancher.
    """
    destinataires = _administrateurs(enrollment.tenant)
    if not destinataires:
        return 0

    salarie = enrollment.learner
    cours = enrollment.version.course.title
    corps = (
        f"{salarie.full_name} ({salarie.email}) a ouvert son lien de formation pour le "
        f"cours « {cours} », mais celui-ci n'est plus valable.\n\n"
        f"L'échéance de la campagne était fixée au {enrollment.due_date:%d/%m/%Y}.\n\n"
        "Pour lui rendre l'accès, ouvrez Formation dans votre espace et réinscrivez-le : "
        "un nouveau lien sera émis.\n\n"
        "Ce message est envoyé automatiquement ; il ne contient aucun lien d'accès."
    )
    send_mail(
        subject=f"Formation — {salarie.full_name} demande un nouvel accès",
        message=corps,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=destinataires,
        fail_silently=False,
    )
    return len(destinataires)
