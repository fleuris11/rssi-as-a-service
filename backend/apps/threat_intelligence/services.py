"""Public interface of the threat_intelligence app (Phase 7, ADR-013) —
other apps and Celery tasks must go through here, never import
``apps.threat_intelligence.models`` directly. Like apps.monitoring/
apps.ai_assistant, every function is given an already-resolved tenant/
asset and consistently uses ``all_objects`` with an explicit tenant
filter, since Celery tasks have no ambient request context.
"""

import hashlib
import logging
from datetime import timedelta
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.accounts import services as accounts_services
from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Alert, Asset
from apps.tenants import services as tenants_services

from . import correlation, exposure, plain_language
from . import quota as quota_module
from .models import (
    BreachFinding,
    BreachIntelligenceUsage,
    BreachScanJob,
    ExposureSynthesis,
    MonitoredAsset,
    SecretPurgeRun,
    SecretRevealAudit,
)
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


# --- Chiffrement des secrets de fuite (ADR-014, mise à jour) ----------------
#
# Clé dédiée (BREACH_SECRET_ENCRYPTION_KEY), distincte de TOTP_ENCRYPTION_KEY
# et AI_PSEUDONYMIZATION_KEY — même principe de séparation des clés Fernet
# que le reste du projet (apps.accounts.services._fernet,
# apps.ai_assistant.services._fernet) : compromettre l'une ne doit pas
# compromettre les autres.


# Rotation (Phase 8C) : MultiFernet. La PREMIÈRE clé de la liste chiffre ;
# toutes les clés de la liste déchiffrent. Ajouter une nouvelle clé en tête
# permet donc de tourner sans coupure — les secrets déjà en base restent
# lisibles avec l'ancienne clé le temps que la commande de rotation les
# re-chiffre. Voir `rotate_breach_secret_key` et le README de l'app.


def _encryption_keys() -> list[str]:
    """Clés actives, de la plus récente à la plus ancienne. Accepte l'ancienne
    forme (une seule clé dans ``BREACH_SECRET_ENCRYPTION_KEY``) pour qu'un
    déploiement existant continue de fonctionner sans changement de config."""
    keys = [k for k in getattr(settings, "BREACH_SECRET_ENCRYPTION_KEYS", []) if k]
    if keys:
        return keys
    single = settings.BREACH_SECRET_ENCRYPTION_KEY
    return [single] if single else []


def _fernet() -> MultiFernet:
    keys = _encryption_keys()
    if not keys:
        raise ThreatIntelligenceError(
            "BREACH_SECRET_ENCRYPTION_KEY n'est pas configurée : impossible de chiffrer un "
            "secret de fuite."
        )
    try:
        return MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])
    except (ValueError, TypeError) as exc:
        raise ThreatIntelligenceError(
            "Clé de chiffrement des secrets de fuite invalide (format Fernet attendu)."
        ) from exc


def encrypt_secret(secret_plain: str) -> bytes:
    if not secret_plain:
        return b""
    return _fernet().encrypt(secret_plain.encode())


def decrypt_secret(encrypted: bytes) -> str:
    try:
        return _fernet().decrypt(bytes(encrypted)).decode()
    except InvalidToken as exc:
        raise ThreatIntelligenceError(
            "Secret de fuite illisible (clé de chiffrement invalide ou donnée corrompue)."
        ) from exc


def rotate_secret_ciphertext(encrypted: bytes) -> bytes:
    """Re-chiffre un blob avec la clé courante sans jamais exposer le clair
    en dehors de cet appel (``MultiFernet.rotate`` déchiffre et rechiffre en
    une opération). Traduit l'exception de la librairie en erreur métier,
    comme ``decrypt_secret`` : l'appelant (commande de rotation) ne doit pas
    avoir à connaître `cryptography` pour distinguer un secret illisible
    d'une panne."""
    try:
        return _fernet().rotate(bytes(encrypted))
    except InvalidToken as exc:
        raise ThreatIntelligenceError(
            "Secret de fuite illisible avec les clés configurées : rotation impossible."
        ) from exc


