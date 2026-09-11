import csv
import logging

from django.core.cache import cache
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing import api_guards, entitlements, features
from apps.billing import capacity as platform_capacity
from apps.monitoring import services as monitoring_services
from apps.tenants.models import Membership
from apps.tenants.permissions import IsTenantAdmin, IsTenantMember, IsTenantMemberReadOnlyForReader

from . import finding_details, services
from . import quota as quota_module
from .models import (
    BreachFinding,
    BreachIntelligenceUsage,
    IdentifierAccessAudit,
    SecretRevealAudit,
)
from .reveal_throttle import RevealIPRateThrottle, RevealUserRateThrottle
from .serializers import (
    BreachFindingSerializer,
    BreachFindingStatusUpdateSerializer,
    BreachIntelligenceUsageSerializer,
    BreachScanJobSerializer,
    BreachScanTriggerSerializer,
    ExposureFeedSerializer,
    IdentifierAccessAuditSerializer,
    MonitoredAssetCreateSerializer,
    MonitoredAssetSerializer,
    PreIncidentSummarySerializer,
    SecretPurgeRunSerializer,
    SecretRevealAuditAdminSerializer,
    SecretRevealAuditSerializer,
    SecretRevealRequestSerializer,
    WatchedAccountCreateSerializer,
    WatchedAccountFindingSerializer,
    WatchedAccountFindingUpdateSerializer,
    WatchedAccountScanTriggerSerializer,
    WatchedAccountSerializer,
)
from .tasks import run_breach_scan_task, run_watched_account_scan_task
from .webhook_auth import is_valid_basic_auth

logger = logging.getLogger(__name__)


def _client_ip(request) -> str:
    # Same trust model as apps.accounts.views._client_ip: the only path to
    # this app in production is behind Caddy, which sets X-Forwarded-For —
    # never trust this header on a directly internet-facing process.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class IdentifierAwareMixin:
    """Sert les adresses selon le rôle, et trace ce qui a été servi en clair.

    Regroupé dans un mixin plutôt que recopié dans chaque vue : la garde de
    rôle et la trace vont ensemble, et une vue qui n'appliquerait que la
    première servirait des adresses sans laisser d'empreinte — exactement le
    reproche que la V2-2 corrige.
    """

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["viewer_role"] = getattr(self.request.membership, "role", None)
        return context

    def _tracer_acces(self, findings):
        services.record_identifier_access(
            tenant=self.request.tenant,
            user=self.request.user,
            context=IdentifierAccessAudit.Context.CONSULTATION,
            findings=findings,
            role=getattr(self.request.membership, "role", None),
            ip_address=_client_ip(self.request),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )


