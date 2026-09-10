"""Public interface of the monitoring app — other apps (and Celery tasks)
must go through here instead of importing apps.monitoring.models
directly. Like apps.assessments/apps.actions, every function is given an
already-resolved tenant/asset, so it consistently uses ``all_objects``
with an explicit ``tenant=`` filter rather than the request-scoped one.
"""

import logging
import secrets
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from . import ownership_messages
from .checks import ownership as ownership_checks
from .checks.email_dns import check_email_dns
from .checks.http_uptime import check_http_uptime
from .checks.security_headers import check_security_headers
from .checks.ssl_certificate import check_ssl_certificate
from .models import Alert, Asset, AssetOwnershipAttestation, AssetOwnershipProof, CheckResult

logger = logging.getLogger(__name__)

# Written every minute by tasks.heartbeat (Beat + a worker on the
# monitoring queue), read by config.views.healthz_worker — proves the
# whole scheduling chain is alive end to end, not just that a process
# is running.
HEARTBEAT_CACHE_KEY = "monitoring:worker_heartbeat"
HEARTBEAT_CACHE_TIMEOUT_SECONDS = 180  # 3x the 1-minute beat schedule


class MonitoringError(Exception):
    """Base class for business-rule violations raised by this module."""


class InvalidAssetError(MonitoringError):
    pass


# CLAUDE.md: "Alerte monitoring : confirmer un DOWN par 3 échecs consécutifs
# avant d'alerter (anti faux positifs)."
CONSECUTIVE_FAILURES_FOR_DOWN = 3

# US-5.3: "alerte anticipée (30/14/7 jours)" — each is a distinct
# notification point on the same still-open alert, not three alert rows.
SSL_NOTIFY_THRESHOLDS = [30, 14, 7]

CHECK_INTERVALS = {
    CheckResult.CheckType.HTTP_UPTIME: timedelta(minutes=5),
    CheckResult.CheckType.SSL_CERTIFICATE: timedelta(hours=24),
    CheckResult.CheckType.SECURITY_HEADERS: timedelta(hours=24),
    CheckResult.CheckType.EMAIL_DNS: timedelta(hours=24),
}

CHECK_TYPES_BY_ASSET_TYPE = {
    Asset.Type.WEBSITE: [
        CheckResult.CheckType.HTTP_UPTIME,
        CheckResult.CheckType.SSL_CERTIFICATE,
        CheckResult.CheckType.SECURITY_HEADERS,
    ],
    Asset.Type.EMAIL_DOMAIN: [CheckResult.CheckType.EMAIL_DNS],
}


# --- Assets ------------------------------------------------------------


def create_asset(
    *,
    tenant,
    user,
    type: str,
    value: str,
    ownership_confirmed: bool,
    ip_address: str = "",
    user_agent: str = "",
) -> Asset:
    """Déclare un actif, et TRACE la déclaration sur l'honneur qui l'autorise.

    La case cochée ne laissait aucune trace : ni qui, ni quand, ni sur quel
    actif. C'est ce qui manquait le jour où un client a déclaré le domaine
    d'une autre organisation — on ne pouvait même pas dire qui l'avait
    affirmé. La déclaration devient une ligne datée et nominative
    (``AssetOwnershipAttestation``, ADR-026), et c'est elle qui autorise
    l'analyse ponctuelle.

    L'actif et sa déclaration sont écrits dans la même transaction : un actif
    sans déclaration serait exactement l'état qu'on cherche à ne plus créer.
    """
    if not ownership_confirmed:
        raise InvalidAssetError(
            "La case d'engagement de propriété doit être cochée pour déclarer un actif."
        )
    with transaction.atomic():
        asset = Asset.all_objects.create(
            tenant=tenant,
            type=type,
            value=value,
            ownership_confirmed=True,
            created_by=user,
        )
        record_ownership_attestation(
            asset=asset, user=user, ip_address=ip_address, user_agent=user_agent
        )
    return asset


def list_assets(tenant):
    return Asset.all_objects.filter(tenant=tenant).order_by("-created_at")


def get_asset(*, tenant, asset_id):
    return Asset.all_objects.filter(tenant=tenant, id=asset_id).first()


