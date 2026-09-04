"""Public interface of the tenants app — other apps must go through here
instead of importing apps.tenants.models directly (CLAUDE.md architecture rule).
"""

import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import Membership, Tenant

logger = logging.getLogger(__name__)


def _unique_slug(name: str) -> str:
    base = slugify(name)[:200] or "entreprise"
    slug = base
    counter = 1
    while Tenant.objects.filter(slug=slug).exists():
        counter += 1
        slug = f"{base}-{counter}"
    return slug


@transaction.atomic
def create_tenant_with_owner(
    *, name: str, owner, sector: str = "", headcount: int | None = None
) -> Tenant:
    """Creates a tenant and makes ``owner`` its first admin member.

    Atomique : si l'ouverture de l'essai est refusée faute de capacité, on ne
    laisse pas derrière soi une entreprise à moitié créée.
    """
    tenant = Tenant.objects.create(
        name=name,
        slug=_unique_slug(name),
        sector=sector,
        headcount=headcount,
    )
    Membership.all_objects.create(tenant=tenant, user=owner, role=Membership.Role.ADMIN)

    # Essai automatique (Phase 10). Import différé : apps.billing importe
    # apps.tenants pour sa clé étrangère, un import au niveau module créerait
    # un cycle.
    from apps.billing import capacity
    from apps.billing import services as billing_services

    try:
        billing_services.start_trial(tenant=tenant, actor=owner)
    except capacity.PlatformCapacityError:
        # Le seul échec qui n'est PAS absorbé. Un essai engage des
        # emplacements de surveillance sur un pool partagé par toute la
        # plateforme : l'ouvrir quand même reviendrait à constater le
        # dépassement après coup. Créer l'entreprise sans son abonnement
        # serait à peine mieux — l'utilisateur obtiendrait un compte dont
        # toutes les fonctions refusent. On remonte donc le refus, à charge
        # de l'appelant de l'afficher (la transaction annule la création).
        raise
    except Exception:  # noqa: BLE001 - la création d'entreprise prime
        # Tout le reste (catalogue d'offres vide, offre par défaut retirée)
        # est un défaut de configuration de la plateforme, pas une limite
        # qu'on oppose au client : l'entreprise est créée sans abonnement,
        # état que les gardes d'entitlements traitent explicitement
        # (« aucun abonnement actif »).
        logger.warning(
            "Essai non ouvert pour l'entreprise %s : abonnement à créer manuellement.",
            tenant.id,
            exc_info=True,
        )

    return tenant


def list_user_memberships(user):
    """All of a user's memberships, across every tenant (used before a
    tenant is selected, e.g. to populate a tenant switcher)."""
    return (
        Membership.all_objects.filter(user=user).select_related("tenant").order_by("tenant__name")
    )


def get_membership(*, user, tenant_id):
    return (
        Membership.all_objects.filter(user=user, tenant_id=tenant_id)
        .select_related("tenant")
        .first()
    )


def list_tenant_members(tenant: Tenant):
    """Members of ``tenant``. Relies on TenantScopingMiddleware having
    already set the tenant context for this request."""
    return Membership.objects.select_related("user").filter(tenant=tenant)


def list_members(tenant: Tenant):
    """Members of ``tenant``, independent of ambient tenant context —
    for Celery tasks and other code with no request/middleware to have set
    it, where list_tenant_members's request-scoped read isn't available."""
    return Membership.all_objects.select_related("user").filter(tenant=tenant)


def get_tenant(tenant_id):
    return Tenant.objects.filter(id=tenant_id).first()


# --- Console d'administration : cycle de vie complet (phase 11) -------------
#
# Ces opérations sont appelées par le back-office. Elles portent la règle
# métier UNE SEULE FOIS, côté serveur : l'interface les réutilise, elle ne les
# redéfinit pas. Aucune ne se contente d'écrire — chacune valide d'abord, et
# laisse remonter le refus.


class TenantError(Exception):
    """Violation d'une règle métier de gestion des entreprises."""


# Champs modifiables depuis la console. Liste explicite : appliquer en bloc ce
# que contient la requête laisserait modifier ``is_active`` ou ``archived_at``
# par un chemin qui ne les trace pas.
EDITABLE_TENANT_FIELDS = (
    "name",
    "sector",
    "headcount",
    "contact_email",
    "contact_phone",
    "address",
    "website",
    "account_manager",
    "internal_notes",
    # Surcharge du délai entre deux analyses manuelles (ADR-013 : le délai
    # protège le budget de requêtes PARTAGÉ, pas le client — il n'a donc pas
    # à être le même pour tous). Figurer dans cette liste sert deux choses :
    # la fiche peut l'écrire, et `snapshot_tenant` l'inclut, donc toute
    # modification apparaît dans le journal d'audit. Un réglage qui allonge ou
    # supprime un délai commercial doit laisser une trace de qui l'a décidé.
    "scan_cooldown_minutes",
)


