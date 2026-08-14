"""Interface publique du back-office plateforme."""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from .models import AdminAuditLog

logger = logging.getLogger(__name__)


# --- Traçabilité ------------------------------------------------------------


def record_admin_action(
    *,
    actor,
    action: str,
    tenant=None,
    target: str = "",
    detail: str = "",
    ip_address: str = "",
    changes: dict | None = None,
) -> AdminAuditLog:
    return AdminAuditLog.objects.create(
        actor=actor,
        action=action,
        tenant=tenant,
        target=target[:200],
        detail=detail,
        changes=changes or {},
        ip_address=ip_address or None,
    )


def diff_fields(before: dict, after: dict) -> dict:
    """Champs réellement modifiés, sous la forme {"champ": [avant, après]}.

    Enregistrer l'objet entier noierait le changement dans le bruit ; ne rien
    enregistrer laisse un journal qui dit « modifié » sans dire quoi. On ne
    garde donc que les écarts, et on n'écrit aucune ligne d'audit s'il n'y en
    a aucun (une modification sans changement n'est pas un acte de gestion).
    """
    changed = {}
    for field, new_value in after.items():
        old_value = before.get(field)
        if old_value != new_value:
            changed[field] = [_auditable(old_value), _auditable(new_value)]
    return changed


def _auditable(value):
    """Rend une valeur sérialisable en JSON sans perdre son sens."""
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if value is None or isinstance(value, str | int | float | bool | list | dict):
        return value
    return str(value)


def list_admin_audit(limit: int = 100):
    return AdminAuditLog.objects.select_related("actor", "tenant")[:limit]


# --- Fiches clients ---------------------------------------------------------


def list_tenants_with_subscription():
    from django.db.models import IntegerField, OuterRef, Subquery

    from apps.tenants.models import Membership, Tenant

    # ``TenantScopedModel`` déclare sa clé étrangère avec ``related_name="+"``
    # : il n'existe donc aucune relation inverse à agréger depuis Tenant. On
    # compte par sous-requête plutôt qu'en bouclant — une liste de
    # back-office reste petite, mais un N+1 s'installe sans qu'on le revoie.
    member_count = (
        Membership.all_objects.filter(tenant=OuterRef("pk"))
        .order_by()
        .values("tenant")
        .annotate(total=Count("*"))
        .values("total")
    )

    return (
        Tenant.objects.select_related("subscription", "subscription__plan")
        .annotate(user_count=Subquery(member_count, output_field=IntegerField()))
        .order_by("name")
    )


def tenant_detail(tenant) -> dict:
    """Fiche client. Volontairement **sans aucune donnée de fuite** : ADR-014
    limite l'accès d'un administrateur plateforme aux tenants dont il est
    membre. L'administration gère des abonnements et des quotas, elle ne
    consulte pas les compromissions des clients — on n'affiche donc que des
    compteurs, jamais un contenu."""
    from apps.billing import entitlements
    from apps.monitoring.models import Asset
    from apps.tenants.models import Membership
    from apps.threat_intelligence.models import BreachFinding, MonitoredAsset

    subscription = entitlements.get_subscription(tenant)
    members = Membership.all_objects.filter(tenant=tenant).select_related("user")
    last_activity = (
        BreachFinding.all_objects.filter(tenant=tenant)
        .order_by("-detected_at")
        .values_list("detected_at", flat=True)
        .first()
    )

    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "sector": tenant.sector,
        "headcount": tenant.headcount,
        "is_active": tenant.is_active,
        "created_at": tenant.created_at,
        "last_activity_at": last_activity,
        "subscription": _subscription_dict(subscription),
        "usage": {
            "users": members.count(),
            "assets": Asset.all_objects.filter(tenant=tenant).count(),
            "monitored_assets": MonitoredAsset.all_objects.filter(
                tenant=tenant, is_active=True
            ).count(),
            "findings_total": BreachFinding.all_objects.filter(tenant=tenant).count(),
            "monthly_scans_used": entitlements.monthly_scans_used(tenant),
        },
        "members": [
            {
                "email": m.user.email,
                "name": m.user.get_full_name(),
                "role": m.role,
            }
            for m in members
        ],
    }