def set_asset_active(asset: Asset, is_active: bool) -> Asset:
    asset.is_active = is_active
    asset.save(update_fields=["is_active"])
    return asset


def delete_asset(asset: Asset) -> None:
    asset.delete()


# --- Possession d'un domaine (V2-1, ADR-026) --------------------------------
#
# ADR-010 posait « un actif n'est verifie que s'il est declare ». La
# production a montre la faille de ce principe : **declarer n'est pas
# posseder**. Un client a declare, puis fait surveiller, le domaine d'une
# autre organisation.
#
# La regle retenue distingue les deux gestes selon ce qu'ils engagent :
#
#   - **surveillance continue** — durable, invisible du dehors, elle occupe
#     un emplacement de la licence plateforme et fera parvenir des alertes
#     pendant des mois : elle exige une PREUVE ;
#   - **analyse ponctuelle** — un geste unique, decide et date, dont le
#     client repond : une declaration sur l'honneur suffit, mais elle est
#     TRACEE (qui, quand, quel actif).


class OwnershipError(MonitoringError):
    """Regle de possession non respectee."""


class OwnershipNotProvenError(OwnershipError):
    pass


# Adresses generiques admises pour la validation par email. Liste FERMEE, et
# c'est tout l'interet : laisser le client saisir l'adresse de son choix
# reviendrait a lui demander de s'ecrire a lui-meme. Ce sont les boites que
# les autorites de certification utilisent pour la meme raison — seul
# quelqu'un qui administre reellement le domaine y a acces.
OWNERSHIP_EMAIL_LOCAL_PARTS = ("admin", "administrator", "hostmaster", "postmaster", "webmaster")


def asset_domain(asset: Asset) -> str:
    """Domaine d'un actif, quel que soit son type. Un actif « site web »
    porte une URL complete, un actif « domaine email » porte le domaine nu."""
    if asset.type == Asset.Type.WEBSITE:
        return urlparse(asset.value).hostname or asset.value
    return asset.value


def record_ownership_attestation(
    *, asset: Asset, user, ip_address: str = "", user_agent: str = ""
) -> AssetOwnershipAttestation:
    """Trace la declaration sur l'honneur qui autorise une analyse ponctuelle."""
    return AssetOwnershipAttestation.all_objects.create(
        tenant=asset.tenant,
        asset=asset,
        user=user,
        statement=ownership_messages.ATTESTATION_STATEMENT,
        ip_address=ip_address or None,
        user_agent=user_agent[:255],
    )


def list_ownership_attestations(asset: Asset):
    return AssetOwnershipAttestation.all_objects.filter(asset=asset).select_related("user")


def is_ownership_proven(asset: Asset) -> bool:
    return AssetOwnershipProof.all_objects.filter(
        asset=asset, status=AssetOwnershipProof.Status.VERIFIED
    ).exists()


def has_ownership_attestation(asset: Asset) -> bool:
    return AssetOwnershipAttestation.all_objects.filter(asset=asset).exists()


def needs_ownership_review(asset: Asset) -> bool:
    """Actif « a verifier » : ni preuve, ni declaration tracee.

    Derive plutot que stocke. Un drapeau aurait du etre pose par une
    migration, puis maintenu a jour a chaque preuve validee — deux occasions
    de diverger de la realite. Ici la question n'a qu'une seule reponse
    possible, celle que portent les tables.

    Ce sont exactement les actifs declares AVANT la V2-1 : ils continuent
    d'etre surveilles (les couper punirait le client d'une regle qui
    n'existait pas quand il a declare), mais ils apparaissent dans l'ecran de
    regularisation de la console.
    """
    return not is_ownership_proven(asset) and not has_ownership_attestation(asset)


def ownership_state(asset: Asset) -> str:
    if is_ownership_proven(asset):
        return "proven"
    if has_ownership_attestation(asset):
        return "declared"
    return "to_review"


