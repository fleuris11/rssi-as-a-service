"""Public interface of the threat_intelligence app (Phase 7, ADR-013) —
other apps and Celery tasks must go through here, never import
``apps.threat_intelligence.models`` directly. Like apps.monitoring/
apps.ai_assistant, every function is given an already-resolved tenant/
asset and consistently uses ``all_objects`` with an explicit tenant
filter, since Celery tasks have no ambient request context.
"""

import logging
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Alert, Asset
from apps.tenants import services as tenants_services

from . import quota as quota_module
from .models import BreachFinding, BreachIntelligenceUsage, BreachScanJob, MonitoredAsset
from .providers import ProviderPoolFullError, get_provider
from .providers.base import RawFinding
from .providers.breachsense import normalizer

logger = logging.getLogger(__name__)

TriggeredBy = BreachIntelligenceUsage.TriggeredBy

SCAN_COOLDOWN_CACHE_KEY = "threat_intelligence:scan_cooldown:{tenant_id}"

# Un actif website/email_domain se traduit toujours en domaine côté
# Breachsense (ADR-013) — ni l'un ni l'autre type d'actif monitoring
# n'est une adresse email individuelle.
_SCANNABLE_ASSET_TYPES = {Asset.Type.WEBSITE, Asset.Type.EMAIL_DOMAIN}

_FINDING_SEVERITY_TO_ALERT_SEVERITY = {
    BreachFinding.Severity.CRITICAL: Alert.Severity.CRITICAL,
    BreachFinding.Severity.HIGH: Alert.Severity.CRITICAL,
    BreachFinding.Severity.ATTENTION: Alert.Severity.WARNING,
}


class ThreatIntelligenceError(Exception):
    """Base class for business-rule violations raised by this module."""


class CooldownActiveError(ThreatIntelligenceError):
    pass


class PoolFullError(ThreatIntelligenceError):
    pass


class AssetAlreadyMonitoredError(ThreatIntelligenceError):
    pass


class WebhookNotConfiguredError(ThreatIntelligenceError):
    pass


# --- Résolution actif -> domaine Breachsense --------------------------------


def derive_scan_domain(asset: Asset) -> str:
    if asset.type == Asset.Type.WEBSITE:
        return urlparse(asset.value).hostname or asset.value
    return asset.value


def tenant_member_emails(tenant) -> set[str]:
    return set(tenants_services.list_members(tenant).values_list("user__email", flat=True))


# --- Ingestion (partagée scan + webhook) ------------------------------------


def ingest_raw_findings(
    *, tenant, asset: Asset, raw_findings: list[RawFinding], tenant_emails: set[str] | None = None
) -> list[BreachFinding]:
    """Normalizes (masking secrets — ADR-014), deduplicates, persists, and
    opens/escalates the corresponding monitoring alert for every non-test
    raw finding. Used identically by the query scan path and the webhook
    path — the single place downstream of a provider that any finding
    passes through, so both are held to the same masking/dedup/alerting
    discipline."""
    tenant_emails = tenant_emails if tenant_emails is not None else tenant_member_emails(tenant)
    created: list[BreachFinding] = []

    for raw in raw_findings:
        if raw.is_test:
            logger.info(
                "Notification de test Breachsense reçue pour le tenant %s (endpoint %s) — ignorée.",
                tenant.id,
                raw.endpoint,
            )
            continue

        normalized = normalizer.normalize_finding(
            raw.endpoint, raw.payload, tenant_emails=tenant_emails
        )
        finding, was_created = BreachFinding.all_objects.get_or_create(
            tenant=tenant,
            dedup_hash=normalized["dedup_hash"],
            defaults={"asset": asset, **normalized},
        )
        if not was_created:
            continue

        created.append(finding)
        alert_severity = _FINDING_SEVERITY_TO_ALERT_SEVERITY[finding.severity]
        alert = monitoring_services.open_or_update_alert(
            asset=asset,
            alert_type=Alert.AlertType.BREACH_COMPROMISE,
            severity=alert_severity,
            details={
                "finding_id": finding.id,
                "finding_type": finding.finding_type,
                "source_endpoint": finding.source_endpoint,
                "severity": finding.severity,
            },
        )
        finding.alert = alert
        finding.save(update_fields=["alert"])

    return created


# --- Mode requête : scan de diagnostic --------------------------------------


