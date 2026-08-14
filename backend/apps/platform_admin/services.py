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
    *, actor, action: str, tenant=None, target: str = "", detail: str = "", ip_address: str = ""
) -> AdminAuditLog:
    return AdminAuditLog.objects.create(
        actor=actor,
        action=action,
        tenant=tenant,
        target=target[:200],
        detail=detail,
        ip_address=ip_address or None,
    )


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
    return {
        "keys": key_status(),
        "cti_mode": settings.BREACHSENSE_MODE,
        "caps": {
            "monitored_slots": settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE,
            "monthly_scans": settings.PLATFORM_MONTHLY_SCAN_CAP,
            "quota_safety_margin": settings.BREACHSENSE_QUOTA_SAFETY_MARGIN,
        },
        "retention": {
            "secret_days": settings.BREACH_SECRET_RETENTION_DAYS,
            "reveal_audit_days": settings.BREACH_REVEAL_AUDIT_RETENTION_DAYS,
        },
        "trial_days": settings.BILLING_TRIAL_DAYS,
    }