# --- Révélation privilégiée (ADR-014, mise à jour) --------------------------
#
# Ré-authentification fraîche à chaque révélation (« step-up ») : l'appelant
# doit re-fournir son mot de passe de compte OU un code TOTP valide dans la
# requête elle-même — jamais une session/élévation mise en cache, pour que
# chaque révélation exige une preuve fraîche, pas seulement un token d'accès
# déjà en poche (qui pourrait être volé sans que le mot de passe/2FA le
# soient).


def verify_step_up(*, user, password: str = "", totp_code: str = "") -> bool:
    if password:
        return user.check_password(password)
    if totp_code:
        credential = accounts_services.get_confirmed_credential(user)
        return bool(credential and accounts_services.verify_totp_code(credential, totp_code))
    return False


def record_reveal_attempt(
    *,
    tenant,
    finding: BreachFinding | None,
    user,
    success: bool,
    denial_reason: str = "",
    ip_address: str = "",
    user_agent: str = "",
) -> SecretRevealAudit:
    """Traces every reveal attempt — granted or denied, for every denial
    reason — never the secret itself (the model has no field for it)."""
    return SecretRevealAudit.all_objects.create(
        tenant=tenant,
        finding=finding,
        user=user,
        success=success,
        denial_reason=denial_reason,
        ip_address=ip_address or None,
        user_agent=user_agent[:255],
    )


def list_reveal_audits(tenant):
    return SecretRevealAudit.all_objects.filter(tenant=tenant).select_related("finding", "user")


def list_reveal_audits_all_tenants(limit: int = 100):
    """Platform back-office (ADR-014 update): the reveal audit trail — who
    attempted to reveal what, when, granted or denied — is aggregate enough
    (no secret, no raw finding detail) to be shown platform-wide, unlike
    BreachFinding detail itself (see ThreatIntelligenceAdminStatusView)."""
    return SecretRevealAudit.all_objects.select_related("tenant", "finding", "user").order_by(
        "-created_at"
    )[:limit]


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
        # Popped immediately, never logged, never passed to create() as-is
        # (BreachFinding has no such field) — encrypted in memory right
        # here, the one hop between the normalizer and the encrypted
        # column (ADR-014 update).
        secret_plain = normalized.pop("secret_plain", "")
        normalized["secret_encrypted"] = encrypt_secret(secret_plain) if secret_plain else b""
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

    if created:
        # L'analyse en cache décrit un état des fuites qui vient de changer.
        mark_synthesis_stale(tenant)

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
        _notify_pre_incident_signals(created)

    return {"findings_created": total_created, "unmatched_refs": unmatched_refs}


def _notify_pre_incident_signals(findings: list[BreachFinding]) -> None:
    """Pushes a "signal avant-coureur" email for webhook-delivered radar/
    darkweb/attack-surface findings (Phase 8A). Deliberately webhook-only:
    a diagnostic scan surfaces a whole backlog of pre-existing signals at
    once, and mailing all of them would be noise — the value of this
    notification is that something *changed* in the tenant's public exposure
    just now. Import is deferred (like apps.monitoring.tasks does) to keep
    the notifications -> threat_intelligence dependency one-way at import
    time."""
    pre_incident = [f for f in findings if f.source_endpoint in PRE_INCIDENT_ENDPOINTS]
    if not pre_incident:
        return
    from apps.notifications.tasks import send_pre_incident_signal_email

    for finding in pre_incident:
        try:
            send_pre_incident_signal_email.delay(finding.id)
        except Exception:  # noqa: BLE001 - l'ingestion ne doit jamais échouer à cause de l'email
            logger.warning(
                "Impossible de planifier la notification de signal avant-coureur pour %s",
                finding.id,
                exc_info=True,
            )


# --- Findings : consultation & traitement -----------------------------------