def ensure_scan_cooldown_elapsed(tenant) -> None:
    key = SCAN_COOLDOWN_CACHE_KEY.format(tenant_id=tenant.id)
    if cache.get(key):
        raise CooldownActiveError(
            "Un scan Breachsense a déjà été lancé récemment pour cette entreprise. "
            f"Réessayez dans quelques heures (délai anti-abus : "
            f"{settings.BREACHSENSE_SCAN_COOLDOWN_HOURS}h)."
        )


def mark_scan_cooldown(tenant) -> None:
    key = SCAN_COOLDOWN_CACHE_KEY.format(tenant_id=tenant.id)
    cache.set(key, True, timeout=settings.BREACHSENSE_SCAN_COOLDOWN_HOURS * 3600)


def create_scan_job(*, tenant, asset: Asset | None = None, triggered_by: str) -> BreachScanJob:
    if triggered_by == TriggeredBy.MANUAL:
        ensure_scan_cooldown_elapsed(tenant)
    quota_module.QuotaManager().ensure_query_budget_available()
    return BreachScanJob.all_objects.create(tenant=tenant, asset=asset, triggered_by=triggered_by)


def get_scan_job(*, tenant, job_id):
    return BreachScanJob.all_objects.filter(tenant=tenant, id=job_id).first()


def mark_job_running(job: BreachScanJob) -> BreachScanJob:
    job.status = BreachScanJob.Status.RUNNING
    job.save(update_fields=["status"])
    return job


def mark_job_done(job: BreachScanJob, result_ref: dict | None = None) -> BreachScanJob:
    job.status = BreachScanJob.Status.DONE
    if result_ref:
        job.result_ref = {**job.result_ref, **result_ref}
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "result_ref", "finished_at"])
    return job


def mark_job_failed(job: BreachScanJob, error_message: str) -> BreachScanJob:
    job.status = BreachScanJob.Status.FAILED
    job.error_message = error_message
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error_message", "finished_at"])
    return job


def execute_scan(*, tenant, assets: list[Asset], triggered_by: str) -> dict:
    """Runs the actual provider query(ies) and ingestion for one or more
    assets, then records usage once for the whole batch. Called from
    inside the Celery task — never directly from a view (CLAUDE.md: pas
    d'appel réseau dans le cycle requête/réponse HTTP)."""
    provider = get_provider()
    manager = quota_module.QuotaManager()
    tenant_emails = tenant_member_emails(tenant)

    total_created = 0
    total_requests = 0
    for asset in assets:
        domain = derive_scan_domain(asset)
        scan_result = provider.scan_domain(domain)
        total_requests += scan_result.requests_consumed
        created = ingest_raw_findings(
            tenant=tenant,
            asset=asset,
            raw_findings=scan_result.findings,
            tenant_emails=tenant_emails,
        )
        total_created += len(created)

    manager.record_usage(
        tenant=tenant,
        endpoint="scan",
        requests_consumed=total_requests,
        remaining_after=manager.get_remaining(),
        triggered_by=triggered_by,
        findings_created=total_created,
    )
    if triggered_by == TriggeredBy.MANUAL:
        mark_scan_cooldown(tenant)

    return {"findings_created": total_created, "requests_consumed": total_requests}


def scannable_assets(tenant, *, asset: Asset | None = None) -> list[Asset]:
    if asset is not None:
        return [asset]
    return [
        a
        for a in monitoring_services.list_assets(tenant)
        if a.is_active and a.type in _SCANNABLE_ASSET_TYPES
    ]


# --- Mode webhook : monitoring continu --------------------------------------


def pool_capacity_remaining() -> int:
    used = MonitoredAsset.all_objects.filter(is_active=True).count()
    return max(0, settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE - used)


def pool_summary() -> dict:
    used = MonitoredAsset.all_objects.filter(is_active=True).count()
    return {
        "used": used,
        "capacity": settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE,
        "remaining": max(0, settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE - used),
    }


def list_monitored_assets(tenant):
    return MonitoredAsset.all_objects.filter(tenant=tenant, is_active=True).select_related("asset")