def assets_needing_ownership_review():
    """Tous tenants confondus — ecran de regularisation de la console.

    L'une des rares lectures non scopees de ce module, et pour la meme raison
    que le pool de surveillance : la question posee est celle de l'exploitant
    (« que reste-t-il a regulariser sur la plateforme ? »), pas celle d'un
    client sur ses propres actifs.
    """
    return (
        Asset.all_objects.filter(ownership_proofs__isnull=True, ownership_attestations__isnull=True)
        .select_related("tenant")
        .order_by("tenant__name", "value")
    )


def get_ownership_proof(*, asset: Asset, proof_id: int) -> AssetOwnershipProof | None:
    return AssetOwnershipProof.all_objects.filter(asset=asset, id=proof_id).first()


def list_ownership_proofs(asset: Asset):
    return AssetOwnershipProof.all_objects.filter(asset=asset)


def start_ownership_proof(
    *, asset: Asset, method: str, user=None, email_recipient: str = ""
) -> AssetOwnershipProof:
    """Ouvre une verification et renvoie ce que le client doit publier.

    Une preuve deja VERIFIEE n'est pas rejouee : la contrainte d'unicite
    l'interdirait de toute facon, et redemander une preuve acquise serait une
    perte de temps pour le client.
    """
    if method not in AssetOwnershipProof.Method.values:
        raise OwnershipError("Methode de verification inconnue.")
    if is_ownership_proven(asset):
        raise OwnershipError("La possession de cet actif est deja prouvee.")

    domaine = asset_domain(asset)
    if method == AssetOwnershipProof.Method.EMAIL:
        partie_locale = (email_recipient or "").split("@")[0].strip().lower()
        if partie_locale not in OWNERSHIP_EMAIL_LOCAL_PARTS:
            raise OwnershipError(ownership_messages.email_choices_message(domaine))
        email_recipient = f"{partie_locale}@{domaine}"
    else:
        email_recipient = ""

    # Les tentatives en cours de la MEME methode sont remplacees : deux jetons
    # valides simultanement pour la meme methode ne servent qu'a faire publier
    # le mauvais.
    AssetOwnershipProof.all_objects.filter(
        asset=asset,
        method=method,
        status__in=[AssetOwnershipProof.Status.PENDING, AssetOwnershipProof.Status.FAILED],
    ).delete()

    proof = AssetOwnershipProof.all_objects.create(
        tenant=asset.tenant,
        asset=asset,
        method=method,
        token=secrets.token_urlsafe(24),
        email_recipient=email_recipient,
        created_by=user,
    )
    if method == AssetOwnershipProof.Method.EMAIL:
        _send_ownership_email(proof)
    return proof