def list_findings(tenant, *, status: str | None = None, include_pre_incident: bool = False):
    """Fuites **avérées** du tenant. Depuis la Phase 8B, les signaux
    pré-incident (radar/dark web/surface d'attaque) en sont exclus par
    défaut : ils vivent dans la carte « Signaux avant-coureurs », qui porte
    désormais ses propres actions de traitement. Mélanger les deux dans une
    même liste affichait deux fois la même chose et diluait la distinction
    entre « ça a fuité » et « on surveille ».

    ``include_pre_incident=True`` reste disponible pour les usages qui ont
    besoin de la vue complète — notamment le fil d'exposition et les
    contextes IA/météo, où l'utilisateur ne lit pas une liste mais une
    synthèse par actif.
    """
    qs = BreachFinding.all_objects.filter(tenant=tenant).select_related("asset")
    if not include_pre_incident:
        qs = qs.exclude(source_endpoint__in=PRE_INCIDENT_ENDPOINTS)
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
    # Traiter une fuite change le score et donc la lecture d'ensemble.
    mark_synthesis_stale(finding.tenant)
    return finding


def count_critical_open_findings(tenant) -> int:
    return BreachFinding.all_objects.filter(
        tenant=tenant, status=BreachFinding.Status.OPEN, severity=BreachFinding.Severity.CRITICAL
    ).count()


# --- Radar pré-incident (Phase 8A) ------------------------------------------
#
# Un signal "avant-coureur" est une observation sur l'exposition PUBLIQUE du
# tenant (domaine ressemblant déposé, mention sur un forum, surface d'attaque)
# — pas le constat qu'une donnée a fuité. La distinction est produit, pas
# cosmétique : elle change ce que le dirigeant doit faire (surveiller /
# prévenir ses équipes) et le ton du message (« rien n'a encore fuité »).

PRE_INCIDENT_ENDPOINTS = (
    BreachFinding.SourceEndpoint.RADAR,
    BreachFinding.SourceEndpoint.DARKWEB,
    BreachFinding.SourceEndpoint.ASM,
)

# Nature du signal -> (libellé, explication grand public, urgence).
# L'explication est délibérément en une phrase, sans jargon : c'est ce que
# lit un dirigeant de TPE/PME, pas un analyste.
SIGNAL_TYPOSQUAT = "typosquat"
SIGNAL_DARKWEB = "darkweb"
SIGNAL_PUBLIC_MENTION = "public_mention"
SIGNAL_ATTACK_SURFACE = "attack_surface"

_SIGNAL_DEFINITIONS = {
    SIGNAL_TYPOSQUAT: {
        "label": "Nom de domaine imitant le vôtre",
        "plain_language": (
            "Quelqu'un a déposé une adresse internet très proche de la vôtre — c'est souvent "
            "le préparatif d'un faux email demandant un virement ou un mot de passe. Prévenez "
            "vos équipes (surtout la comptabilité) de vérifier l'adresse exacte de l'expéditeur."
        ),
        "urgency": "high",
    },
    SIGNAL_DARKWEB: {
        "label": "Mention sur le dark web",
        "plain_language": (
            "Le nom de votre entreprise a été repéré dans un espace fréquenté par des attaquants. "
            "Rien n'indique qu'une donnée a fuité, mais cela peut signaler un intérêt pour vous : "
            "c'est le bon moment pour vérifier vos sauvegardes et la double authentification."
        ),
        "urgency": "high",
    },
    SIGNAL_PUBLIC_MENTION: {
        "label": "Mention publique repérée",
        "plain_language": (
            "Votre entreprise a été mentionnée publiquement dans un espace surveillé. C'est une "
            "information de veille : à connaître, sans action urgente de votre part."
        ),
        "urgency": "info",
    },
    SIGNAL_ATTACK_SURFACE: {
        "label": "Élément exposé sur internet",
        "plain_language": (
            "Un élément technique de votre entreprise est visible publiquement sur internet. "
            "C'est normal pour la plupart des services, mais cela fait partie de ce qu'un "
            "attaquant regarde en premier — à garder à jour."
        ),
        "urgency": "info",
    },
}