def register_monitored_asset(*, tenant, asset: Asset) -> MonitoredAsset:
    if asset.tenant_id != tenant.id:
        raise ThreatIntelligenceError("Cet actif n'appartient pas à cette entreprise.")
    if MonitoredAsset.all_objects.filter(asset=asset, is_active=True).exists():
        raise AssetAlreadyMonitoredError(
            "Cet actif est déjà surveillé en temps réel par Breachsense."
        )
    if not settings.BREACHSENSE_WEBHOOK_CALLBACK_URL:
        raise WebhookNotConfiguredError(
            "L'URL publique du webhook Breachsense n'est pas configurée sur cet environnement "
            "(disponible uniquement une fois la plateforme déployée)."
        )
    if pool_capacity_remaining() <= 0:
        raise PoolFullError(
            f"Le pool Breachsense de {settings.BREACHSENSE_MONITORED_ASSET_POOL_SIZE} actifs "
            "monitorés est complet. Retirez un actif existant avant d'en ajouter un nouveau."
        )

    provider = get_provider()
    domain = derive_scan_domain(asset)
    try:
        registration = provider.register_monitored_asset(asset_type="domain", value=domain)
    except ProviderPoolFullError as exc:
        raise PoolFullError(str(exc)) from exc

    return MonitoredAsset.all_objects.create(
        tenant=tenant,
        asset=asset,
        provider_ref=registration.provider_ref,
        provider_asset_type=registration.asset_type,
    )


def unregister_monitored_asset(monitored_asset: MonitoredAsset) -> None:
    provider = get_provider()
    provider.unregister_monitored_asset(monitored_asset.provider_ref)
    monitored_asset.is_active = False
    monitored_asset.save(update_fields=["is_active"])


def get_monitored_asset(*, tenant, asset_id):
    return MonitoredAsset.all_objects.filter(
        tenant=tenant, asset_id=asset_id, is_active=True
    ).first()


def resolve_monitored_asset_by_provider_ref(provider_ref: str) -> MonitoredAsset | None:
    """The one lookup in this module allowed to cross tenants without a
    resolved tenant context (like TenantScopingMiddleware resolving a
    tenant from a JWT) — the webhook has no JWT/X-Tenant-Id, Breachsense
    only tells us which asset (``ast``) a finding concerns."""
    return (
        MonitoredAsset.all_objects.filter(provider_ref=provider_ref, is_active=True)
        .select_related("tenant", "asset")
        .first()
    )


def ingest_webhook_payload(payload: list[dict]) -> dict:
    """Idempotent ingestion entry point for POST /api/v1/webhooks/breachsense
    (view layer only handles HTTP concerns — auth, parsing — this handles
    everything business-related)."""
    provider = get_provider()
    raw_findings = provider.normalize_webhook_payload(payload)

    by_asset_ref: dict[str, list[RawFinding]] = {}
    for raw in raw_findings:
        by_asset_ref.setdefault(raw.asset_ref, []).append(raw)

    total_created = 0
    unmatched_refs = []
    for asset_ref, findings in by_asset_ref.items():
        monitored = resolve_monitored_asset_by_provider_ref(asset_ref)
        if monitored is None:
            unmatched_refs.append(asset_ref)
            logger.warning(
                "Notification webhook Breachsense pour un actif non reconnu (ref=%s) — ignorée.",
                asset_ref,
            )
            continue
        created = ingest_raw_findings(
            tenant=monitored.tenant,
            asset=monitored.asset,
            raw_findings=findings,
            tenant_emails=tenant_member_emails(monitored.tenant),
        )
        total_created += len(created)

    return {"findings_created": total_created, "unmatched_refs": unmatched_refs}


# --- Findings : consultation & traitement -----------------------------------


def list_findings(tenant, *, status: str | None = None):
    qs = BreachFinding.all_objects.filter(tenant=tenant).select_related("asset")
    if status:
        qs = qs.filter(status=status)
    return qs


def get_finding(*, tenant, finding_id):
    return BreachFinding.all_objects.filter(tenant=tenant, id=finding_id).first()


def set_finding_status(finding: BreachFinding, *, status: str, user=None) -> BreachFinding:
    finding.status = status
    if status == BreachFinding.Status.TREATED:
        finding.treated_by = user
        finding.treated_at = timezone.now()
    finding.save(update_fields=["status", "treated_by", "treated_at"])
    return finding


def count_critical_open_findings(tenant) -> int:
    return BreachFinding.all_objects.filter(
        tenant=tenant, status=BreachFinding.Status.OPEN, severity=BreachFinding.Severity.CRITICAL
    ).count()
