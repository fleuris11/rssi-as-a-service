"""Comptes désignés : déclaration, analyse à la demande, résultats (V2-6).

Module séparé de ``services.py`` — qui fait déjà 1 200 lignes et parle des
actifs — mais **ré-exporté par lui** : les autres apps continuent de passer par
``threat_intelligence.services``, conformément à la règle d'architecture n°1.

Ce que ce module ne fait pas, et c'est délibéré (ADR-033) :

- il n'ouvre **aucune alerte de surveillance** : une alerte se pose sur un
  actif déclaré, et un compte désigné n'en est pas un ;
- il ne stocke **aucun secret**, même chiffré : révéler le mot de passe du
  compte d'un tiers est une tout autre affaire que révéler celui d'un compte
  de l'entreprise (ADR-014), et l'action utile est la même sans lui ;
- il n'alimente **ni le score d'exposition, ni les indicateurs de comité, ni
  le registre des incidents**. Ceux-là lisent ``BreachFinding`` ; ces
  résultats-ci vivent dans leur propre table.
"""

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.billing import entitlements

from .models import BreachIntelligenceUsage, BreachScanJob, WatchedAccount, WatchedAccountFinding
from .providers import get_provider
from .providers.breachsense import normalizer

logger = logging.getLogger(__name__)

#: Version du texte de déclaration. À incrémenter à CHAQUE reformulation de
#: ``DECLARATION_TEXT`` : les déclarations déjà signées gardent leur propre
#: version et leur propre texte, ce qui permet de dire six mois plus tard ce
#: qu'un client avait exactement accepté.
DECLARATION_VERSION = "2026-09-1"

#: Le texte que le client accepte en déclarant un compte. Écrit pour un
#: dirigeant de PME : il doit engager sans faire fuir, et surtout être
#: compris. Il est FIGÉ dans chaque déclaration (``declaration_text``).
DECLARATION_TEXT = (
    "Je déclare avoir le droit de faire surveiller ce compte. Si ce compte n'est pas le "
    "mien, je reconnais que cette surveillance constitue un traitement de données "
    "personnelles dont mon entreprise est responsable : il m'appartient d'en informer la "
    "personne concernée et de pouvoir justifier du fondement de ce traitement. "
    "RSSI as a Service agit ici comme sous-traitant, sur mes seules instructions, et ne "
    "vérifie pas ce fondement à ma place."
)


class WatchedAccountError(Exception):
    """Refus métier propre aux comptes désignés."""


class DeclarationRequiredError(WatchedAccountError):
    pass


# --- Déclaration ------------------------------------------------------------


def normalize_account_value(value: str) -> str:
    """Deux déclarations qui ne diffèrent que par la casse ou des espaces
    sont le même compte — sinon elles compteraient deux fois dans le quota et
    seraient analysées deux fois."""
    return (value or "").strip().lower()


def list_watched_accounts(tenant, *, include_removed: bool = False):
    queryset = WatchedAccount.all_objects.filter(tenant=tenant).select_related(
        "declared_by", "removed_by"
    )
    if not include_removed:
        queryset = queryset.filter(is_active=True)
    return queryset.order_by("-declared_at")


def get_watched_account(*, tenant, account_id):
    return WatchedAccount.all_objects.filter(tenant=tenant, id=account_id).first()


def declare_watched_account(
    *,
    tenant,
    user,
    value: str,
    label: str = "",
    category: str = WatchedAccount.Category.OTHER,
    legal_basis: str,
    purpose: str,
    declaration_accepted: bool,
) -> WatchedAccount:
    """Déclare un compte à surveiller. La déclaration N'EST PAS une case à
    cocher de plus : elle est la condition de la création.

    Le produit ne vérifie pas le fondement invoqué — il ne le peut pas, et
    ADR-033 dit pourquoi ce n'est pas son rôle. Ce qu'il fait, c'est
    l'exiger, le figer et le conserver.
    """
    if not declaration_accepted:
        raise DeclarationRequiredError(
            "La déclaration est obligatoire pour ajouter un compte à surveiller."
        )
    if not (purpose or "").strip():
        raise DeclarationRequiredError(
            "Indiquez pourquoi vous surveillez ce compte : cette finalité fait partie de "
            "la déclaration."
        )

    valeur = normalize_account_value(value)
    if not valeur:
        raise WatchedAccountError("Indiquez le compte à surveiller.")

    entitlements.ensure_watched_account_quota(tenant)

    try:
        with transaction.atomic():
            return WatchedAccount.all_objects.create(
                tenant=tenant,
                value=valeur,
                label=(label or "").strip(),
                category=category,
                legal_basis=legal_basis,
                purpose=purpose.strip(),
                declaration_text=DECLARATION_TEXT,
                declaration_version=DECLARATION_VERSION,
                declared_by=user,
            )
    except IntegrityError as exc:
        raise WatchedAccountError("Ce compte est déjà surveillé.") from exc