def classify_pre_incident_signal(finding: BreachFinding) -> str:
    """Maps a finding onto the nature of the *signal* it represents, which
    doesn't map 1:1 onto ``source_endpoint``: ``radar`` covers both a
    look-alike domain registration (actionable, high urgency) and a plain
    public mention (informational), and only the phishing sub-type of
    ``asm`` is a real pre-incident signal rather than inventory."""
    if finding.source_endpoint == BreachFinding.SourceEndpoint.DARKWEB:
        return SIGNAL_DARKWEB
    if finding.source_endpoint == BreachFinding.SourceEndpoint.ASM:
        return (
            SIGNAL_TYPOSQUAT
            if finding.finding_type == normalizer.ASM_PHISHING_TYPE
            else SIGNAL_ATTACK_SURFACE
        )
    # radar : un domaine ressemblant déposé est un signal de préparation
    # d'attaque, pas une simple mention — distingué par la sévérité "élevée"
    # calculée à l'ingestion, ou par la source annoncée par le fournisseur.
    source = str(finding.raw_data.get("src", "")).lower()
    if "domaine" in source or "domain" in source:
        return SIGNAL_TYPOSQUAT
    return SIGNAL_PUBLIC_MENTION


def list_pre_incident_findings(tenant, *, status: str = BreachFinding.Status.OPEN):
    """Defaults to OPEN: a signal the tenant has already treated/ignored
    shouldn't keep shouting at them from the top of the page. Passing another
    status backs the « Voir les signaux traités » history view (Phase 8B) —
    the card now carries the treat/ignore actions, so treated signals need
    somewhere to still be consultable."""
    qs = BreachFinding.all_objects.filter(tenant=tenant, source_endpoint__in=PRE_INCIDENT_ENDPOINTS)
    if status:
        qs = qs.filter(status=status)
    return qs.select_related("asset").order_by("-detected_at")


def build_pre_incident_summary(tenant, *, status: str = BreachFinding.Status.OPEN) -> dict:
    """Groups the tenant's pre-incident findings by signal nature, each with
    its plain-language explanation and urgency — the shape the "Signaux
    avant-coureurs" card renders directly."""
    groups: dict[str, list] = {}
    for finding in list_pre_incident_findings(tenant, status=status):
        groups.setdefault(classify_pre_incident_signal(finding), []).append(finding)

    signals = []
    for signal_type, definition in _SIGNAL_DEFINITIONS.items():
        findings = groups.get(signal_type, [])
        if not findings:
            continue
        signals.append(
            {
                "signal_type": signal_type,
                "label": definition["label"],
                "plain_language": definition["plain_language"],
                "urgency": definition["urgency"],
                "count": len(findings),
                "items": [
                    {
                        "id": finding.id,
                        "asset_value": finding.asset.value,
                        "detail": pre_incident_detail(finding),
                        "detected_at": finding.detected_at,
                        "breach_date": finding.breach_date,
                    }
                    for finding in findings
                ],
            }
        )

    return {"signals": signals, "total": sum(s["count"] for s in signals)}


def pre_incident_detail(finding: BreachFinding) -> str:
    """The one concrete observed value worth showing (the look-alike domain,
    the mentioned domain) — read from the already-masked ``raw_data``, never
    from anything sensitive."""
    for key in ("dom", "data", "cname"):
        value = finding.raw_data.get(key)
        if value:
            return str(value)
    return finding.asset.value


def pre_incident_definition(signal_type: str) -> dict:
    """Label/vulgarisation/urgence for one signal nature — the single source
    of truth shared by the API and the notification email, so the wording a
    tenant reads is identical in both places."""
    return _SIGNAL_DEFINITIONS[signal_type]


# --- Fil d'exposition (Phase 8B) --------------------------------------------
#
# La vue principale du produit : « le médecin, pas la chemise de résultats ».
# On ne montre plus une liste plate de fuites, mais les actifs du tenant
# classés par exposition, chacun avec un score explicable et, pour chaque
# fuite, ce que ça veut dire et ce qu'il faut faire.