def _subscription_dict(subscription) -> dict | None:
    if subscription is None:
        return None
    return {
        "id": subscription.id,
        "plan_code": subscription.plan.code,
        "plan_name": subscription.plan.name,
        "status": subscription.status,
        "status_label": subscription.get_status_display(),
        "period": subscription.period,
        "is_operational": subscription.is_operational,
        "started_at": subscription.started_at,
        "trial_ends_at": subscription.trial_ends_at,
        "renews_at": subscription.renews_at,
        "quotas": {
            "monitored_assets": subscription.monitored_assets_quota,
            "monthly_scans": subscription.monthly_scans_quota,
            "max_users": subscription.max_users_quota,
        },
        "internal_notes": subscription.internal_notes,
    }


# --- Santé de la plateforme -------------------------------------------------


def _check(name: str, label: str, healthy: bool, detail: str = "") -> dict:
    return {"name": name, "label": label, "healthy": healthy, "detail": detail}


def platform_health() -> dict:
    """État des services, tâches planifiées et volumétrie.

    Chaque sonde est isolée dans son ``try`` : une brique en panne doit
    apparaître comme telle sans empêcher d'afficher l'état des autres — c'est
    précisément quand quelque chose casse qu'on ouvre cette page.
    """
    checks = []

    try:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks.append(_check("database", "Base de données", True))
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("database", "Base de données", False, str(exc)[:200]))

    try:
        from django.core.cache import cache

        cache.set("platform_health:ping", "1", timeout=10)
        healthy = cache.get("platform_health:ping") == "1"
        checks.append(_check("redis", "Redis (cache, files)", healthy))
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("redis", "Redis (cache, files)", False, str(exc)[:200]))

    try:
        from config.celery import app as celery_app

        pings = celery_app.control.ping(timeout=1.5) or []
        checks.append(
            _check(
                "celery_worker",
                "Celery worker",
                bool(pings),
                f"{len(pings)} worker(s) joignable(s)" if pings else "Aucun worker ne répond",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("celery_worker", "Celery worker", False, str(exc)[:200]))

    # Beat n'expose pas de ping : on déduit son activité d'une tâche planifiée
    # à haute fréquence (battement de cœur de la surveillance, toutes les
    # minutes). Sans exécution récente, beat est probablement arrêté.
    try:
        from apps.monitoring.models import CheckResult

        recent = CheckResult.all_objects.filter(
            checked_at__gte=timezone.now() - timedelta(minutes=30)
        ).exists()
        checks.append(
            _check(
                "celery_beat",
                "Celery beat (tâches planifiées)",
                recent,
                "Activité détectée sur les 30 dernières minutes"
                if recent
                else "Aucune exécution récente — beat est peut-être arrêté",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("celery_beat", "Celery beat", False, str(exc)[:200]))

    try:
        from apps.threat_intelligence.providers import get_provider

        provider = get_provider()
        checks.append(
            _check(
                "cti_provider",
                "Fournisseur de renseignement",
                True,
                f"{provider.__class__.__name__} (mode {settings.BREACHSENSE_MODE})",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("cti_provider", "Fournisseur de renseignement", False, str(exc)[:200]))

    checks.append(
        _check(
            "ai_provider",
            "Service d'analyse (IA)",
            bool(settings.ANTHROPIC_API_KEY),
            "Clé configurée" if settings.ANTHROPIC_API_KEY else "Aucune clé configurée",
        )
    )

    # Mêmes précautions que pour les sondes ci-dessus : une agrégation qui
    # échoue ne doit pas emporter toute la page de santé. Renvoyer une page
    # partielle avec une section en erreur vaut mieux qu'une 500 au moment
    # précis où l'on cherche à comprendre ce qui ne va pas.
    try:
        scheduled = scheduled_task_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("État des tâches planifiées indisponible", exc_info=True)
        scheduled = []
        checks.append(_check("scheduled_tasks", "Tâches planifiées", False, str(exc)[:200]))

    try:
        volumes = platform_volumes()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Volumétrie indisponible", exc_info=True)
        volumes = {}
        checks.append(_check("volumes", "Volumétrie", False, str(exc)[:200]))

    return {"checks": checks, "scheduled_tasks": scheduled, "volumes": volumes}


def scheduled_task_status() -> list[dict]:
    """Dernière exécution réussie observable de chaque tâche planifiée.

    Déduite de ses effets en base plutôt que d'un registre d'exécutions : la
    plateforme n'utilise pas django-celery-results, et l'effet est de toute
    façon un meilleur signal que le statut de la tâche (une tâche « réussie »
    qui n'a rien produit n'est pas une bonne nouvelle).
    """
    from apps.monitoring.models import CheckResult
    from apps.notifications.models import EmailLog
    from apps.threat_intelligence.models import BreachFinding

    def _last(queryset, field):
        return queryset.order_by(f"-{field}").values_list(field, flat=True).first()

    return [
        {
            "task": "Checks de surveillance",
            "schedule": "toutes les 5 minutes",
            "last_success_at": _last(CheckResult.all_objects.all(), "checked_at"),
        },
        {
            "task": "Météo cyber quotidienne",
            "schedule": "toutes les 15 minutes (envoi à l'heure choisie)",
            "last_success_at": _last(
                EmailLog.all_objects.filter(kind=EmailLog.Kind.WEATHER), "sent_at"
            ),
        },
        {
            "task": "Purge des secrets expirés",
            "schedule": "quotidienne (3 h 30)",
            "last_success_at": _last(
                BreachFinding.all_objects.filter(secret_purged_at__isnull=False),
                "secret_purged_at",
            ),
        },
    ]


def platform_volumes() -> dict:
    from apps.marketing.models import DemoRequest
    from apps.tenants.models import Tenant
    from apps.threat_intelligence.models import BreachFinding, SecretRevealAudit

    tenants = Tenant.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    return {
        "tenants_total": tenants["total"],
        "tenants_active": tenants["active"],
        "findings_total": BreachFinding.all_objects.count(),
        "reveals_total": SecretRevealAudit.all_objects.count(),
        "demo_requests_new": DemoRequest.objects.filter(status=DemoRequest.Status.NEW).count(),
    }


# --- Configuration technique ------------------------------------------------


def key_status() -> list[dict]:
    """État des clés de chiffrement — **jamais leur valeur**.

    On rapporte présence et validité de forme. L'ancienneté n'est pas
    disponible : une clé vit dans une variable d'environnement, qui ne porte
    pas de date. La renseigner supposerait un registre en base, c'est-à-dire
    stocker une métadonnée sur un secret dont on a fait le choix de ne rien
    stocker — signalé ici plutôt que simulé.
    """
    from cryptography.fernet import Fernet

    def _describe(name, label):
        raw = getattr(settings, name, "") or ""
        if not raw:
            return {"name": name, "label": label, "present": False, "valid": False}
        try:
            Fernet(raw.encode() if isinstance(raw, str) else raw)
            valid = True
        except Exception:  # noqa: BLE001
            valid = False
        return {"name": name, "label": label, "present": True, "valid": valid}

    keys = [
        _describe("AI_PSEUDONYMIZATION_KEY", "Pseudonymisation avant analyse externe"),
        _describe("TOTP_ENCRYPTION_KEY", "Secrets de double authentification"),
        _describe("BREACH_SECRET_ENCRYPTION_KEY", "Mots de passe fuités"),
    ]
    keys.append(
        {
            "name": "ANTHROPIC_API_KEY",
            "label": "Service d'analyse (IA)",
            "present": bool(settings.ANTHROPIC_API_KEY),
            "valid": bool(settings.ANTHROPIC_API_KEY),
        }
    )
    keys.append(
        {
            "name": "BREACHSENSE_LICENSE_KEY",
            "label": "Licence de renseignement",
            "present": bool(settings.BREACHSENSE_LICENSE_KEY),
            "valid": bool(settings.BREACHSENSE_LICENSE_KEY),
        }
    )
    return keys


def technical_configuration() -> dict:
    """État technique en LECTURE : ce qui n'est pas réglable depuis la console.

    Les plafonds et durées eux-mêmes sont désormais des réglages modifiables
    (``settings_registry``) ; ce qui reste ici est ce qui doit rester
    immuable depuis une interface web — la présence des clés, le mode du
    fournisseur de renseignement.
    """
    from . import settings_registry

    return {
        "keys": key_status(),
        "cti_mode": settings.BREACHSENSE_MODE,
        "caps": {
            "monitored_slots": settings_registry.get(settings_registry.MONITORED_SLOT_POOL),
            "monthly_scans": settings_registry.get(settings_registry.MONTHLY_SCAN_CAP),
            "quota_safety_margin": settings.BREACHSENSE_QUOTA_SAFETY_MARGIN,
        },
        "retention": {
            "secret_days": settings_registry.get(settings_registry.SECRET_RETENTION_DAYS),
            "reveal_audit_days": settings_registry.get(
                settings_registry.REVEAL_AUDIT_RETENTION_DAYS
            ),
        },
        "trial_days": settings_registry.get(settings_registry.TRIAL_DAYS),
    }


# --- Réglages d'exploitation (phase 11) -------------------------------------


def update_setting(*, key: str, raw_value, actor=None) -> tuple[object, list]:
    """Modifie un réglage. Renvoie (réglage, [avant, après]).

    La validation vit dans le registre, pas ici ni dans le sérialiseur : c'est
    la même règle qui doit s'appliquer que la valeur vienne de la console, d'un
    script de migration ou d'un test.
    """
    from . import settings_registry
    from .models import PlatformSetting

    spec = settings_registry.REGISTRY.get(key)
    if spec is None:
        raise settings_registry.SettingError(f"Réglage inconnu : {key}")

    before = settings_registry.get(key)
    value = settings_registry.coerce(spec, raw_value)

    setting, _created = PlatformSetting.objects.update_or_create(
        key=key, defaults={"value": value, "updated_by": actor}
    )
    settings_registry.invalidate_cache()
    return setting, [before, value]


def reset_setting(*, key: str) -> None:
    """Revient à la valeur du fichier d'environnement."""
    from . import settings_registry
    from .models import PlatformSetting

    PlatformSetting.objects.filter(key=key).delete()
    settings_registry.invalidate_cache()


def capacity_setting_warning(*, key: str, new_value) -> str:
    """Avertissement à afficher AVANT d'appliquer une baisse de plafond.

    Baisser le pool en dessous de ce qui est déjà engagé ne retire rien aux
    clients en cours — les gardes refusent les nouvelles activations, elles ne
    résilient personne. Le dire explicitement évite deux erreurs opposées :
    croire que la baisse est sans effet, ou croire qu'elle coupe des clients.
    """
    from apps.billing import capacity

    from . import settings_registry

    if key != settings_registry.MONITORED_SLOT_POOL:
        return ""
    committed = capacity.projected_monitored_slots(additional=0)
    if int(new_value) >= committed:
        return ""
    return (
        f"{committed} emplacements sont déjà engagés auprès de vos clients, soit plus "
        f"que le nouveau plafond de {new_value}. Aucun client ne perdra sa surveillance : "
        "les engagements en cours sont honorés. En revanche, aucune nouvelle activation "
        "ne sera possible tant que l'engagement dépassera le plafond."
    )


# --- Administrateurs de la plateforme ---------------------------------------


class AdminManagementError(Exception):
    """Violation d'une règle de gestion des administrateurs."""


def list_platform_admins():
    from django.contrib.auth import get_user_model

    from .models import PlatformAdminProfile

    User = get_user_model()
    admins = User.objects.filter(is_staff=True).select_related("platform_admin").order_by("email")
    rows = []
    for user in admins:
        profile = getattr(user, "platform_admin", None)
        rows.append(
            {
                "id": str(user.id),
                "email": user.email,
                "name": user.get_full_name(),
                "is_active": user.is_active,
                # Sans profil = niveau complet : c'est le cas du fondateur et
                # des comptes antérieurs à la phase 11, qui ne doivent pas
                # perdre leurs droits au déploiement de cette migration.
                "level": (
                    profile.level if profile else PlatformAdminProfile.Level.FULL
                ),
                "level_label": (
                    profile.get_level_display()
                    if profile
                    else PlatformAdminProfile.Level.FULL.label
                ),
                "has_usable_password": user.has_usable_password(),
                "last_login": user.last_login,
            }
        )
    return rows


def _count_full_admins(exclude_user_id=None) -> int:
    from django.contrib.auth import get_user_model

    from .models import PlatformAdminProfile

    User = get_user_model()
    queryset = User.objects.filter(is_staff=True, is_active=True)
    if exclude_user_id is not None:
        queryset = queryset.exclude(id=exclude_user_id)
    total = 0
    for user in queryset.select_related("platform_admin"):
        profile = getattr(user, "platform_admin", None)
        if profile is None or profile.level == PlatformAdminProfile.Level.FULL:
            total += 1
    return total


def invite_platform_admin(*, email: str, level: str, actor=None):
    """Crée (ou promeut) un administrateur et émet son lien d'accès.

    Renvoie ``(user, jeton en clair)``. Comme pour un utilisateur client,
    aucun mot de passe n'est choisi ni transmis par l'invitant.
    """
    from django.contrib.auth import get_user_model

    from apps.accounts.models import AccessInvitation
    from apps.accounts.services import create_access_invitation

    from .models import PlatformAdminProfile

    email = (email or "").strip().lower()
    if not email:
        raise AdminManagementError("L'adresse email est obligatoire.")
    if level not in PlatformAdminProfile.Level.values:
        raise AdminManagementError("Niveau d'administration inconnu.")

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create_user(email=email, password=None)
        user.set_unusable_password()
        user.is_active = False

    user.is_staff = True
    user.save()

    PlatformAdminProfile.objects.update_or_create(
        user=user, defaults={"level": level, "invited_by": actor}
    )

    _invitation, raw_token = create_access_invitation(
        user=user, purpose=AccessInvitation.Purpose.INVITATION, actor=actor
    )
    return user, raw_token


def change_admin_level(*, user, level: str, actor=None):
    from .models import PlatformAdminProfile

    if level not in PlatformAdminProfile.Level.values:
        raise AdminManagementError("Niveau d'administration inconnu.")
    if actor is not None and user.id == actor.id:
        # Se rétrograder soi-même est le moyen le plus simple de se retrouver
        # sans personne pour revenir en arrière.
        raise AdminManagementError("Vous ne pouvez pas modifier votre propre niveau.")
    if level != PlatformAdminProfile.Level.FULL and _count_full_admins(exclude_user_id=user.id) == 0:
        raise AdminManagementError(
            "C'est le dernier administrateur complet. Nommez-en un autre avant de "
            "rétrograder celui-ci."
        )

    profile, _created = PlatformAdminProfile.objects.update_or_create(
        user=user, defaults={"level": level}
    )
    return profile


def revoke_platform_admin(*, user, actor=None) -> str:
    """Retire les droits d'administration. Le compte subsiste : la personne
    peut être membre d'une entreprise cliente par ailleurs."""
    if actor is not None and user.id == actor.id:
        raise AdminManagementError("Vous ne pouvez pas retirer vos propres droits.")
    if _count_full_admins(exclude_user_id=user.id) == 0:
        raise AdminManagementError(
            "C'est le dernier administrateur complet : le retirer rendrait la console "
            "inaccessible. Nommez-en un autre d'abord."
        )

    from .models import PlatformAdminProfile

    email = user.email
    user.is_staff = False
    user.is_superuser = False
    user.save(update_fields=["is_staff", "is_superuser"])
    PlatformAdminProfile.objects.filter(user=user).delete()
    return email


# --- Recherche globale ------------------------------------------------------


def global_search(query: str, *, limit: int = 8) -> dict:
    """Une seule barre pour retrouver une entreprise, une personne ou un
    prospect. Sans elle, retrouver un client se fait en parcourant une liste
    triée par nom — praticable à dix clients, plus à cent."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    from apps.marketing.models import DemoRequest
    from apps.tenants.models import Membership, Tenant

    query = (query or "").strip()
    if len(query) < 2:
        return {"tenants": [], "users": [], "prospects": [], "query": query}

    User = get_user_model()

    tenants = Tenant.objects.filter(
        Q(name__icontains=query)
        | Q(slug__icontains=query)
        | Q(contact_email__icontains=query)
        | Q(website__icontains=query)
    ).select_related("subscription", "subscription__plan")[:limit]

    users = User.objects.filter(
        Q(email__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)
    )[:limit]

    prospects = DemoRequest.objects.filter(
        Q(company__icontains=query) | Q(full_name__icontains=query) | Q(email__icontains=query)
    )[:limit]

    user_tenants = {
        membership.user_id: membership.tenant
        for membership in Membership.all_objects.filter(user__in=users).select_related("tenant")
    }

    return {
        "query": query,
        "tenants": [
            {
                "id": str(t.id),
                "name": t.name,
                "archived": t.is_archived,
                "plan_name": getattr(getattr(t, "subscription", None), "plan", None)
                and t.subscription.plan.name,
            }
            for t in tenants
        ],
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.get_full_name(),
                "is_active": u.is_active,
                "is_staff": u.is_staff,
                "tenant_id": str(user_tenants[u.id].id) if u.id in user_tenants else None,
                "tenant_name": user_tenants[u.id].name if u.id in user_tenants else "",
            }
            for u in users
        ],
        "prospects": [
            {
                "id": p.id,
                "company": p.company,
                "full_name": p.full_name,
                "email": p.email,
                "status": p.status,
                "status_label": p.get_status_display(),
            }
            for p in prospects
        ],
    }


# --- Exports ----------------------------------------------------------------


def export_rows(kind: str) -> tuple[list[str], list[list]]:
    """En-têtes et lignes d'un export CSV. Le formatage CSV lui-même reste
    dans la vue : ce service produit des données, pas un fichier."""
    from apps.billing.models import Subscription
    from apps.marketing.models import DemoRequest
    from apps.tenants.models import Tenant

    if kind == "tenants":
        headers = [
            "Entreprise",
            "Secteur",
            "Effectif",
            "Email de contact",
            "Téléphone",
            "Référent",
            "Offre",
            "État",
            "Créée le",
            "Archivée",
        ]
        rows = []
        for tenant in Tenant.objects.select_related(
            "subscription", "subscription__plan"
        ).order_by("name"):
            subscription = getattr(tenant, "subscription", None)
            rows.append(
                [
                    tenant.name,
                    tenant.sector,
                    tenant.headcount or "",
                    tenant.contact_email,
                    tenant.contact_phone,
                    tenant.account_manager,
                    subscription.plan.name if subscription else "",
                    subscription.get_status_display() if subscription else "Aucun abonnement",
                    tenant.created_at.date().isoformat(),
                    "oui" if tenant.is_archived else "non",
                ]
            )
        return headers, rows

    if kind == "prospects":
        headers = [
            "Entreprise",
            "Contact",
            "Fonction",
            "Email",
            "Téléphone",
            "Taille",
            "Statut",
            "Motif de perte",
            "Relance prévue",
            "Origine",
            "Reçue le",
        ]
        rows = [
            [
                p.company,
                p.full_name,
                p.role,
                p.email,
                p.phone,
                p.get_company_size_display() or "",
                p.get_status_display(),
                p.lost_reason,
                p.next_follow_up_on.isoformat() if p.next_follow_up_on else "",
                p.get_source_display(),
                p.created_at.date().isoformat(),
            ]
            for p in DemoRequest.objects.all().order_by("-created_at")
        ]
        return headers, rows

    if kind == "subscriptions":
        headers = [
            "Entreprise",
            "Offre",
            "État",
            "Périodicité",
            "Emplacements",
            "Analyses/mois",
            "Utilisateurs",
            "Début",
            "Fin d'essai",
            "Renouvellement",
        ]
        rows = [
            [
                s.tenant.name,
                s.plan.name,
                s.get_status_display(),
                s.get_period_display(),
                s.monitored_assets_quota,
                s.monthly_scans_quota,
                s.max_users_quota,
                s.started_at.date().isoformat() if s.started_at else "",
                s.trial_ends_at.date().isoformat() if s.trial_ends_at else "",
                s.renews_at.date().isoformat() if s.renews_at else "",
            ]
            for s in Subscription.objects.select_related("tenant", "plan").order_by("tenant__name")
        ]
        return headers, rows

    raise ValueError(f"Export inconnu : {kind}")