class BreachFindingListView(IdentifierAwareMixin, generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    serializer_class = BreachFindingSerializer

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        return services.list_findings(self.request.tenant, status=status_filter)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Tracé APRÈS la sérialisation, sur la page réellement servie : tracer
        # le queryset entier compterait des adresses que le client n'a pas
        # reçues, et la trace cesserait de dire ce qui a été vu.
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        self._tracer_acces(page if page is not None else [])
        return response


class BreachFindingDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def _get_or_404(self, request, finding_id):
        finding = services.get_finding(tenant=request.tenant, finding_id=finding_id)
        if finding is None:
            raise NotFound("Fuite introuvable.")
        return finding

    def _contexte(self, request):
        return {"viewer_role": getattr(request.membership, "role", None)}

    def _tracer(self, request, finding):
        services.record_identifier_access(
            tenant=request.tenant,
            user=request.user,
            context=IdentifierAccessAudit.Context.CONSULTATION,
            findings=[finding],
            role=getattr(request.membership, "role", None),
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

    def get(self, request, finding_id):
        finding = self._get_or_404(request, finding_id)
        self._tracer(request, finding)
        return Response(BreachFindingSerializer(finding, context=self._contexte(request)).data)

    def patch(self, request, finding_id):
        finding = self._get_or_404(request, finding_id)
        serializer = BreachFindingStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        finding = services.set_finding_status(
            finding, status=serializer.validated_data["status"], user=request.user
        )
        return Response(BreachFindingSerializer(finding, context=self._contexte(request)).data)


class BreachFindingRevealView(APIView):
    """POST /api/v1/threat-intelligence/findings/{id}/reveal/ (ADR-014, mise
    à jour) : déchiffre en mémoire le secret d'un finding et le renvoie une
    fois, jamais mis en cache/persisté à nouveau. Conditions cumulatives :
    (a) rôle admin du tenant OU utilisateur plateforme (is_staff) déjà membre
    de ce tenant — ``request.tenant``/``request.membership`` ne se résolvent
    que pour un tenant dont l'utilisateur est réellement membre (voir
    ``TenantScopingMiddleware``), donc même le bypass "admin plateforme" ne
    permet pas d'atteindre un tenant hors de sa propre appartenance (pas de
    mécanisme d'emprunt d'identité inter-tenant dans cette plateforme — un
    admin plateforme sans aucune adhésion ne peut révéler aucun finding) ;
    (b) ré-authentification fraîche (mot de passe ou code TOTP, vérifiée à
    chaque appel) ; (c) tenant-scoping strict (``services.get_finding``
    filtre déjà sur ``request.tenant``). La permission de rôle est vérifiée
    manuellement (pas via ``permission_classes``) pour que CHAQUE refus —
    y compris "rôle insuffisant" — soit tracé dans ``SecretRevealAudit``,
    ce que le court-circuit habituel de DRF sur un ``has_permission`` figé
    ne permettrait pas."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]
    throttle_classes = [RevealUserRateThrottle, RevealIPRateThrottle]

    def post(self, request, finding_id):
        ip_address = _client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        def _deny(*, denial_reason, finding=None, http_status, detail):
            services.record_reveal_attempt(
                tenant=request.tenant,
                finding=finding,
                user=request.user,
                success=False,
                denial_reason=denial_reason,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return Response({"detail": detail}, status=http_status)

        is_admin_or_platform_staff = request.membership.role == Membership.Role.ADMIN or bool(
            request.user.is_staff
        )
        if not is_admin_or_platform_staff:
            return _deny(
                denial_reason=SecretRevealAudit.DenialReason.ROLE,
                http_status=status.HTTP_403_FORBIDDEN,
                detail="Cette action nécessite le rôle administrateur sur l'entreprise "
                "(ou un accès administrateur plateforme).",
            )

        # La révélation est une fonctionnalité d'offre : vérifiée avant la
        # ré-authentification (inutile de faire saisir un mot de passe pour
        # refuser ensuite), et le refus est tracé comme tout autre refus.
        if not entitlements.has_feature(request.tenant, features.SECRET_REVEAL):
            plan = entitlements.cheapest_plan_with(features.SECRET_REVEAL)
            return _deny(
                denial_reason=SecretRevealAudit.DenialReason.ROLE,
                http_status=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    "La révélation de mot de passe n'est pas comprise dans votre offre"
                    + (f" ; elle est incluse à partir de l'offre {plan.name}." if plan else ".")
                ),
            )

        finding = services.get_finding(tenant=request.tenant, finding_id=finding_id)
        if finding is None:
            return _deny(
                denial_reason=SecretRevealAudit.DenialReason.NOT_FOUND,
                http_status=status.HTTP_404_NOT_FOUND,
                detail="Fuite introuvable.",
            )

        serializer = SecretRevealRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        step_up_ok = services.verify_step_up(
            user=request.user,
            password=serializer.validated_data["password"],
            totp_code=serializer.validated_data["totp_code"],
        )
        if not step_up_ok:
            return _deny(
                denial_reason=SecretRevealAudit.DenialReason.STEP_UP,
                finding=finding,
                http_status=status.HTTP_401_UNAUTHORIZED,
                detail="Ré-authentification invalide (mot de passe ou code incorrect).",
            )

        if not finding.has_secret or not bytes(finding.secret_encrypted):
            return _deny(
                denial_reason=SecretRevealAudit.DenialReason.NO_SECRET,
                finding=finding,
                http_status=status.HTTP_404_NOT_FOUND,
                detail="Aucun secret chiffré n'est disponible pour cette fuite.",
            )

        try:
            secret = services.decrypt_secret(bytes(finding.secret_encrypted))
        except services.ThreatIntelligenceError:
            # Le secret est là mais illisible avec les clés courantes : rotation
            # menée sans re-chiffrement, ancienne clé retirée trop tôt, ou donnée
            # corrompue. Renvoyer une 500 brute laisserait l'utilisateur devant
            # un plantage générique pour un problème d'exploitation identifiable.
            # La tentative est tracée comme les autres : c'est un accès refusé,
            # pas un non-événement.
            logger.error(
                "Secret illisible pour la fuite %s (tenant %s) : clé de chiffrement "
                "incorrecte ou donnée corrompue.",
                finding.id,
                request.tenant.id,
            )
            return _deny(
                denial_reason=SecretRevealAudit.DenialReason.NO_SECRET,
                finding=finding,
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Ce mot de passe est temporairement illisible. L'incident a été "
                    "signalé à l'administrateur de la plateforme."
                ),
            )
        services.record_reveal_attempt(
            tenant=request.tenant,
            finding=finding,
            user=request.user,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        response = Response({"finding_id": finding.id, "secret": secret})
        # Jamais mis en cache — ni par un proxy intermédiaire, ni par le
        # navigateur (ADR-014 : la révélation est ponctuelle, à usage unique
        # côté affichage).
        response["Cache-Control"] = "no-store"
        return response


class PreIncidentRadarView(APIView):
    """GET /api/v1/threat-intelligence/pre-incident/ — les signaux
    d'exposition publique (radar, dark web, surface d'attaque) du tenant,
    groupés par nature, avec pour chacun une phrase de vulgarisation et un
    niveau d'urgence. Distinct de la liste des fuites : c'est du
    pré-incident (« nous surveillons »), pas un constat (« ça a fuité »).

    ``?status=treated|ignored`` sert la vue d'historique « Voir les signaux
    traités » — depuis la Phase 8B la carte porte ses propres actions de
    traitement, donc un signal traité doit rester consultable quelque part."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        status_filter = request.query_params.get("status") or BreachFinding.Status.OPEN
        summary = services.build_pre_incident_summary(request.tenant, status=status_filter)
        return Response(PreIncidentSummarySerializer(summary).data)


class ExposureFeedView(APIView):
    """GET /api/v1/threat-intelligence/exposure-feed/ — la vue principale du
    produit (Phase 8B) : les fuites ouvertes groupées par actif, chaque
    groupe portant son score d'exposition explicable et, pour chaque fuite,
    sa vulgarisation et l'action recommandée. Groupes triés par score
    décroissant : ce qu'il faut regarder en premier arrive en premier.

    La synthèse IA est jointe si elle existe, mais n'est jamais générée ici
    (aucun appel IA dans le cycle requête/réponse — CLAUDE.md) : sa présence
    est optionnelle, la page est complète sans elle."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        role = getattr(request.membership, "role", None)
        feed = services.build_exposure_feed(request.tenant, role=role)
        # Le fil sert des adresses en clair comme la liste : même garde, même
        # trace. Une seule ligne pour toute la page, avec les actifs concernés.
        services.record_identifier_access(
            tenant=request.tenant,
            user=request.user,
            context=IdentifierAccessAudit.Context.CONSULTATION,
            findings=services.list_findings(
                request.tenant, status=BreachFinding.Status.OPEN, include_pre_incident=True
            ),
            role=role,
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        synthesis = services.get_exposure_synthesis(request.tenant)
        feed["synthesis"] = (
            {
                "content": synthesis.content,
                "generated_at": synthesis.generated_at,
                "is_stale": synthesis.is_stale,
            }
            if synthesis
            else None
        )
        return Response(ExposureFeedSerializer(feed).data)


class ExposureSynthesisRefreshView(APIView):
    """POST — déclenche la (re)génération de la synthèse via le pattern job
    asynchrone (ADR-011) : réponse 202 + id de job, le frontend sonde
    ``GET /api/v1/ai/jobs/{id}/`` comme pour les autres cas d'usage IA."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def post(self, request):
        from apps.ai_assistant import services as ai_services
        from apps.ai_assistant.models import AIJob
        from apps.ai_assistant.tasks import generate_exposure_synthesis_task

        try:
            entitlements.ensure_operational(request.tenant, action="La génération d'une analyse")
            entitlements.ensure_feature(request.tenant, features.EXPOSURE_SYNTHESIS)
        except entitlements.EntitlementError as exc:
            return Response(
                {"detail": exc.message, "required_plan": exc.required_plan},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            ai_services.ensure_ai_enabled(request.tenant)
            ai_services.ensure_quota_available(request.tenant)
        except ai_services.AIError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        if services.synthesis_cooldown_active(request.tenant):
            return Response(
                {"detail": ("Une analyse vient d'être générée. Réessayez dans quelques minutes.")},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        job = AIJob.all_objects.create(
            tenant=request.tenant,
            use_case=AIJob.UseCase.EXPOSURE_SYNTHESIS,
            status=AIJob.Status.PENDING,
            created_by=request.user,
        )
        generate_exposure_synthesis_task.delay(job.id)
        return Response({"job_id": job.id}, status=status.HTTP_202_ACCEPTED)


class SecretRevealAuditListView(generics.ListAPIView):
    """Journal des révélations du tenant courant — consultable par l'admin
    du tenant (ADR-014, mise à jour) ; jamais le secret lui-même."""

    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    serializer_class = SecretRevealAuditSerializer

    def get_queryset(self):
        return services.list_reveal_audits(self.request.tenant)


class IdentifierAccessAuditListView(generics.ListAPIView):
    """Journal des consultations d'adresses — consultable par l'admin du
    tenant (ADR-027).

    Même principe que le journal des révélations : une trace que seul
    l'éditeur peut lire ne prouve rien à celui qui en aurait besoin. C'est le
    client qui doit pouvoir répondre « voici qui a consulté, et quand » — à un
    salarié, à un délégué à la protection des données, à un auditeur.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    serializer_class = IdentifierAccessAuditSerializer

    def get_queryset(self):
        return services.list_identifier_access_audits(self.request.tenant)


class MonitoredAssetListCreateView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]
    serializer_class = MonitoredAssetSerializer

    def get_queryset(self):
        return services.list_monitored_assets(self.request.tenant)

    def post(self, request, *args, **kwargs):
        serializer = MonitoredAssetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = monitoring_services.get_asset(
            tenant=request.tenant, asset_id=serializer.validated_data["asset_id"]
        )
        if asset is None:
            raise NotFound("Actif introuvable.")

        # Deux plafonds indépendants : celui du client (son offre) et celui de
        # la plateforme (les 15 emplacements partagés). Un client peut avoir du
        # quota alors que la plateforme est saturée, et l'inverse.
        try:
            entitlements.ensure_operational(request.tenant, action="La surveillance en temps réel")
            entitlements.ensure_feature(request.tenant, features.REALTIME_MONITORING)
            entitlements.ensure_monitored_asset_quota(request.tenant)
        except entitlements.EntitlementError as exc:
            return Response(
                {"detail": exc.message, "required_plan": exc.required_plan},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            monitored = services.register_monitored_asset(tenant=request.tenant, asset=asset)
        except services.ThreatIntelligenceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MonitoredAssetSerializer(monitored).data, status=status.HTTP_201_CREATED)


class MonitoredAssetDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def delete(self, request, asset_id):
        monitored = services.get_monitored_asset(tenant=request.tenant, asset_id=asset_id)
        if monitored is None:
            raise NotFound("Cet actif n'est pas surveillé en temps réel.")
        services.unregister_monitored_asset(monitored)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BreachScanTriggerView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def post(self, request):
        serializer = BreachScanTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = None
        asset_id = serializer.validated_data.get("asset_id")
        if asset_id is not None:
            asset = monitoring_services.get_asset(tenant=request.tenant, asset_id=asset_id)
            if asset is None:
                raise NotFound("Actif introuvable.")

        # Une analyse consomme trois ressources distinctes, vérifiées dans cet
        # ordre : l'abonnement doit être opérationnel, le quota du client non
        # épuisé, et le budget mensuel de la PLATEFORME disponible (les 1000
        # requêtes sont partagées par tous les clients — ADR-013).
        try:
            entitlements.ensure_operational(request.tenant, action="Le lancement d'une analyse")
            entitlements.ensure_scan_quota(request.tenant)
            platform_capacity.ensure_scan_budget_available(additional=1)
        except entitlements.EntitlementError as exc:
            return Response({"detail": exc.message}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except platform_capacity.PlatformCapacityError as exc:
            # `client_message`, jamais `str(exc)` : le message d'exploitation
            # porte le compteur du parc (« 87/1000 ») et notre palier de
            # licence. Le back-office, lui, continue de lire `str(exc)`.
            logger.warning("Capacité plateforme atteinte : %s", exc)
            return Response(
                {"detail": exc.client_message}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        try:
            job = services.create_scan_job(
                tenant=request.tenant, asset=asset, triggered_by=services.TriggeredBy.MANUAL
            )
        except services.CooldownActiveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except quota_module.QuotaExceededError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        run_breach_scan_task.delay(
            tenant_id=str(request.tenant.id),
            asset_id=asset.id if asset else None,
            triggered_by=services.TriggeredBy.MANUAL,
            job_id=job.id,
        )
        return Response(BreachScanJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class BreachScanJobDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request, job_id):
        job = services.get_scan_job(tenant=request.tenant, job_id=job_id)
        if job is None:
            raise NotFound("Analyse introuvable.")
        return Response(BreachScanJobSerializer(job).data)


class ThreatIntelligenceStatusView(APIView):
    """État de SON espace, vu par un client — et rien de plus.

    Cette vue renvoyait auparavant des chiffres de PLATEFORME : le budget de
    requêtes partagé (« 971 restantes ») et l'occupation du pool de licence
    (« 0 / 15 emplacements »). Le frontend les affichait tels quels, avec le
    mot « plateforme » et la mention « pour toute la plateforme ».

    Deux problèmes, et le second est le vrai :

    1. Ces nombres ne veulent rien dire pour un client. « 971 requêtes
       restantes » n'est pas son quota : c'est celui de tout le monde. Il peut
       le voir descendre sans avoir rien fait, et le voir bloquer alors qu'il
       n'a lancé aucune analyse.
    2. Ils décrivent la consommation des AUTRES clients. Dans un produit dont
       l'argument est le cloisonnement, l'écran principal publiait l'état du
       parc. C'est une fuite entre locataires, dans l'interface cette fois et
       plus seulement dans les messages d'erreur.

    Ce que renvoie cette vue est désormais entièrement dérivé de l'offre du
    client : ses analyses, ses emplacements. Les plafonds de plateforme
    continuent de s'appliquer côté serveur (``billing.capacity``) — ils
    refusent quand il le faut, mais ne se racontent plus.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        tenant = request.tenant
        cooldown_key = services.SCAN_COOLDOWN_CACHE_KEY.format(tenant_id=tenant.id)
        subscription = entitlements.get_subscription(tenant)

        scans_quota = subscription.monthly_scans_quota if subscription else 0
        scans_used = entitlements.monthly_scans_used(tenant)
        assets_quota = subscription.monitored_assets_quota if subscription else 0
        assets_used = services.list_monitored_assets(tenant).count()

        return Response(
            {
                # 0 = illimité côté offre : on renvoie None plutôt que zéro,
                # qu'un affichage lirait comme « aucune analyse disponible ».
                "scans_quota": scans_quota or None,
                "scans_used": scans_used,
                "scans_remaining": (max(0, scans_quota - scans_used) if scans_quota else None),
                "monitored_quota": assets_quota or None,
                "monitored_used": assets_used,
                "monitored_remaining": (
                    max(0, assets_quota - assets_used) if assets_quota else None
                ),
                "cooldown_active": bool(cache.get(cooldown_key)),
                "cooldown_minutes": services.scan_cooldown_minutes(tenant),
                # Déjà formaté pour l'écran : « 30 minutes », « 2 h »,
                # « 1 h 30 ». Laisser le frontend recomposer la phrase
                # depuis un nombre de minutes produirait « 90 minutes ».
                "cooldown_label": services.format_cooldown(services.scan_cooldown_minutes(tenant)),
                "critical_open_findings": services.count_critical_open_findings(tenant),
                # Permet à l'écran de retrouver une analyse déjà lancée après
                # un changement de page ou un rechargement — le job tourne
                # côté worker, pas dans l'onglet.
                "running_scan_id": getattr(services.get_running_scan_job(tenant), "id", None),
                "last_scan_finished_at": getattr(
                    services.get_last_finished_scan_job(tenant), "finished_at", None
                ),
            }
        )


# --- Back-office plateforme (§9 du prompt Phase 7) --------------------------


class ThreatIntelligenceAdminStatusView(APIView):
    """Vue plateforme (pas tenant-scopée) : état du quota mensuel partagé,
    occupation des 15 slots monitorés, journal d'usage récent. Le back-
    office platform_admin est un scaffold vide à ce stade (réservé à une
    phase ultérieure — voir apps.platform_admin.apps) : cette vue est
    exposée ici, gardée par IsAdminUser (is_staff), plutôt que d'anticiper
    la construction du back-office complet, hors périmètre de cette phase."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        quota_summary = quota_module.get_quota_summary()
        pool = services.pool_summary()
        recent_usage = BreachIntelligenceUsage.all_objects.select_related("tenant").order_by(
            "-created_at"
        )[:50]
        recent_reveal_audits = services.list_reveal_audits_all_tenants(limit=50)
        return Response(
            {
                "quota": quota_summary,
                "pool": pool,
                "recent_usage": BreachIntelligenceUsageSerializer(recent_usage, many=True).data,
                # ADR-014 (mise à jour) : agrégat suffisamment non-sensible
                # (qui/quand/accordé ou refusé, jamais le secret ni le
                # détail du finding) pour être plateforme-entière, à la
                # différence d'un BreachFinding complet — voir docstring de
                # cette vue.
                "recent_reveal_audits": SecretRevealAuditAdminSerializer(
                    recent_reveal_audits, many=True
                ).data,
                # Phase 8C : la politique de rétention ne vaut que si l'on
                # peut constater qu'elle tourne réellement.
                "retention_policy": services.retention_policy(),
                "recent_purge_runs": SecretPurgeRunSerializer(
                    services.list_purge_runs(limit=20), many=True
                ).data,
            }
        )


# --- Webhook entrant (§7 du prompt Phase 7) ---------------------------------


@method_decorator(csrf_exempt, name="dispatch")
class BreachsenseWebhookView(APIView):
    """POST /api/v1/webhooks/breachsense — pas de JWT, pas d'en-tête
    X-Tenant-Id : authentification HTTP Basic uniquement (identifiants
    dans BREACHSENSE_WEBHOOK_USERNAME/PASSWORD, comparés en temps
    constant — voir webhook_auth.py), le tenant est résolu en interne via
    MonitoredAsset.provider_ref (ADR-013). AllowAny côté DRF puisque
    l'authentification n'est pas celle de la plateforme (pas de JWT)."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not is_valid_basic_auth(request):
            response = Response(
                {"detail": "Authentification requise."}, status=status.HTTP_401_UNAUTHORIZED
            )
            response["WWW-Authenticate"] = 'Basic realm="breachsense-webhook"'
            return response

        payload = request.data
        if not isinstance(payload, list):
            raise DRFValidationError("Le corps attendu est un tableau JSON d'événements.")

        result = services.ingest_webhook_payload(payload)
        return Response(result, status=status.HTTP_200_OK)


# --- Comptes désignés (V2-6, ADR-033) ---------------------------------------


class WatchedAccountListCreateView(APIView):
    """L'espace des comptes désignés : ce que le client a déclaré surveiller.

    Séparé des actifs et de l'exposition générale — ce ne sont pas ses actifs,
    ce sont des comptes qu'il surveille. La séparation est structurelle : ces
    lignes vivent dans leur propre table et n'entrent ni dans le score
    d'exposition, ni dans les indicateurs de comité.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def get(self, request):
        # LECTURE non gardée par l'offre : un client qui perd la
        # fonctionnalité doit continuer de voir ce qu'il a déclaré — et
        # pouvoir le retirer. Reprendre la liste lui interdirait d'arrêter une
        # surveillance qu'il a lui-même mise en place, ce qui serait le
        # contraire de ce que veut ADR-033.
        comptes = services.list_watched_accounts(
            request.tenant, include_removed=request.query_params.get("include_removed") == "1"
        )
        return Response(
            {
                "declaration_text": services.DECLARATION_TEXT,
                "declaration_version": services.DECLARATION_VERSION,
                "summary": services.watched_accounts_summary(request.tenant),
                "results": WatchedAccountSerializer(
                    comptes.prefetch_related("findings"), many=True
                ).data,
            }
        )

    def post(self, request):
        api_guards.ensure_feature(request.tenant, features.WATCHED_ACCOUNTS)

        serializer = WatchedAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            entitlements.ensure_operational(
                request.tenant, action="La surveillance de comptes désignés"
            )
            compte = services.declare_watched_account(
                tenant=request.tenant,
                user=request.user,
                value=data["value"],
                label=data["label"],
                category=data["category"],
                legal_basis=data["legal_basis"],
                purpose=data["purpose"],
                declaration_accepted=data["declaration_accepted"],
            )
        except entitlements.EntitlementError as exc:
            return Response({"detail": exc.message}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except services.DeclarationRequiredError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except services.WatchedAccountError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(WatchedAccountSerializer(compte).data, status=status.HTTP_201_CREATED)


class WatchedAccountDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def delete(self, request, account_id):
        """Arrête la surveillance. Jamais gardé par l'offre : arrêter de
        traiter les données d'un tiers ne doit dépendre d'aucun abonnement."""
        compte = services.get_watched_account(tenant=request.tenant, account_id=account_id)
        if compte is None:
            raise NotFound("Compte introuvable.")
        services.remove_watched_account(
            compte, user=request.user, reason=request.data.get("reason", "")
        )
        return Response(WatchedAccountSerializer(compte).data)


def _date_depuis(valeur):
    """Une periode de filtre, ou None. Une date illisible n'est pas une erreur
    du client : on l'ignore plutot que de lui renvoyer un 400 pour un filtre."""
    if not valeur:
        return None
    return parse_date(valeur)


class WatchedAccountFindingListView(APIView):
    """Les resultats des comptes designes : groupes par defaut, pagines toujours.

    **Pourquoi grouper plutot que seulement paginer.** Mesure en production :
    un compte portait 3 222 resultats. Tous distincts en base — 3 222
    empreintes de dedoublonnage distinctes, 470 couples (domaine, nom de
    cookie) — mais identiques a l'ecran faute d'afficher ce qui les distingue.
    Paginer sans grouper ne fait que repartir 3 222 lignes identiques sur 162
    pages. Personne ne traitera cela.

    Trois modes, un seul endpoint :

    - par defaut : la liste des GROUPES (compte, type, service d'origine) ;
    - ``?group=<cle>`` : le detail d'un groupe qu'on deplie ;
    - ``?flat=1`` : la liste ligne a ligne, pour l'export.

    Toujours pagine cote serveur : la reponse complete pesait 1,6 Mo et
    demandait 4,9 s de construction pour un seul compte. Borner l'affichage ne
    borne jamais l'analyse — les compteurs de ``summary`` continuent de porter
    sur l'ensemble.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        compte = None
        account_id = request.query_params.get("account")
        if account_id:
            compte = services.get_watched_account(tenant=request.tenant, account_id=account_id)
            if compte is None:
                raise NotFound("Compte introuvable.")

        base = services.list_watched_account_findings(
            request.tenant,
            account=compte,
            status=request.query_params.get("status"),
            severity=request.query_params.get("severity"),
            finding_type=request.query_params.get("type"),
            since=_date_depuis(request.query_params.get("since")),
            search=request.query_params.get("q"),
        )

        paginateur = PageNumberPagination()
        paginateur.page_size = int(request.query_params.get("page_size") or 25)
        paginateur.page_size_query_param = "page_size"
        paginateur.max_page_size = 200

        groupe = request.query_params.get("group")
        if groupe:
            try:
                account_pk, finding_type, service = groupe.split("|", 2)
            except ValueError as exc:
                raise DRFValidationError({"group": "Groupe illisible."}) from exc
            lignes = services.findings_in_group(
                base, account_id=account_pk, finding_type=finding_type, service=service
            )
            page = paginateur.paginate_queryset(lignes, request)
            return paginateur.get_paginated_response(
                WatchedAccountFindingSerializer(page, many=True).data
            )

        if request.query_params.get("flat"):
            page = paginateur.paginate_queryset(base, request)
            return paginateur.get_paginated_response(
                WatchedAccountFindingSerializer(page, many=True).data
            )

        groupes = services.group_watched_account_findings(base)
        page = paginateur.paginate_queryset(groupes, request)
        reponse = paginateur.get_paginated_response(page)
        # Les filtres se peuplent de ce qui existe REELLEMENT chez ce client :
        # proposer un type qu'il n'a pas donne un filtre qui ne renvoie jamais
        # rien, et laisse croire a une panne.
        reponse.data["filters"] = services.watched_account_filter_options(request.tenant)
        return reponse


class WatchedAccountFindingExportView(APIView):
    """L'export en tableur, filtre EXACTEMENT comme a l'ecran (A5.17).

    Un RSSI veut retravailler ses donnees. Exporter autre chose que ce qu'il
    voit — l'ensemble plutot que sa selection — lui donnerait un fichier qui
    ne correspond a rien de ce qu'il a demande.

    Ligne a ligne et non par groupes : le groupe sert a LIRE, le fichier sert
    a trier et filtrer ailleurs. Les champs distinctifs y figurent en
    colonnes, ce qui est precisement ce qui manquait a l'ecran d'origine.
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantMember]

    def get(self, request):
        compte = None
        account_id = request.query_params.get("account")
        if account_id:
            compte = services.get_watched_account(tenant=request.tenant, account_id=account_id)
            if compte is None:
                raise NotFound("Compte introuvable.")

        lignes = services.list_watched_account_findings(
            request.tenant,
            account=compte,
            status=request.query_params.get("status"),
            severity=request.query_params.get("severity"),
            finding_type=request.query_params.get("type"),
            since=_date_depuis(request.query_params.get("since")),
            search=request.query_params.get("q"),
        )

        reponse = HttpResponse(content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = 'attachment; filename="comptes-surveilles.csv"'
        # Le separateur point-virgule et le BOM : sans eux, Excel en francais
        # ouvre le fichier en une seule colonne et abime les accents. Un
        # export qu'il faut reparer a la main n'est pas un export.
        reponse.write("\ufeff")
        plume = csv.writer(reponse, delimiter=";")
        plume.writerow(
            [
                "Compte",
                "Libelle",
                "Type",
                "Gravite",
                "Statut",
                "Date de fuite",
                "Detecte le",
                "Mot de passe expose",
                "Origine",
                "Details",
            ]
        )
        for ligne in lignes.iterator(chunk_size=500):
            details = finding_details.details_for(ligne)
            plume.writerow(
                [
                    ligne.account.value,
                    ligne.account.label,
                    ligne.finding_type,
                    ligne.get_severity_display(),
                    ligne.get_status_display(),
                    ligne.breach_date or "date inconnue",
                    ligne.detected_at.date() if ligne.detected_at else "",
                    "oui" if ligne.has_secret else "non",
                    "historique" if ligne.from_first_scan else "apparu depuis",
                    " | ".join(f"{d['label']} : {d['value']}" for d in details),
                ]
            )
        return reponse


class WatchedAccountFindingDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def patch(self, request, finding_id):
        resultat = services.get_watched_account_finding(
            tenant=request.tenant, finding_id=finding_id
        )
        if resultat is None:
            raise NotFound("Résultat introuvable.")
        serializer = WatchedAccountFindingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_watched_account_finding_status(
            resultat, serializer.validated_data["status"]
        )
        return Response(WatchedAccountFindingSerializer(resultat).data)


class WatchedAccountScanTriggerView(APIView):
    """Analyse à la demande, sur un ou plusieurs comptes."""

    permission_classes = [permissions.IsAuthenticated, IsTenantMemberReadOnlyForReader]

    def post(self, request):
        api_guards.ensure_feature(request.tenant, features.WATCHED_ACCOUNTS)

        serializer = WatchedAccountScanTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comptes = services.resolve_scan_targets(
            request.tenant, account_ids=serializer.validated_data["account_ids"] or None
        )
        if not comptes:
            return Response(
                {"detail": "Aucun compte à analyser."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Trois ressources, vérifiées dans cet ordre, comme pour les actifs :
        # l'abonnement doit être opérationnel, le quota VIP du client non
        # épuisé — c'est un quota À PART, il ne consomme pas celui des actifs
        # — et le budget mensuel de la PLATEFORME disponible.
        try:
            entitlements.ensure_operational(request.tenant, action="Le lancement d'une analyse")
            entitlements.ensure_watched_account_scan_quota(request.tenant)
            platform_capacity.ensure_scan_budget_available(additional=len(comptes))
        except entitlements.EntitlementError as exc:
            return Response({"detail": exc.message}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except platform_capacity.PlatformCapacityError as exc:
            logger.warning("Capacité plateforme atteinte : %s", exc)
            return Response(
                {"detail": exc.client_message}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        job = services.create_watched_account_scan_job(
            tenant=request.tenant, user=request.user, accounts=comptes
        )
        run_watched_account_scan_task.delay(tenant_id=str(request.tenant.id), job_id=job.id)
        return Response(BreachScanJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