def snapshot_tenant(tenant: Tenant) -> dict:
    """État auditable d'une entreprise, pour comparer avant/après."""
    return {field: getattr(tenant, field) for field in EDITABLE_TENANT_FIELDS}


@transaction.atomic
def create_client(
    *,
    name: str,
    owner_email: str,
    plan=None,
    engagement: str = "trial",
    trial_days: int | None = None,
    owner_first_name: str = "",
    owner_last_name: str = "",
    actor=None,
    **tenant_fields,
):
    """Crée une entreprise, son premier utilisateur et son abonnement.

    **Une seule opération atomique** : une entreprise sans utilisateur, ou avec
    un utilisateur mais sans abonnement, est un état que personne ne sait
    rattraper depuis l'interface. Si la capacité manque, rien n'est écrit et
    l'erreur remonte telle quelle.

    Renvoie ``(tenant, user, subscription, jeton d'invitation en clair)``. Le
    jeton n'existe qu'ici et dans la réponse HTTP qui suit : il n'est pas
    stocké en clair.
    """
    from apps.accounts.models import AccessInvitation
    from apps.accounts.services import create_access_invitation
    from apps.billing import services as billing_services

    name = (name or "").strip()
    if not name:
        raise TenantError("Le nom de l'entreprise est obligatoire.")
    if Tenant.objects.filter(name__iexact=name, archived_at__isnull=True).exists():
        raise TenantError(f"Une entreprise nommée « {name} » existe déjà.")

    owner_email = (owner_email or "").strip().lower()
    if not owner_email:
        raise TenantError("L'adresse email du premier utilisateur est obligatoire.")

    User = get_user_model()
    user = User.objects.filter(email__iexact=owner_email).first()
    if user is None:
        # Créé SANS mot de passe utilisable : seul le lien d'invitation
        # permettra d'en définir un. Un administrateur ne choisit jamais le
        # mot de passe d'un tiers.
        user = User.objects.create_user(
            email=owner_email,
            password=None,
            first_name=owner_first_name,
            last_name=owner_last_name,
        )
        user.set_unusable_password()
        user.is_active = False
        user.save(update_fields=["password", "is_active"])

    tenant = Tenant.objects.create(
        name=name,
        slug=_unique_slug(name),
        **{k: v for k, v in tenant_fields.items() if k in EDITABLE_TENANT_FIELDS and k != "name"},
    )
    Membership.all_objects.create(tenant=tenant, user=user, role=Membership.Role.ADMIN)

    # La garde de capacité s'applique ici comme partout ailleurs. Aucun
    # ``except`` autour : un refus doit annuler toute la transaction.
    subscription = billing_services.start_trial(
        tenant=tenant, plan=plan, actor=actor, days=trial_days
    )
    if engagement == "active":
        billing_services.activate(
            subscription=subscription,
            actor=actor,
            reason="Client créé directement en abonnement actif.",
        )

    _invitation, raw_token = create_access_invitation(
        user=user, purpose=AccessInvitation.Purpose.INVITATION, actor=actor
    )
    return tenant, user, subscription, raw_token


def update_tenant(*, tenant: Tenant, **fields) -> tuple[Tenant, dict]:
    """Modifie une fiche entreprise. Renvoie (entreprise, champs modifiés)."""
    from apps.platform_admin.services import diff_fields

    before = snapshot_tenant(tenant)

    if "name" in fields:
        name = (fields["name"] or "").strip()
        if not name:
            raise TenantError("Le nom de l'entreprise est obligatoire.")
        clash = Tenant.objects.filter(name__iexact=name, archived_at__isnull=True).exclude(
            id=tenant.id
        )
        if clash.exists():
            raise TenantError(f"Une autre entreprise porte déjà le nom « {name} ».")
        fields["name"] = name

    for field, value in fields.items():
        if field in EDITABLE_TENANT_FIELDS:
            setattr(tenant, field, value)
    tenant.save()

    return tenant, diff_fields(before, snapshot_tenant(tenant))


@transaction.atomic
def archive_tenant(*, tenant: Tenant, actor=None, reason: str = "") -> Tenant:
    """Archivage réversible : l'entreprise sort des listes actives et son
    abonnement est résilié, mais rien n'est détruit.

    Résilier l'abonnement n'est pas un détail : sans cela, une entreprise
    archivée continuerait d'occuper des emplacements du pool partagé.
    """
    from apps.billing import entitlements
    from apps.billing import services as billing_services

    if tenant.is_archived:
        return tenant

    subscription = entitlements.get_subscription(tenant)
    if subscription is not None and subscription.is_operational:
        billing_services.cancel(
            subscription=subscription, actor=actor, reason="Entreprise archivée."
        )

    tenant.archived_at = timezone.now()
    tenant.archived_by = actor
    tenant.archive_reason = reason[:200]
    tenant.is_active = False
    tenant.save(update_fields=["archived_at", "archived_by", "archive_reason", "is_active"])
    return tenant


