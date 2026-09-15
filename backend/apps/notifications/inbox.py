"""Les notifications DANS l'application (lot C, point 20 ; ADR-037).

Interface publique : les autres apps passent par ici pour prévenir quelqu'un,
jamais par le modèle (règle d'architecture n°1). Module volontairement séparé
de ``services.py`` : celui-ci importe la surveillance, le renseignement et
l'IA pour composer les emails ; une app qui voudrait simplement prévenir un
utilisateur importerait toute cette chaîne, et la première dépendance
circulaire suivrait. Ici, aucune dépendance métier — seulement les membres
d'un client, via ``tenants.services``.

Trois règles, chacune tenue par un test :

- une notification appartient à une PERSONNE, pas à un client : celles de
  l'exploitant n'ont pas de client, et un utilisateur qui suit trois
  entreprises reçoit les trois dans la même cloche ;
- une personne qui a quitté un client ne voit plus ce qui concerne ce client ;
- un même événement ne notifie pas deux fois la même personne (clé
  d'idempotence) — les tâches Celery sont relivrées, un double clic arrive.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from apps.tenants import services as tenants_services

from .models import Notification

Kind = Notification.Kind


def notify(recipients, *, kind, title, body="", link="", tenant=None, dedupe_key="") -> int:
    """Crée une notification par destinataire. Renvoie le nombre CRÉÉ.

    Avec ``dedupe_key``, un second appel pour le même destinataire ne crée
    rien : la contrainte d'unicité tranche, en base, même entre deux workers.
    """
    destinataires = {user.pk: user for user in recipients if user is not None}
    if not destinataires:
        return 0

    avant = (
        Notification.objects.filter(recipient_id__in=destinataires, dedupe_key=dedupe_key).count()
        if dedupe_key
        else 0
    )
    Notification.objects.bulk_create(
        [
            Notification(
                recipient=user,
                tenant=tenant,
                kind=kind,
                title=title[:200],
                body=body,
                link=link[:200],
                dedupe_key=dedupe_key,
            )
            for user in destinataires.values()
        ],
        ignore_conflicts=bool(dedupe_key),
    )
    if not dedupe_key:
        return len(destinataires)
    apres = Notification.objects.filter(
        recipient_id__in=destinataires, dedupe_key=dedupe_key
    ).count()
    return apres - avant


def tenant_admins(tenant) -> list:
    """Les administrateurs ACTIFS d'un client — ceux qui répondent de son compte."""
    return [
        adhesion.user
        for adhesion in tenants_services.list_members(tenant)
        if adhesion.role == "admin" and adhesion.user.is_active
    ]


def staff_users() -> list:
    """Les administrateurs de la plateforme en activité."""
    return list(get_user_model().objects.filter(is_staff=True, is_active=True))


def notify_tenant_admins(tenant, **champs) -> int:
    return notify(tenant_admins(tenant), tenant=tenant, **champs)


def notify_staff(**champs) -> int:
    """Côté exploitant : sans client rattaché, par construction."""
    return notify(staff_users(), tenant=None, **champs)


def visible_for(user):
    """Ce que ``user`` peut lire : les siennes, et pour celles qui concernent
    un client, seulement s'il en est encore membre."""
    clients = [adhesion.tenant_id for adhesion in tenants_services.list_user_memberships(user)]
    return Notification.objects.filter(recipient=user).filter(
        Q(tenant__isnull=True) | Q(tenant_id__in=clients)
    )


def list_for_user(user, *, unread_only=False, search=""):
    notifications = visible_for(user).select_related("tenant")
    if unread_only:
        notifications = notifications.filter(read_at__isnull=True)
    if search:
        notifications = notifications.filter(Q(title__icontains=search) | Q(body__icontains=search))
    return notifications.order_by("-created_at", "-id")


def unread_count(user) -> int:
    return visible_for(user).filter(read_at__isnull=True).count()


def mark_read(user, ids) -> int:
    """Marque comme lues les notifications désignées, parmi les SIENNES."""
    return (
        visible_for(user)
        .filter(id__in=list(ids), read_at__isnull=True)
        .update(read_at=timezone.now())
    )


def mark_all_read(user) -> int:
    return visible_for(user).filter(read_at__isnull=True).update(read_at=timezone.now())
