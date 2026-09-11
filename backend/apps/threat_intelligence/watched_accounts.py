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
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import (
    Case,
    CharField,
    Count,
    F,
    IntegerField,
    Max,
    Min,
    Q,
    Value,
    When,
)
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce, NullIf
from django.utils import timezone

from apps.billing import entitlements

from .models import (
    BreachFinding,
    BreachIntelligenceUsage,
    BreachScanJob,
    WatchedAccount,
    WatchedAccountFinding,
)
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


#: Rang de gravite, pour trier et pour retenir la pire d'un groupe. Les
#: valeurs sont des chaines : « critical » < « high » en ordre alphabetique,
#: ce qui est l'inverse de ce qu'on veut.
SEVERITY_RANK = {
    BreachFinding.Severity.CRITICAL: 3,
    BreachFinding.Severity.HIGH: 2,
    BreachFinding.Severity.ATTENTION: 1,
}


def _service_expression():
    """Le « service d'origine » d'une observation, lu dans la charge brute.

    Selon l'entrepot il s'appelle ``dom`` (le domaine du cookie vole) ou
    ``src`` (la fuite d'ou vient le couple identifiant/mot de passe). C'est la
    troisieme composante du regroupement : sans elle, des milliers de cookies
    provenant de domaines differents se reduiraient a une seule ligne.
    """
    return Coalesce(
        NullIf(KeyTextTransform("dom", "raw_data"), Value("")),
        NullIf(KeyTextTransform("src", "raw_data"), Value("")),
        Value(""),
        output_field=CharField(),
    )


def list_watched_account_findings(
    tenant,
    *,
    account=None,
    status=None,
    severity=None,
    finding_type=None,
    since=None,
    search=None,
):
    """Les resultats, filtres et tries par DATE DE FUITE decroissante.

    Le tri etait ``-detected_at``, c'est-a-dire l'ordre d'insertion inverse.
    Les milliers de lignes d'une meme analyse etant creees dans la meme
    boucle, trier par cette colonne revenait a trier par l'ordre dans lequel
    le fournisseur avait repondu : arbitraire pour un lecteur, et c'est ce qui
    faisait apparaitre en tete une serie de cookies tous dates du meme jour.

    ``-breach_date`` repond a la question qu'on se pose vraiment — qu'est-ce
    qui est le plus recent — et ``-detected_at`` ne sert plus qu'a departager
    deux fuites de meme date.
    """
    queryset = WatchedAccountFinding.all_objects.filter(tenant=tenant).select_related("account")
    if account is not None:
        queryset = queryset.filter(account=account)
    if status:
        queryset = queryset.filter(status=status)
    if severity:
        queryset = queryset.filter(severity=severity)
    if finding_type:
        queryset = queryset.filter(finding_type=finding_type)
    if since is not None:
        queryset = queryset.filter(breach_date__gte=since)
    if search:
        queryset = queryset.filter(
            Q(account__value__icontains=search) | Q(account__label__icontains=search)
        )
    return queryset.order_by(F("breach_date").desc(nulls_last=True), "-detected_at")