@transaction.atomic
def restore_tenant(*, tenant: Tenant) -> Tenant:
    """Sort de la corbeille. L'abonnement reste résilié : le réactiver
    ré-engagerait des emplacements sans vérification, et c'est une décision
    commerciale distincte de « je me suis trompé en archivant »."""
    if not tenant.is_archived:
        return tenant

    tenant.archived_at = None
    tenant.archived_by = None
    tenant.archive_reason = ""
    tenant.is_active = True
    tenant.save(update_fields=["archived_at", "archived_by", "archive_reason", "is_active"])
    return tenant


def purgeable_tenants(*, retention_days: int):
    """Entreprises archivées depuis assez longtemps pour être supprimées."""
    cutoff = timezone.now() - timedelta(days=retention_days)
    return Tenant.objects.filter(archived_at__isnull=False, archived_at__lte=cutoff)


@transaction.atomic
def delete_tenant_permanently(*, tenant: Tenant) -> str:
    """Suppression DÉFINITIVE, sans retour. Réservée aux entreprises déjà
    archivées : on ne détruit jamais des données en un seul geste."""
    if not tenant.is_archived:
        raise TenantError(
            "Cette entreprise doit d'abord être archivée. La suppression définitive "
            "n'est possible que depuis la corbeille."
        )
    name = tenant.name
    tenant.delete()
    return name


# --- Utilisateurs d'un client ----------------------------------------------


@transaction.atomic
def invite_member(
    *, tenant: Tenant, email: str, role: str, actor=None, first_name: str = "", last_name: str = ""
):
    """Ajoute un utilisateur à une entreprise et émet son lien d'accès.

    Renvoie ``(membership, jeton en clair)``. Le quota d'utilisateurs de
    l'offre est vérifié AVANT l'écriture, comme toute autre limite.
    """
    from apps.accounts.models import AccessInvitation
    from apps.accounts.services import create_access_invitation
    from apps.billing import entitlements

    email = (email or "").strip().lower()
    if not email:
        raise TenantError("L'adresse email est obligatoire.")
    if role not in Membership.Role.values:
        raise TenantError("Rôle inconnu.")

    entitlements.ensure_user_quota(tenant, additional=1)

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create_user(
            email=email, password=None, first_name=first_name, last_name=last_name
        )
        user.set_unusable_password()
        user.is_active = False
        user.save(update_fields=["password", "is_active"])

    if Membership.all_objects.filter(tenant=tenant, user=user).exists():
        raise TenantError("Cette personne fait déjà partie de cette entreprise.")

    membership = Membership.all_objects.create(tenant=tenant, user=user, role=role)
    _invitation, raw_token = create_access_invitation(
        user=user, purpose=AccessInvitation.Purpose.INVITATION, actor=actor
    )
    return membership, raw_token


def _is_last_admin(membership: Membership) -> bool:
    """Un client sans administrateur ne peut plus gérer ses propres accès —
    et seul le back-office pourrait l'en sortir. On refuse en amont."""
    if membership.role != Membership.Role.ADMIN:
        return False
    return (
        Membership.all_objects.filter(tenant_id=membership.tenant_id, role=Membership.Role.ADMIN)
        .exclude(id=membership.id)
        .count()
        == 0
    )


def change_member_role(*, membership: Membership, role: str) -> Membership:
    if role not in Membership.Role.values:
        raise TenantError("Rôle inconnu.")
    if role != Membership.Role.ADMIN and _is_last_admin(membership):
        raise TenantError(
            "C'est le dernier administrateur de cette entreprise. Nommez d'abord "
            "un autre administrateur."
        )
    membership.role = role
    membership.save(update_fields=["role"])
    return membership


def set_member_active(*, membership: Membership, active: bool) -> Membership:
    """Coupe ou rétablit l'accès d'une personne.

    Le cas réel : un salarié quitte l'entreprise cliente. On désactive son
    compte plutôt que de le supprimer — son historique d'actions reste
    attribuable, et une réactivation reste possible s'il revient.
    """
    if not active and _is_last_admin(membership):
        raise TenantError(
            "C'est le dernier administrateur de cette entreprise. Nommez d'abord "
            "un autre administrateur."
        )
    user = membership.user
    user.is_active = active
    user.save(update_fields=["is_active"])
    return membership


@transaction.atomic
def remove_member(*, membership: Membership) -> str:
    """Retire une personne d'une entreprise. Le compte utilisateur subsiste :
    il peut appartenir à d'autres entreprises."""
    if _is_last_admin(membership):
        raise TenantError(
            "C'est le dernier administrateur de cette entreprise. Nommez d'abord "
            "un autre administrateur."
        )
    email = membership.user.email
    membership.delete()
    return email


def list_members_with_status(tenant: Tenant):
    return Membership.all_objects.filter(tenant=tenant).select_related("user").order_by("role")


def list_active_tenants():
    return Tenant.objects.filter(archived_at__isnull=True)


def list_archived_tenants():
    return Tenant.objects.filter(archived_at__isnull=False).select_related("archived_by")