def serialize_finding_for_feed(finding: BreachFinding, reuse_signals: list | None = None) -> dict:
    explanation = plain_language.explain(finding)
    reuse_signals = reuse_signals or []
    action = explanation["action"]
    if reuse_signals:
        # C'est ici que la révélation prend son sens : une réutilisation
        # possible est une hypothèse, et le mot de passe permet de la lever.
        action = f"{action} {correlation.recommended_verification(finding)}"
    return {
        "id": finding.id,
        "source_endpoint": finding.source_endpoint,
        "source_label": finding.get_source_endpoint_display(),
        "finding_type": finding.finding_type,
        "severity": finding.severity,
        "severity_label": finding.get_severity_display(),
        "identifier": finding.identifier_plain or finding.identifier_masked,
        "secret_masked": finding.secret_masked,
        "has_secret": finding.has_secret,
        "secret_purged_at": finding.secret_purged_at,
        "breach_date": finding.breach_date,
        "detected_at": finding.detected_at,
        # Vulgarisation déterministe (Tâche 2) : immédiate, sans appel IA.
        "meaning": explanation["meaning"],
        "recommended_action": action,
        "reuse_signals": reuse_signals,
    }


def build_exposure_feed(tenant) -> dict:
    """Fuites ouvertes groupées par actif, chaque groupe portant son score
    d'exposition et ses composantes, groupes triés par score décroissant.

    Inclut les signaux pré-incident (``include_pre_incident=True``) : ici on
    ne lit pas une liste mais l'exposition d'un actif, et un domaine
    ressemblant déposé fait bien partie de son exposition — la séparation
    liste/carte de la Tâche 0 est une distinction d'affichage, pas de fond.
    """
    findings = list(
        list_findings(
            tenant, status=BreachFinding.Status.OPEN, include_pre_incident=True
        ).select_related("asset")
    )

    # Corrélation calculée sur l'ENSEMBLE des fuites du tenant, pas par actif :
    # une réutilisation possible se voit précisément quand le même identifiant
    # traverse plusieurs actifs (ADR-017).
    assets = list(monitoring_services.list_assets(tenant))
    reuse_by_finding = correlation.correlate(
        findings, tenant_emails=tenant_member_emails(tenant), assets=assets
    )

    by_asset: dict[int, list[BreachFinding]] = {}
    for finding in findings:
        by_asset.setdefault(finding.asset_id, []).append(finding)

    groups = []
    for asset_findings in by_asset.values():
        asset = asset_findings[0].asset
        score = exposure.compute_exposure_score(asset_findings)
        asset_findings.sort(key=exposure.freshness_sort_key)
        serialized = [
            serialize_finding_for_feed(f, reuse_by_finding.get(f.id)) for f in asset_findings
        ]
        groups.append(
            {
                "asset_id": asset.id,
                "asset_value": asset.value,
                "asset_type_label": asset.get_type_display(),
                **score.as_dict(),
                "findings": serialized,
                # Section dédiée de la carte de l'actif : la synthèse des
                # réutilisations possibles qui le concernent.
                "reuse_signals": [signal for f in serialized for signal in f["reuse_signals"]],
            }
        )

    # Score décroissant, puis nombre de fuites — deux actifs à score égal se
    # départagent par le volume, pour un ordre stable d'un appel à l'autre.
    groups.sort(key=lambda g: (-g["score"], -g["findings_count"], g["asset_value"]))

    return {
        "assets": groups,
        "total_findings": len(findings),
        "highest_score": groups[0]["score"] if groups else 0,
        "retention_policy": retention_policy(),
    }


# --- Synthèse IA d'exposition (Phase 8B, tâche 4) ---------------------------
#
# Couche AU-DESSUS du fil d'exposition : la page est complète sans elle. Elle
# est mise en cache (un appel IA coûte du quota) et marquée obsolète dès
# qu'une fuite est créée ou change de statut — plutôt que supprimée, pour
# pouvoir afficher « cette analyse date d'avant vos dernières actions » au
# lieu de faire disparaître le bandeau sans explication.


def findings_fingerprint(tenant) -> str:
    """Empreinte de l'état des fuites ouvertes : si elle n'a pas changé,
    régénérer produirait la même analyse pour le même coût en tokens."""
    rows = (
        BreachFinding.all_objects.filter(tenant=tenant, status=BreachFinding.Status.OPEN)
        .order_by("id")
        .values_list("id", "status")
    )
    payload = "|".join(f"{finding_id}:{status}" for finding_id, status in rows)
    return hashlib.sha256(payload.encode()).hexdigest()