def _send_ownership_email(proof: AssetOwnershipProof) -> None:
    domaine = asset_domain(proof.asset)
    try:
        send_mail(
            subject=ownership_messages.email_subject(domaine),
            message=ownership_messages.email_body(
                domaine=domaine, entreprise=proof.asset.tenant.name, jeton=proof.token
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[proof.email_recipient],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001 — un echec d'envoi n'est pas une panne
        # Journalise SANS l'adresse : elle designe une organisation tierce
        # tant que la possession n'est justement pas prouvee.
        logger.warning(
            "Envoi de l'email de verification de possession impossible (actif %s) : %s",
            proof.asset_id,
            exc,
        )
        proof.status = AssetOwnershipProof.Status.FAILED
        proof.last_attempt_at = timezone.now()
        proof.last_error = ownership_messages.EMAIL_SEND_FAILED
        proof.save(update_fields=["status", "last_attempt_at", "last_error"])


def ownership_instructions(proof: AssetOwnershipProof) -> dict:
    """Ce que le client doit faire, dans ses mots. Calcule cote serveur pour
    que l'ecran, l'email et le support disent exactement la meme chose."""
    domaine = asset_domain(proof.asset)
    if proof.method == AssetOwnershipProof.Method.DNS_TXT:
        return {
            "method": proof.method,
            "domain": domaine,
            "record_name": domaine,
            "record_type": "TXT",
            "record_value": ownership_checks.expected_dns_record(proof.token),
            "how_to": ownership_messages.DNS_TXT_HOW_TO.format(domaine=domaine),
        }
    if proof.method == AssetOwnershipProof.Method.HTTP_FILE:
        return {
            "method": proof.method,
            "domain": domaine,
            "file_url": f"https://{domaine}{ownership_checks.HTTP_FILE_PATH}",
            "file_content": proof.token,
            "how_to": ownership_messages.HTTP_FILE_HOW_TO.format(
                chemin=ownership_checks.HTTP_FILE_PATH, domaine=domaine
            ),
        }
    return {
        "method": proof.method,
        "domain": domaine,
        "email_recipient": proof.email_recipient,
        "how_to": ownership_messages.EMAIL_HOW_TO.format(adresse=proof.email_recipient),
    }


def verify_ownership_proof(
    proof: AssetOwnershipProof, *, submitted_token: str = ""
) -> AssetOwnershipProof:
    """Controle la preuve et met son statut a jour.

    Ne leve pas quand la preuve n'est pas encore la : « pas encore publie »
    est un etat normal du parcours, pas une erreur. Ce qui leve, c'est ce qui
    empeche de conclure (DNS injoignable, domaine non resolvable).
    """
    domaine = asset_domain(proof.asset)
    proof.last_attempt_at = timezone.now()

    try:
        if proof.method == AssetOwnershipProof.Method.DNS_TXT:
            ok, detail = ownership_checks.verify_dns_txt(domaine, proof.token)
        elif proof.method == AssetOwnershipProof.Method.HTTP_FILE:
            ok, detail = ownership_checks.verify_http_file(domaine, proof.token)
        else:
            ok = secrets.compare_digest(submitted_token.strip(), proof.token)
            detail = "Code accepte." if ok else ownership_messages.EMAIL_CODE_MISMATCH
    except ownership_checks.OwnershipCheckError as exc:
        proof.status = AssetOwnershipProof.Status.FAILED
        proof.last_error = str(exc)
        proof.save(update_fields=["status", "last_attempt_at", "last_error"])
        return proof

    if ok:
        proof.status = AssetOwnershipProof.Status.VERIFIED
        proof.verified_at = timezone.now()
        proof.last_error = ""
        proof.save(update_fields=["status", "verified_at", "last_attempt_at", "last_error"])
    else:
        proof.status = AssetOwnershipProof.Status.FAILED
        proof.last_error = detail
        proof.save(update_fields=["status", "last_attempt_at", "last_error"])
    return proof


def ensure_ownership_proven(asset: Asset) -> None:
    """Garde appelee avant toute activation de la surveillance continue."""
    if not is_ownership_proven(asset):
        raise OwnershipNotProvenError(ownership_messages.OWNERSHIP_REQUIRED)


# --- Running checks ------------------------------------------------------


def list_due_assets(check_type: str):
    """Active assets of a type this check applies to, never checked (for
    this check_type) or last checked longer ago than its interval."""
    interval = CHECK_INTERVALS[check_type]
    cutoff = timezone.now() - interval
    applicable_asset_types = [
        asset_type
        for asset_type, check_types in CHECK_TYPES_BY_ASSET_TYPE.items()
        if check_type in check_types
    ]
    return list(
        Asset.all_objects.filter(is_active=True, type__in=applicable_asset_types)
        .annotate(
            last_checked_at=Max(
                "check_results__checked_at",
                filter=Q(check_results__check_type=check_type),
            )
        )
        .filter(Q(last_checked_at__isnull=True) | Q(last_checked_at__lte=cutoff))
    )


def run_check(asset: Asset, check_type: str) -> tuple[CheckResult, Alert | None]:
    """Runs one check for ``asset``, records the result, and evaluates the
    alert engine. Returns ``(check_result, alert)`` — ``alert`` is only set
    when a *new* alert opened or an SSL threshold was newly crossed, i.e.
    when a real-time notification (US-5.6) is warranted."""
    if check_type == CheckResult.CheckType.HTTP_UPTIME:
        result = check_http_uptime(asset.value)
    elif check_type == CheckResult.CheckType.SSL_CERTIFICATE:
        hostname = urlparse(asset.value).hostname or asset.value
        result = check_ssl_certificate(hostname)
    elif check_type == CheckResult.CheckType.SECURITY_HEADERS:
        result = check_security_headers(asset.value)
    elif check_type == CheckResult.CheckType.EMAIL_DNS:
        result = check_email_dns(asset.value)
    else:
        raise MonitoringError(f"Type de check inconnu : {check_type!r}")

    check_result = CheckResult.all_objects.create(
        tenant=asset.tenant,
        asset=asset,
        check_type=check_type,
        status=result["status"],
        details=result.get("details", {}),
        latency_ms=result.get("latency_ms"),
    )
    notify_alert = evaluate_alerts(asset=asset, check_type=check_type, latest_result=check_result)
    return check_result, notify_alert


def simulate_check_result(
    asset: Asset, *, check_type: str, status: str, details: dict | None = None
) -> tuple[CheckResult, Alert | None]:
    """Injects a CheckResult without performing a live network check, then
    runs it through the same alert engine as ``run_check``. Used by the
    ``simulate_check_failure`` management command (E2E tests, demos) to
    exercise the alerting pipeline without depending on a real external
    target being actually down."""
    check_result = CheckResult.all_objects.create(
        tenant=asset.tenant,
        asset=asset,
        check_type=check_type,
        status=status,
        details=details or {},
    )
    alert = evaluate_alerts(asset=asset, check_type=check_type, latest_result=check_result)
    return check_result, alert


# --- Alert engine ----------------------------------------------------------


def _open_or_update_alert(asset: Asset, alert_type: str, severity: str, details: dict):
    """Returns (alert, created) — "created" also True when severity/details
    changed on an already-open alert (an escalation), so callers can treat
    both as "state changed, maybe notify"."""
    alert = Alert.all_objects.filter(asset=asset, alert_type=alert_type, is_open=True).first()
    if alert is None:
        alert = Alert.all_objects.create(
            tenant=asset.tenant,
            asset=asset,
            alert_type=alert_type,
            severity=severity,
            details=details,
        )
        return alert, True
    changed = alert.severity != severity or alert.details != details
    if changed:
        alert.severity = severity
        alert.details = details
        alert.save(update_fields=["severity", "details", "updated_at"])
    return alert, changed


def open_or_update_alert(*, asset: Asset, alert_type: str, severity: str, details: dict) -> Alert:
    """Public entry point for other apps that need to open/escalate an
    alert on a tenant's asset through this module's dedup/escalation
    engine, without duplicating it (Phase 7, ADR-013:
    apps.threat_intelligence calls this for breach-compromise alerts). The
    check-specific ``evaluate_alerts``/``_evaluate_*`` functions above stay
    private — they're only ever driven by this module's own CheckResults —
    this wrapper is for alert types with no CheckResult behind them."""
    alert, _created = _open_or_update_alert(asset, alert_type, severity, details)
    return alert


def _resolve_alert(asset: Asset, alert_type: str) -> None:
    Alert.all_objects.filter(asset=asset, alert_type=alert_type, is_open=True).update(
        is_open=False, resolved_at=timezone.now()
    )


def evaluate_alerts(*, asset: Asset, check_type: str, latest_result: CheckResult) -> Alert | None:
    if check_type == CheckResult.CheckType.HTTP_UPTIME:
        return _evaluate_down_alert(asset)
    if check_type == CheckResult.CheckType.SSL_CERTIFICATE:
        return _evaluate_ssl_alert(asset, latest_result)
    if check_type == CheckResult.CheckType.SECURITY_HEADERS:
        return _evaluate_headers_alert(asset, latest_result)
    if check_type == CheckResult.CheckType.EMAIL_DNS:
        return _evaluate_email_alert(asset, latest_result)
    return None


def _evaluate_down_alert(asset: Asset) -> Alert | None:
    recent = list(
        CheckResult.all_objects.filter(
            tenant=asset.tenant, asset=asset, check_type=CheckResult.CheckType.HTTP_UPTIME
        ).order_by("-checked_at")[:CONSECUTIVE_FAILURES_FOR_DOWN]
    )
    if not recent:
        return None

    if recent[0].status == CheckResult.Status.OK:
        _resolve_alert(asset, Alert.AlertType.DOWN)
        return None

    if len(recent) < CONSECUTIVE_FAILURES_FOR_DOWN:
        return None  # not enough history yet — anti-false-positive

    if all(r.status == CheckResult.Status.CRITICAL for r in recent):
        alert, created = _open_or_update_alert(
            asset,
            Alert.AlertType.DOWN,
            Alert.Severity.CRITICAL,
            {
                "consecutive_failures": CONSECUTIVE_FAILURES_FOR_DOWN,
                "last_error": recent[0].details.get("error"),
            },
        )
        return alert if created else None
    return None


def _evaluate_ssl_alert(asset: Asset, latest_result: CheckResult) -> Alert | None:
    days_left = latest_result.details.get("days_left")
    if days_left is None:
        return None  # certificate fetch failed — no expiry-specific alert to raise

    if days_left > max(SSL_NOTIFY_THRESHOLDS):
        _resolve_alert(asset, Alert.AlertType.SSL_EXPIRING)
        return None

    severity = (
        Alert.Severity.CRITICAL
        if days_left <= min(SSL_NOTIFY_THRESHOLDS)
        else Alert.Severity.WARNING
    )

    existing = Alert.all_objects.filter(
        asset=asset, alert_type=Alert.AlertType.SSL_EXPIRING, is_open=True
    ).first()
    already_notified = set(existing.details.get("notified_thresholds", [])) if existing else set()
    newly_crossed = {t for t in SSL_NOTIFY_THRESHOLDS if days_left <= t} - already_notified
    if not newly_crossed:
        return None  # already alerted for this threshold, don't re-notify

    notified_thresholds = sorted(already_notified | newly_crossed)
    alert, _created = _open_or_update_alert(
        asset,
        Alert.AlertType.SSL_EXPIRING,
        severity,
        {
            "days_left": days_left,
            "expires_at": latest_result.details.get("expires_at"),
            "notified_thresholds": notified_thresholds,
        },
    )
    return alert


def _evaluate_headers_alert(asset: Asset, latest_result: CheckResult) -> Alert | None:
    missing = latest_result.details.get("missing", [])
    if not missing:
        _resolve_alert(asset, Alert.AlertType.SECURITY_HEADERS)
        return None
    alert, created = _open_or_update_alert(
        asset,
        Alert.AlertType.SECURITY_HEADERS,
        Alert.Severity.WARNING,
        {"missing": [m["header"] for m in missing]},
    )
    return alert if created else None


def _evaluate_email_alert(asset: Asset, latest_result: CheckResult) -> Alert | None:
    issues = latest_result.details.get("issues", [])
    if not issues:
        _resolve_alert(asset, Alert.AlertType.EMAIL_MISCONFIGURED)
        return None
    severity = (
        Alert.Severity.CRITICAL
        if latest_result.status == CheckResult.Status.CRITICAL
        else Alert.Severity.WARNING
    )
    alert, created = _open_or_update_alert(
        asset, Alert.AlertType.EMAIL_MISCONFIGURED, severity, {"issues": issues}
    )
    return alert if created else None


# --- Dashboard / reporting -------------------------------------------------


def list_open_alerts(tenant):
    return (
        Alert.all_objects.filter(tenant=tenant, is_open=True)
        .select_related("asset")
        .order_by("-opened_at")
    )


def get_alert(alert_id):
    """Looked up by primary key alone (no tenant filter) — for the
    notifications Celery task, which receives only an alert_id and hasn't
    resolved a tenant yet at that point."""
    return Alert.all_objects.filter(id=alert_id).select_related("asset", "tenant").first()


def get_latest_check(asset: Asset, check_type: str) -> CheckResult | None:
    return (
        CheckResult.all_objects.filter(tenant=asset.tenant, asset=asset, check_type=check_type)
        .order_by("-checked_at")
        .first()
    )


def compute_uptime_percentage(asset: Asset, *, hours: int = 24) -> float | None:
    since = timezone.now() - timedelta(hours=hours)
    results = CheckResult.all_objects.filter(
        tenant=asset.tenant,
        asset=asset,
        check_type=CheckResult.CheckType.HTTP_UPTIME,
        checked_at__gte=since,
    )
    total = results.count()
    if total == 0:
        return None
    ok = results.filter(status=CheckResult.Status.OK).count()
    return round(100 * ok / total, 1)


def get_asset_dashboard(asset: Asset) -> dict:
    latest_checks = {
        check_type: get_latest_check(asset, check_type)
        for check_type in CHECK_TYPES_BY_ASSET_TYPE.get(asset.type, [])
    }
    return {
        "asset": asset,
        "latest_checks": latest_checks,
        "uptime_24h": compute_uptime_percentage(asset, hours=24)
        if asset.type == Asset.Type.WEBSITE
        else None,
        "open_alerts": list(
            Alert.all_objects.filter(tenant=asset.tenant, asset=asset, is_open=True)
        ),
    }


def get_tenant_dashboard(tenant) -> list[dict]:
    return [get_asset_dashboard(asset) for asset in list_assets(tenant)]


# --- Indicateurs pour le comité (V2-3, ADR-028) -----------------------------


def monitoring_indicators(tenant, *, start, end) -> dict:
    """Surveillance : disponibilité sur la période, et certificats à échéance.

    La disponibilité est agrégée EN BASE — deux compteurs sur la table des
    contrôles, jamais une boucle sur les résultats. Un actif contrôlé toutes
    les cinq minutes produit 8 640 lignes par mois : les charger pour en
    compter une proportion serait exactement la faute que le fil d'exposition
    a déjà coûtée.
    """
    controles = CheckResult.all_objects.filter(
        tenant=tenant,
        check_type=CheckResult.CheckType.HTTP_UPTIME,
        checked_at__gte=start,
        checked_at__lte=end,
    )
    comptes = controles.aggregate(
        total=Count("id"),
        ok=Count("id", filter=Q(status=CheckResult.Status.OK)),
    )
    disponibilite = round(100 * comptes["ok"] / comptes["total"], 2) if comptes["total"] else None

    actifs = Asset.all_objects.filter(tenant=tenant)
    alertes = Alert.all_objects.filter(tenant=tenant)

    return {
        "assets_total": actifs.count(),
        "assets_active": actifs.filter(is_active=True).count(),
        "uptime_percentage": disponibilite,
        "checks_in_period": comptes["total"],
        "failed_checks_in_period": comptes["total"] - comptes["ok"],
        "open_alerts": alertes.filter(is_open=True).count(),
        "alerts_opened_in_period": alertes.filter(opened_at__gte=start, opened_at__lte=end).count(),
        "alerts_resolved_in_period": alertes.filter(
            resolved_at__gte=start, resolved_at__lte=end
        ).count(),
        "certificates": expiring_certificates(tenant),
    }


def expiring_certificates(tenant, *, within_days: int = 60) -> list[dict]:
    """Certificats dont l'échéance approche, du plus urgent au moins urgent.

    Lit le dernier contrôle TLS de chaque actif : un tenant a quelques actifs,
    pas des milliers, et l'information vit dans le JSON de détail — il n'y a
    rien à agréger en base ici.
    """
    proches = []
    for asset in Asset.all_objects.filter(tenant=tenant, type=Asset.Type.WEBSITE, is_active=True):
        dernier = get_latest_check(asset, CheckResult.CheckType.SSL_CERTIFICATE)
        if dernier is None:
            continue
        jours = (dernier.details or {}).get("days_left")
        if jours is None or jours > within_days:
            continue
        proches.append(
            {
                "asset_id": asset.id,
                "asset_value": asset.value,
                "days_left": jours,
                "expires_at": (dernier.details or {}).get("expires_at"),
            }
        )
    proches.sort(key=lambda ligne: ligne["days_left"])
    return proches


# --- Worker health -----------------------------------------------------------


def record_heartbeat() -> None:
    cache.set(
        HEARTBEAT_CACHE_KEY, timezone.now().isoformat(), timeout=HEARTBEAT_CACHE_TIMEOUT_SECONDS
    )


def is_worker_healthy() -> tuple[bool, str | None]:
    """(healthy, last_seen_iso). Unhealthy if Beat/the monitoring worker
    haven't produced a heartbeat recently enough — proves the whole
    scheduling chain end to end, not just that a process exists."""
    last_seen = cache.get(HEARTBEAT_CACHE_KEY)
    return last_seen is not None, last_seen