def remove_watched_account(
    account: WatchedAccount, *, user=None, reason: str = ""
) -> WatchedAccount:
    """Retrait LOGIQUE. La déclaration et la date d'arrêt de la surveillance
    restent : ce sont elles qu'on montre à la personne concernée si elle
    demande depuis quand, et jusqu'à quand, son compte a été surveillé."""
    if not account.is_active:
        return account
    account.is_active = False
    account.removed_at = timezone.now()
    account.removed_by = user
    account.removal_reason = (reason or "")[:200]
    account.save(update_fields=["is_active", "removed_at", "removed_by", "removal_reason"])
    return account


# --- Résultats --------------------------------------------------------------


def list_watched_account_findings(tenant, *, account=None, status=None):
    queryset = WatchedAccountFinding.all_objects.filter(tenant=tenant).select_related("account")
    if account is not None:
        queryset = queryset.filter(account=account)
    if status:
        queryset = queryset.filter(status=status)
    return queryset.order_by("-detected_at")


def get_watched_account_finding(*, tenant, finding_id):
    return WatchedAccountFinding.all_objects.filter(tenant=tenant, id=finding_id).first()


def update_watched_account_finding_status(finding: WatchedAccountFinding, status: str):
    finding.status = status
    finding.treated_at = timezone.now() if status == WatchedAccountFinding.Status.TREATED else None
    finding.save(update_fields=["status", "treated_at"])
    return finding


def watched_accounts_summary(tenant) -> dict:
    """Ce que l'écran affiche en tête : combien de comptes, combien de
    résultats ouverts, et quand la dernière analyse a eu lieu.

    Volontairement séparé de ``exposure_feed`` : ce ne sont pas les actifs du
    client, et les deux chiffres ne doivent jamais s'additionner quelque part.
    """
    comptes = list_watched_accounts(tenant)
    ouverts = WatchedAccountFinding.all_objects.filter(
        tenant=tenant, status=WatchedAccountFinding.Status.OPEN
    )
    derniere = (
        WatchedAccount.all_objects.filter(tenant=tenant, last_scanned_at__isnull=False)
        .order_by("-last_scanned_at")
        .values_list("last_scanned_at", flat=True)
        .first()
    )
    return {
        "accounts": comptes.count(),
        "open_findings": ouverts.count(),
        "critical_findings": ouverts.filter(severity="critical").count(),
        "last_scanned_at": derniere,
    }


# --- Analyse à la demande ---------------------------------------------------


def create_watched_account_scan_job(
    *, tenant, user, accounts: list[WatchedAccount]
) -> BreachScanJob:
    """Crée le job. Les gardes (offre, quota, capacité plateforme) sont posées
    par l'appelant AVANT : un job créé puis refusé laisserait au client un
    travail qui n'a jamais commencé."""
    return BreachScanJob.all_objects.create(
        tenant=tenant,
        asset=None,
        scope=BreachScanJob.Scope.WATCHED_ACCOUNTS,
        triggered_by=BreachIntelligenceUsage.TriggeredBy.MANUAL,
        result_ref={
            "account_ids": [account.id for account in accounts],
            "requested_by": str(user.id) if user else None,
        },
    )


def resolve_scan_targets(tenant, *, account_ids=None) -> list[WatchedAccount]:
    """Les comptes à analyser : ceux désignés, ou tous les comptes actifs."""
    queryset = WatchedAccount.all_objects.filter(tenant=tenant, is_active=True)
    if account_ids:
        queryset = queryset.filter(id__in=account_ids)
    return list(queryset.order_by("declared_at"))