def get_exposure_synthesis(tenant) -> ExposureSynthesis | None:
    return ExposureSynthesis.all_objects.filter(tenant=tenant).first()


def mark_synthesis_stale(tenant) -> None:
    """Appelée à chaque création de fuite et à chaque changement de statut."""
    ExposureSynthesis.all_objects.filter(tenant=tenant, is_stale=False).update(is_stale=True)


def synthesis_cooldown_active(tenant) -> bool:
    synthesis = get_exposure_synthesis(tenant)
    if synthesis is None:
        return False
    cooldown = timedelta(minutes=settings.EXPOSURE_SYNTHESIS_COOLDOWN_MINUTES)
    return timezone.now() - synthesis.generated_at < cooldown


def save_exposure_synthesis(tenant, content: str) -> ExposureSynthesis:
    synthesis, _created = ExposureSynthesis.all_objects.update_or_create(
        tenant=tenant,
        defaults={
            "content": content,
            "is_stale": False,
            "findings_fingerprint": findings_fingerprint(tenant),
        },
    )
    return synthesis


# --- Purge des secrets à échéance (Phase 8C, ADR-014) -----------------------
#
# On purge le SECRET, pas la fuite. Supprimer le BreachFinding ferait perdre
# l'historique de conformité (« cette fuite a été traitée le … »), qui est
# précisément ce qu'un tenant doit pouvoir montrer. Seule la valeur
# récupérable expire.


def purge_expired_secrets(*, now=None) -> SecretPurgeRun:
    """Efface les secrets chiffrés au-delà du délai de rétention, sur tous les
    tenants. Idempotente : une seconde exécution ne trouve plus rien à purger
    (le filtre porte sur ``has_secret=True``), et ``secret_purged_at`` n'est
    donc jamais réécrit."""
    now = now or timezone.now()
    retention_days = settings.BREACH_SECRET_RETENTION_DAYS
    cutoff = now - timedelta(days=retention_days)

    expired = BreachFinding.all_objects.filter(has_secret=True, detected_at__lt=cutoff)
    secrets_purged = expired.update(secret_encrypted=b"", has_secret=False, secret_purged_at=now)

    audit_cutoff = now - timedelta(days=settings.BREACH_REVEAL_AUDIT_RETENTION_DAYS)
    reveal_audits_deleted, _details = SecretRevealAudit.all_objects.filter(
        created_at__lt=audit_cutoff
    ).delete()

    run = SecretPurgeRun.objects.create(
        retention_days=retention_days,
        secrets_purged=secrets_purged,
        reveal_audits_deleted=reveal_audits_deleted,
    )
    logger.info(
        "Purge des secrets de fuite : %s secret(s) effacé(s), %s entrée(s) d'audit supprimée(s) "
        "(rétention %s jours).",
        secrets_purged,
        reveal_audits_deleted,
        retention_days,
    )
    return run


def list_purge_runs(limit: int = 50):
    return SecretPurgeRun.objects.all()[:limit]


def retention_policy() -> dict:
    """Politique de rétention affichable au client — ce qui rend la promesse
    crédible en démonstration, c'est qu'il puisse la LIRE dans le produit."""
    return {
        "secret_retention_days": settings.BREACH_SECRET_RETENTION_DAYS,
        "reveal_audit_retention_days": settings.BREACH_REVEAL_AUDIT_RETENTION_DAYS,
    }


def refresh_exposure_synthesis(tenant) -> ExposureSynthesis:
    """Génère et met en cache la synthèse. Import différé d'ai_assistant :
    threat_intelligence ne dépend pas de l'IA au chargement du module (et
    ai_assistant importe déjà threat_intelligence — l'inverse au niveau
    module créerait un cycle)."""
    from apps.ai_assistant import services as ai_services

    content = ai_services.generate_exposure_synthesis(tenant=tenant)
    return save_exposure_synthesis(tenant, content)