def group_watched_account_findings(queryset):
    """Regroupe par (compte, type de fuite, service d'origine).

    **C'est le regroupement qui rend l'ecran lisible, pas la pagination.**
    Mesure en production : un compte portait 3 222 resultats, tous distincts
    en base (3 222 empreintes de dedoublonnage distinctes) mais rigoureusement
    identiques a l'ecran, faute d'afficher le domaine et le nom du cookie.
    Paginer 3 222 lignes identiques ne fait que les etaler sur 162 pages.

    Renvoie des dictionnaires, pas des objets : un groupe n'est pas une ligne
    de la base, et lui donner l'apparence d'un modele inviterait a lui preter
    des proprietes qu'il n'a pas.
    """
    # order_by() VIDE, et ce n'est pas un detail : Django fait entrer les
    # colonnes de tri dans le GROUP BY. La liste arrive triee par date de
    # fuite puis par date de detection — deux colonnes distinctes sur chaque
    # ligne — ce qui donnait un groupe par ligne, soit exactement le defaut
    # qu'on corrige. Le tri des groupes se fait ensuite, sur leurs agregats.
    annote = queryset.order_by().annotate(service=_service_expression())
    lignes = annote.values(
        "account_id", "account__value", "account__label", "finding_type", "service"
    ).annotate(
        occurrences=Count("id"),
        ouverts=Count("id", filter=Q(status=WatchedAccountFinding.Status.OPEN)),
        traites=Count("id", filter=Q(status=WatchedAccountFinding.Status.TREATED)),
        ignores=Count("id", filter=Q(status=WatchedAccountFinding.Status.IGNORED)),
        plus_recente=Max("breach_date"),
        plus_ancienne=Min("breach_date"),
        derniere_detection=Max("detected_at"),
        # La gravite d'un groupe est la PIRE qu'il contient : annoncer
        # « Attention » sur un groupe qui renferme une fuite critique
        # tromperait sur l'urgence. Calcule en base, en une passe.
        rang_gravite=Max(
            Case(
                When(severity=BreachFinding.Severity.CRITICAL, then=Value(3)),
                When(severity=BreachFinding.Severity.HIGH, then=Value(2)),
                When(severity=BreachFinding.Severity.ATTENTION, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ),
    )

    par_rang = {rang: nom for nom, rang in SEVERITY_RANK.items()}
    groupes = [
        {
            "key": f"{ligne['account_id']}|{ligne['finding_type']}|{ligne['service']}",
            "account_id": ligne["account_id"],
            "account_value": ligne["account__value"],
            "account_label": ligne["account__label"],
            "finding_type": ligne["finding_type"],
            "service": ligne["service"],
            "occurrences": ligne["occurrences"],
            "open_count": ligne["ouverts"],
            "treated_count": ligne["traites"],
            "ignored_count": ligne["ignores"],
            "severity": par_rang.get(ligne["rang_gravite"], ""),
            "latest_breach_date": ligne["plus_recente"],
            "oldest_breach_date": ligne["plus_ancienne"],
            "last_detected_at": ligne["derniere_detection"],
        }
        for ligne in lignes
    ]

    groupes.sort(
        key=lambda g: (
            SEVERITY_RANK.get(g["severity"], 0),
            g["latest_breach_date"] or date.min,
            g["occurrences"],
        ),
        reverse=True,
    )
    return groupes


def findings_in_group(queryset, *, account_id, finding_type, service):
    """Le detail d'un groupe, quand on le deplie."""
    return (
        queryset.annotate(service=_service_expression())
        .filter(account_id=account_id, finding_type=finding_type, service=service)
        .order_by(F("breach_date").desc(nulls_last=True), "-detected_at")
    )


def watched_account_filter_options(tenant) -> dict:
    """Ce qui existe REELLEMENT chez ce client, pour peupler les filtres.

    Proposer un type que le client n'a pas produit un filtre qui ne renvoie
    jamais rien, et laisse croire a une panne.
    """
    # order_by() VIDE pour la meme raison que dans le regroupement : le
    # modele porte un ordre par defaut (-detected_at), et DISTINCT le fait
    # entrer dans le SELECT. Les valeurs redevenaient alors distinctes par
    # (type, date de detection), c'est-a-dire une entree de filtre par ligne.
    base = WatchedAccountFinding.all_objects.filter(tenant=tenant).order_by()
    return {
        "types": sorted(t for t in base.values_list("finding_type", flat=True).distinct() if t),
        "severities": sorted(
            (s for s in base.values_list("severity", flat=True).distinct() if s),
            key=lambda s: SEVERITY_RANK.get(s, 0),
            reverse=True,
        ),
    }


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
    tous = WatchedAccountFinding.all_objects.filter(tenant=tenant)
    return {
        "accounts": comptes.count(),
        "open_findings": ouverts.count(),
        "critical_findings": ouverts.filter(severity="critical").count(),
        "last_scanned_at": derniere,
        # A5.16 : ce qui vient de la reprise d'historique, et ce qui est
        # apparu depuis. Un client qui decouvre 3 000 entrees au premier
        # passage n'a pas 3 000 incidents du jour.
        "from_first_scan": tous.filter(from_first_scan=True).count(),
        "since_first_scan": tous.filter(from_first_scan=False).count(),
        # A3.9 : on masque, on ne cache pas. Le compteur dit ce qui a ete
        # traite ou ecarte, avec de quoi y revenir.
        "treated_findings": tous.filter(status=WatchedAccountFinding.Status.TREATED).count(),
        "ignored_findings": tous.filter(status=WatchedAccountFinding.Status.IGNORED).count(),
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
    # Le premier passage remonte tout l'historique du fournisseur ; les
    # suivants ne rapportent que du nouveau. La distinction est posee ICI,
    # au seul moment ou on la connait avec certitude.
    premier_passage = account.first_scanned_at is None

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
                "from_first_scan": premier_passage,
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

    if premier_passage:
        account.first_scanned_at = now
        account.save(update_fields=["first_scanned_at"])

    return crees, revus