def execute_watched_account_scan(*, tenant, accounts: list[WatchedAccount]) -> dict:
    """Interroge le fournisseur pour chaque compte, puis enregistre l'usage.

    Appelée depuis la tâche Celery, jamais depuis une vue (CLAUDE.md : aucun
    appel réseau dans le cycle requête/réponse).

    Un compte en échec ne fait pas tomber les autres — même règle que
    ``services.execute_scan``, apprise le 06/09/2026 quand un seul actif a
    fait perdre l'analyse entière d'un client réel.
    """
    from . import services as ti_services

    provider = get_provider()
    manager = ti_services.quota_module.QuotaManager()

    total_created = 0
    total_requests = 0
    deja_vus = 0
    comptes_en_echec: list[str] = []
    now = timezone.now()

    for account in accounts:
        try:
            resultat = provider.scan_email(account.value)
            total_requests += resultat.requests_consumed
            crees, revus = _ingest(tenant=tenant, account=account, raw_findings=resultat.findings)
            total_created += crees
            deja_vus += revus
            account.last_scanned_at = now
            account.save(update_fields=["last_scanned_at"])
        except Exception:  # noqa: BLE001 - un compte ne fait pas tomber les autres
            comptes_en_echec.append(account.value)
            logger.exception(
                "Analyse en échec pour un compte désigné (tenant %s) — les autres comptes "
                "de ce lot continuent.",
                tenant.id,
            )

    if total_requests:
        # Enregistré même en échec partiel : les requêtes ont été consommées
        # sur la licence. L'endpoint marque l'usage comme VIP pour qu'il
        # décompte du quota de comptes et NON de celui des actifs.
        manager.record_usage(
            tenant=tenant,
            endpoint=entitlements.WATCHED_ACCOUNT_ENDPOINT,
            requests_consumed=total_requests,
            remaining_after=manager.get_remaining(),
            triggered_by=BreachIntelligenceUsage.TriggeredBy.MANUAL,
            findings_created=total_created,
        )

    if comptes_en_echec and total_created == 0 and len(comptes_en_echec) == len(accounts):
        raise WatchedAccountError("Analyse impossible pour les comptes demandés.")

    return {
        "findings_created": total_created,
        "findings_seen_again": deja_vus,
        "requests_consumed": total_requests,
        "accounts_scanned": len(accounts) - len(comptes_en_echec),
        "accounts_failed": len(comptes_en_echec),
    }


def _ingest(*, tenant, account: WatchedAccount, raw_findings) -> tuple[int, int]:
    """Normalise et enregistre. Renvoie (créées, déjà connues).

    Réutilise le normaliseur des actifs — c'est le même fournisseur et le
    même format — puis **jette** tout ce qui touche au secret. Un seul
    endroit décide de ce qui est conservé, et il est ici.
    """
    crees = 0
    revus = 0
    now = timezone.now()

    for raw in raw_findings:
        if raw.is_test:
            continue
        normalized = normalizer.normalize_finding(raw.endpoint, raw.payload)
        # Le secret en clair est retiré immédiatement et n'est ni chiffré ni
        # écrit : contrairement aux fuites sur actif, il n'existe pas de
        # chemin de révélation pour un compte désigné (ADR-033).
        normalized.pop("secret_plain", "")

        finding, cree = WatchedAccountFinding.all_objects.get_or_create(
            tenant=tenant,
            dedup_hash=normalized["dedup_hash"],
            defaults={
                "account": account,
                "source_endpoint": normalized["source_endpoint"],
                "finding_type": normalized["finding_type"],
                "severity": normalized["severity"],
                "identifier_masked": normalized.get("identifier_masked", ""),
                "secret_masked": normalized.get("secret_masked", ""),
                # Le normaliseur sait si un secret a été vu ; on garde ce
                # signal, jamais sa valeur.
                "has_secret": bool(normalized.get("has_secret")),
                "breach_date": normalized.get("breach_date"),
                "raw_data": normalized.get("raw_data", {}),
                "last_seen_at": now,
            },
        )
        if cree:
            crees += 1
            continue
        # Déjà connue : on avance la date de dernière observation, et rien
        # d'autre. Une fuite traitée ne se rouvre pas toute seule.
        revus += 1
        finding.last_seen_at = now
        finding.save(update_fields=["last_seen_at"])

    return crees, revus
