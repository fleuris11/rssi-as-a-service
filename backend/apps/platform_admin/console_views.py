"""Opérations d'écriture de la console d'administration (phase 11).

Ce module ne contient **aucune règle métier** : chaque vue valide la forme,
appelle le service de l'app concernée, traduit l'exception métier en code HTTP
et journalise. C'est la contrepartie de la règle « une seule règle métier par
opération, côté serveur ».

Traduction des erreurs, uniforme dans tout le module :

===== ============================================================
 402   L'abonnement du client ne permet pas l'opération (quota, offre)
 409   La PLATEFORME ne peut pas honorer l'opération (capacité, conflit)
 422   La demande est cohérente mais viole une règle métier
===== ============================================================

Le 409 est réservé aux refus de capacité : la demande est légitime, c'est
l'état de la plateforme qui la rend impossible — ni une erreur de l'appelant,
ni une panne.
"""

import csv
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing import capacity, entitlements
from apps.billing import services as billing_services
from apps.billing.models import Plan
from apps.billing.serializers import PublicPlanSerializer
from apps.marketing import services as marketing_services
from apps.marketing.models import DemoRequest
from apps.tenants import services as tenant_services
from apps.tenants.models import Membership, Tenant

from . import services, settings_registry
from .console_serializers import (
    AdminInviteSerializer,
    AdminLevelSerializer,
    ClientCreateSerializer,
    MemberInviteSerializer,
    MemberSerializer,
    MemberUpdateSerializer,
    MonitoredAssetCreateSerializer,
    PlanDuplicateSerializer,
    PlanImpactSerializer,
    ProspectNoteSerializer,
    ProspectSerializer,
    ProspectWriteSerializer,
    SettingUpdateSerializer,
    SubscriptionUpdateSerializer,
    TenantActionSerializer,
    TenantSerializer,
    TenantUpdateSerializer,
)
from .models import AdminAuditLog, PlatformAdminProfile
from .permissions import IsFullPlatformAdmin, IsPlatformAdmin, admin_level

logger = logging.getLogger(__name__)
User = get_user_model()


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class ConsoleView(APIView):
    """Base des écrans de gestion : lecture pour tout administrateur, écriture
    réservée au niveau complet."""

    permission_classes = [IsFullPlatformAdmin]

    def audit(self, request, action, *, tenant=None, target="", detail="", changes=None):
        return services.record_admin_action(
            actor=request.user,
            action=action,
            tenant=tenant,
            target=target,
            detail=detail,
            changes=changes,
            ip_address=_client_ip(request),
        )

    def refused(self, exc, code):
        return Response({"detail": str(exc)}, status=code)


def invitation_payload(raw_token: str, *, email: str, sent: bool) -> dict:
    """Ce qu'on renvoie après avoir émis un lien d'accès.

    Le lien est renvoyé À LA CONSOLE, pas au navigateur du destinataire : c'est
    la seule façon d'inviter quelqu'un tant qu'aucun serveur d'envoi n'est
    configuré. Il n'est stocké nulle part en clair et n'apparaît pas dans le
    journal d'audit.
    """
    from apps.accounts.services import invitation_url

    return {
        "invitation_url": invitation_url(raw_token),
        "invitation_email": email,
        "email_sent": sent,
        "expires_in_hours": 72,
    }


def send_invitation_email(*, user, raw_token: str, purpose_label: str) -> bool:
    """Envoie le lien si un serveur d'envoi est configuré. Best-effort : la
    console affiche de toute façon le lien à copier, donc un incident SMTP ne
    doit jamais faire échouer la création du compte."""
    from django.conf import settings as django_settings
    from django.core.mail import send_mail

    from apps.accounts.services import invitation_url

    if not getattr(django_settings, "EMAIL_HOST", ""):
        return False
    try:
        send_mail(
            subject=f"{purpose_label} — RSSI as a Service",
            message=(
                f"Bonjour,\n\n"
                f"Un accès vous a été ouvert sur la plateforme RSSI as a Service.\n"
                f"Définissez votre mot de passe avec ce lien :\n\n"
                f"{invitation_url(raw_token)}\n\n"
                f"Ce lien est valable 72 heures et ne fonctionne qu'une fois.\n"
            ),
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return True
    except Exception:  # noqa: BLE001 - le lien reste affiché dans la console
        logger.warning("Email d'invitation non envoyé à %s", user.pk, exc_info=True)
        return False


# --- Clients ----------------------------------------------------------------


class ClientCreateView(ConsoleView):
    """Création d'un client complet : entreprise + premier utilisateur +
    abonnement, en une opération atomique."""

    def post(self, request):
        serializer = ClientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        plan = None
        if data.get("plan_code"):
            plan = get_object_or_404(Plan, code=data["plan_code"])

        prospect = None
        if data.get("prospect_id"):
            prospect = DemoRequest.objects.filter(id=data["prospect_id"]).first()

        tenant_fields = {
            key: data.get(key, "")
            for key in (
                "sector",
                "contact_email",
                "contact_phone",
                "address",
                "website",
                "account_manager",
                "internal_notes",
            )
        }
        tenant_fields["headcount"] = data.get("headcount")

        try:
            with transaction.atomic():
                tenant, user, subscription, raw_token = tenant_services.create_client(
                    name=data["name"],
                    owner_email=data["owner_email"],
                    owner_first_name=data["owner_first_name"],
                    owner_last_name=data["owner_last_name"],
                    plan=plan,
                    engagement=data["engagement"],
                    trial_days=data.get("trial_days"),
                    actor=request.user,
                    **tenant_fields,
                )
                if prospect is not None:
                    marketing_services.mark_converted(prospect=prospect, tenant=tenant)
        except capacity.PlatformCapacityError as exc:
            return self.refused(exc, status.HTTP_409_CONFLICT)
        except tenant_services.TenantError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
        except billing_services.BillingError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        sent = send_invitation_email(
            user=user, raw_token=raw_token, purpose_label="Votre accès à la plateforme"
        )
        self.audit(
            request,
            AdminAuditLog.Action.TENANT_CREATED,
            tenant=tenant,
            target=tenant.name,
            detail=(
                f"Offre {subscription.plan.name}, {subscription.get_status_display().lower()}. "
                f"Propriétaire : {user.email}."
                + (f" Converti depuis le prospect {prospect.id}." if prospect else "")
            ),
        )
        return Response(
            {
                **services.tenant_detail(tenant),
                "invitation": invitation_payload(raw_token, email=user.email, sent=sent),
            },
            status=status.HTTP_201_CREATED,
        )


class ClientDetailView(ConsoleView):
    def get(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        return Response(
            {
                **services.tenant_detail(tenant),
                "fiche": TenantSerializer(tenant).data,
            }
        )

    def patch(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        serializer = TenantUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            tenant, changes = tenant_services.update_tenant(
                tenant=tenant, **serializer.validated_data
            )
        except tenant_services.TenantError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Aucune ligne d'audit si rien n'a changé : une modification sans
        # changement n'est pas un acte de gestion.
        if changes:
            self.audit(
                request,
                AdminAuditLog.Action.TENANT_UPDATED,
                tenant=tenant,
                target=tenant.name,
                changes=changes,
            )
        return Response({**services.tenant_detail(tenant), "fiche": TenantSerializer(tenant).data})

    def delete(self, request, tenant_id):
        """Suppression DÉFINITIVE. Le nom doit être retapé (``confirm_name``) :
        c'est la seule action irréversible de la console."""
        tenant = get_object_or_404(Tenant, id=tenant_id)
        if request.data.get("confirm_name", "").strip() != tenant.name:
            return Response(
                {
                    "detail": "Pour supprimer définitivement, retapez exactement le nom de "
                    f"l'entreprise : « {tenant.name} »."
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        try:
            name = tenant_services.delete_tenant_permanently(tenant=tenant)
        except tenant_services.TenantError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        self.audit(
            request,
            AdminAuditLog.Action.TENANT_DELETED,
            target=name,
            detail="Suppression définitive depuis la corbeille.",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClientArchiveView(ConsoleView):
    def post(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        restore = bool(request.data.get("restore"))

        if restore:
            tenant_services.restore_tenant(tenant=tenant)
            self.audit(
                request,
                AdminAuditLog.Action.TENANT_RESTORED,
                tenant=tenant,
                target=tenant.name,
                detail="L'abonnement reste résilié : réactivez-le si nécessaire.",
            )
        else:
            tenant_services.archive_tenant(
                tenant=tenant, actor=request.user, reason=request.data.get("reason", "")
            )
            self.audit(
                request,
                AdminAuditLog.Action.TENANT_ARCHIVED,
                tenant=tenant,
                target=tenant.name,
                detail=request.data.get("reason", ""),
            )
        return Response({**services.tenant_detail(tenant), "fiche": TenantSerializer(tenant).data})


class TrashView(ConsoleView):
    def get(self, request):
        retention = int(settings_registry.get(settings_registry.TRASH_RETENTION_DAYS))
        rows = []
        for tenant in tenant_services.list_archived_tenants():
            age = (timezone.now() - tenant.archived_at).days
            rows.append(
                {
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "archived_at": tenant.archived_at,
                    "archived_by": getattr(tenant.archived_by, "email", ""),
                    "reason": tenant.archive_reason,
                    "days_since_archive": age,
                    "purgeable": age >= retention,
                }
            )
        return Response({"retention_days": retention, "tenants": rows})


# --- Utilisateurs d'un client -----------------------------------------------


class ClientMemberListView(ConsoleView):
    def get(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        members = tenant_services.list_members_with_status(tenant)
        return Response(MemberSerializer(members, many=True).data)

    def post(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        serializer = MemberInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            membership, raw_token = tenant_services.invite_member(
                tenant=tenant, actor=request.user, **serializer.validated_data
            )
        except entitlements.EntitlementError as exc:
            return self.refused(exc, status.HTTP_402_PAYMENT_REQUIRED)
        except tenant_services.TenantError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        sent = send_invitation_email(
            user=membership.user,
            raw_token=raw_token,
            purpose_label="Votre accès à la plateforme",
        )
        self.audit(
            request,
            AdminAuditLog.Action.USER_INVITED,
            tenant=tenant,
            target=membership.user.email,
            detail=f"Rôle : {membership.get_role_display()}.",
        )
        return Response(
            {
                **MemberSerializer(membership).data,
                "invitation": invitation_payload(
                    raw_token, email=membership.user.email, sent=sent
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class ClientMemberDetailView(ConsoleView):
    def _membership(self, tenant_id, membership_id):
        return get_object_or_404(
            Membership.all_objects.select_related("user"),
            id=membership_id,
            tenant_id=tenant_id,
        )

    def patch(self, request, tenant_id, membership_id):
        membership = self._membership(tenant_id, membership_id)
        serializer = MemberUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            if "role" in data and data["role"] != membership.role:
                previous = membership.get_role_display()
                tenant_services.change_member_role(membership=membership, role=data["role"])
                self.audit(
                    request,
                    AdminAuditLog.Action.USER_ROLE_CHANGED,
                    tenant=membership.tenant,
                    target=membership.user.email,
                    changes={"role": [previous, membership.get_role_display()]},
                )
            if "is_active" in data and data["is_active"] != membership.user.is_active:
                tenant_services.set_member_active(
                    membership=membership, active=data["is_active"]
                )
                self.audit(
                    request,
                    AdminAuditLog.Action.USER_REACTIVATED
                    if data["is_active"]
                    else AdminAuditLog.Action.USER_DEACTIVATED,
                    tenant=membership.tenant,
                    target=membership.user.email,
                )
        except tenant_services.TenantError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        membership.refresh_from_db()
        return Response(MemberSerializer(membership).data)

    def delete(self, request, tenant_id, membership_id):
        membership = self._membership(tenant_id, membership_id)
        tenant = membership.tenant
        try:
            email = tenant_services.remove_member(membership=membership)
        except tenant_services.TenantError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        self.audit(
            request,
            AdminAuditLog.Action.USER_REMOVED,
            tenant=tenant,
            target=email,
            detail="Le compte subsiste : il peut appartenir à d'autres entreprises.",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemberPasswordResetView(ConsoleView):
    """Émet un lien de réinitialisation. L'administrateur ne voit, ne choisit
    et ne transmet jamais le mot de passe lui-même."""

    def post(self, request, tenant_id, membership_id):
        membership = get_object_or_404(
            Membership.all_objects.select_related("user"),
            id=membership_id,
            tenant_id=tenant_id,
        )
        from apps.accounts.models import AccessInvitation
        from apps.accounts.services import create_access_invitation

        _invitation, raw_token = create_access_invitation(
            user=membership.user,
            purpose=AccessInvitation.Purpose.RESET,
            actor=request.user,
        )
        sent = send_invitation_email(
            user=membership.user,
            raw_token=raw_token,
            purpose_label="Réinitialisation de votre mot de passe",
        )
        self.audit(
            request,
            AdminAuditLog.Action.PASSWORD_RESET_SENT,
            tenant=membership.tenant,
            target=membership.user.email,
        )
        return Response(
            invitation_payload(raw_token, email=membership.user.email, sent=sent)
        )


# --- Abonnement d'un client -------------------------------------------------


class SubscriptionDetailView(ConsoleView):
    """Échéance d'essai, périodicité, notes et quotas négociés.

    Les transitions d'état (activer, suspendre, résilier, changer d'offre)
    restent sur ``AdminSubscriptionActionView`` : ce sont des actes distincts,
    tracés distinctement.
    """

    def patch(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        subscription = entitlements.get_subscription(tenant)
        if subscription is None:
            return Response(
                {"detail": "Cette entreprise n'a pas d'abonnement."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        before = billing_services.snapshot_subscription(subscription)

        try:
            if "trial_ends_at" in data:
                billing_services.set_trial_end(
                    subscription=subscription,
                    ends_at=data["trial_ends_at"],
                    actor=request.user,
                )
            if "internal_notes" in data:
                billing_services.set_internal_notes(
                    subscription=subscription, notes=data["internal_notes"]
                )
            overrides = {
                key: value
                for key, value in data.items()
                if key in billing_services.OVERRIDE_FIELDS
            }
            if overrides:
                billing_services.set_quota_overrides(
                    subscription=subscription, actor=request.user, **overrides
                )
            if "period" in data and data["period"] != subscription.period:
                subscription.period = data["period"]
                subscription.save(update_fields=["period", "updated_at"])
        except capacity.PlatformCapacityError as exc:
            return self.refused(exc, status.HTTP_409_CONFLICT)
        except billing_services.BillingError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        subscription.refresh_from_db()
        changes = services.diff_fields(
            before, billing_services.snapshot_subscription(subscription)
        )
        if changes:
            action = (
                AdminAuditLog.Action.QUOTA_OVERRIDDEN
                if any(field.startswith("override_") for field in changes)
                else AdminAuditLog.Action.SUBSCRIPTION_UPDATED
            )
            self.audit(
                request,
                action,
                tenant=tenant,
                target=tenant.name,
                changes=changes,
            )
        return Response(services.tenant_detail(tenant))


# --- Actifs surveillés et actions sur les données ---------------------------


class ClientMonitoredAssetView(ConsoleView):
    """Surveillance continue d'un client, pilotée depuis la console.

    Ne donne accès à AUCUN contenu de compromission (ADR-014) : on manipule
    des actifs déclarés et des emplacements, pas des fuites.
    """

    def get(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        from apps.monitoring.models import Asset
        from apps.threat_intelligence.models import MonitoredAsset

        monitored = MonitoredAsset.all_objects.filter(tenant=tenant).select_related("asset")
        monitored_ids = {m.asset_id for m in monitored}
        assets = Asset.all_objects.filter(tenant=tenant)
        return Response(
            {
                "monitored": [
                    {
                        "id": m.id,
                        "asset_id": m.asset_id,
                        "value": m.asset.value,
                        "is_active": m.is_active,
                    }
                    for m in monitored
                ],
                "available": [
                    {"id": a.id, "value": a.value, "kind": a.kind}
                    for a in assets
                    if a.id not in monitored_ids
                ],
                "quota": entitlements.get_subscription(tenant).monitored_assets_quota
                if entitlements.get_subscription(tenant)
                else 0,
            }
        )

    def post(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        serializer = MonitoredAssetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.monitoring.models import Asset
        from apps.threat_intelligence import services as ti_services

        asset = get_object_or_404(
            Asset.all_objects, id=serializer.validated_data["asset_id"], tenant=tenant
        )
        try:
            entitlements.ensure_operational(tenant, action="La surveillance continue")
            entitlements.ensure_monitored_asset_quota(tenant)
            capacity.ensure_monitored_slots_available(additional=1)
            monitored = ti_services.register_monitored_asset(tenant=tenant, asset=asset)
        except entitlements.EntitlementError as exc:
            return self.refused(exc, status.HTTP_402_PAYMENT_REQUIRED)
        except capacity.PlatformCapacityError as exc:
            return self.refused(exc, status.HTTP_409_CONFLICT)

        self.audit(
            request,
            AdminAuditLog.Action.MONITORED_ASSET_ADDED,
            tenant=tenant,
            target=asset.value,
        )
        return Response({"id": monitored.id}, status=status.HTTP_201_CREATED)

    def delete(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        from apps.monitoring.models import Asset
        from apps.threat_intelligence import services as ti_services

        asset = get_object_or_404(
            Asset.all_objects, id=request.data.get("asset_id"), tenant=tenant
        )
        ti_services.unregister_monitored_asset(tenant=tenant, asset=asset)
        self.audit(
            request,
            AdminAuditLog.Action.MONITORED_ASSET_REMOVED,
            tenant=tenant,
            target=asset.value,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClientActionView(ConsoleView):
    """Déclenche une action sur les données d'un client sans en consulter le
    contenu : on lance, on ne lit pas (ADR-014)."""

    def post(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        serializer = TenantActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        if action == "scan":
            from apps.threat_intelligence import services as ti_services
            from apps.threat_intelligence.quota import QuotaExceededError, QuotaManager
            from apps.threat_intelligence.tasks import run_breach_scan

            try:
                entitlements.ensure_operational(tenant, action="Une analyse")
                entitlements.ensure_scan_quota(tenant)
                QuotaManager().ensure_query_budget_available()
            except entitlements.EntitlementError as exc:
                return self.refused(exc, status.HTTP_402_PAYMENT_REQUIRED)
            except QuotaExceededError as exc:
                return self.refused(exc, status.HTTP_409_CONFLICT)

            job = ti_services.create_scan_job(
                tenant=tenant, asset=None, triggered_by="platform_admin"
            )
            run_breach_scan.delay(str(tenant.id), job.id)
            self.audit(
                request,
                AdminAuditLog.Action.SCAN_TRIGGERED,
                tenant=tenant,
                target=tenant.name,
            )
            return Response({"job_id": job.id}, status=status.HTTP_202_ACCEPTED)

        if action == "refresh_synthesis":
            from apps.threat_intelligence.tasks import refresh_exposure_synthesis

            try:
                entitlements.ensure_operational(tenant, action="La synthèse d'exposition")
            except entitlements.EntitlementError as exc:
                return self.refused(exc, status.HTTP_402_PAYMENT_REQUIRED)

            refresh_exposure_synthesis.delay(str(tenant.id))
            self.audit(
                request,
                AdminAuditLog.Action.SCAN_TRIGGERED,
                tenant=tenant,
                target=tenant.name,
                detail="Régénération de la synthèse d'exposition.",
            )
            return Response(status=status.HTTP_202_ACCEPTED)

        # purge_secrets
        from apps.threat_intelligence.models import BreachFinding

        purged = 0
        for finding in BreachFinding.all_objects.filter(
            tenant=tenant, encrypted_secret__isnull=False, secret_purged_at__isnull=True
        ):
            finding.encrypted_secret = None
            finding.secret_purged_at = timezone.now()
            finding.save(update_fields=["encrypted_secret", "secret_purged_at"])
            purged += 1

        self.audit(
            request,
            AdminAuditLog.Action.SECRETS_PURGED,
            tenant=tenant,
            target=tenant.name,
            detail=f"{purged} secret(s) effacé(s). Les fuites restent, leurs mots de passe non.",
        )
        return Response({"purged": purged})


# --- Catalogue --------------------------------------------------------------


class PlanImpactView(ConsoleView):
    """Aperçu AVANT confirmation. N'écrit rien."""

    def post(self, request, plan_code):
        plan = get_object_or_404(Plan, code=plan_code)
        serializer = PlanImpactSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        impact = billing_services.plan_impact(plan=plan, changes=serializer.validated_data)
        allowed, message = billing_services.can_delete_plan(plan)
        return Response({**impact, "can_delete": allowed, "delete_blocked_reason": message})


class PlanDuplicateView(ConsoleView):
    def post(self, request, plan_code):
        plan = get_object_or_404(Plan, code=plan_code)
        serializer = PlanDuplicateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            clone = billing_services.duplicate_plan(plan=plan, **serializer.validated_data)
        except billing_services.BillingError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        self.audit(
            request,
            AdminAuditLog.Action.PLAN_DUPLICATED,
            target=clone.name,
            detail=f"Copie de « {plan.name} », créée en brouillon.",
        )
        from .serializers import PlanAdminSerializer

        return Response(PlanAdminSerializer(clone).data, status=status.HTTP_201_CREATED)


class PlanDeleteView(ConsoleView):
    def delete(self, request, plan_code):
        plan = get_object_or_404(Plan, code=plan_code)
        try:
            name = billing_services.delete_plan(plan=plan)
        except billing_services.BillingError as exc:
            return self.refused(exc, status.HTTP_409_CONFLICT)

        self.audit(request, AdminAuditLog.Action.PLAN_RETIRED, target=name, detail="Offre supprimée.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlanPreviewView(ConsoleView):
    """Rendu de l'offre tel qu'il apparaîtra sur la vitrine — le même
    sérialiseur que l'endpoint public, sans le filtre « publiée »."""

    def get(self, request, plan_code):
        plan = get_object_or_404(Plan, code=plan_code)
        return Response(
            {
                "plan": PublicPlanSerializer(plan).data,
                "is_visible_publicly": plan.status == Plan.Status.PUBLISHED,
            }
        )


# --- Prospects --------------------------------------------------------------


class ProspectListView(ConsoleView):
    # Un commercial doit pouvoir créer et travailler ses prospects : c'est le
    # seul domaine d'écriture ouvert à son niveau.
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        prospects = DemoRequest.objects.prefetch_related("notes").select_related(
            "owner", "converted_tenant"
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            prospects = prospects.filter(status=status_filter)
        if request.query_params.get("open") == "1":
            prospects = prospects.exclude(status__in=DemoRequest.TERMINAL_STATUSES)
        return Response(
            {
                "prospects": ProspectSerializer(prospects[:200], many=True).data,
                "open_count": DemoRequest.objects.exclude(
                    status__in=DemoRequest.TERMINAL_STATUSES
                ).count(),
            }
        )

    def post(self, request):
        serializer = ProspectWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            prospect = marketing_services.create_prospect(
                actor=request.user, **serializer.validated_data
            )
        except marketing_services.ProspectError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        self.audit(
            request,
            AdminAuditLog.Action.PROSPECT_CREATED,
            target=prospect.company,
            detail=f"Saisie manuelle — {prospect.full_name}.",
        )
        return Response(ProspectSerializer(prospect).data, status=status.HTTP_201_CREATED)


class ProspectDetailView(ConsoleView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, prospect_id):
        prospect = get_object_or_404(DemoRequest, id=prospect_id)
        return Response(ProspectSerializer(prospect).data)

    def patch(self, request, prospect_id):
        prospect = get_object_or_404(DemoRequest, id=prospect_id)
        serializer = ProspectWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            prospect, changes = marketing_services.update_prospect(
                prospect=prospect, **serializer.validated_data
            )
        except marketing_services.ProspectError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        if changes:
            self.audit(
                request,
                AdminAuditLog.Action.PROSPECT_UPDATED,
                target=prospect.company,
                changes=changes,
            )
        return Response(ProspectSerializer(prospect).data)


class ProspectNoteView(ConsoleView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, prospect_id):
        prospect = get_object_or_404(DemoRequest, id=prospect_id)
        try:
            note = marketing_services.add_prospect_note(
                prospect=prospect, body=request.data.get("body", ""), author=request.user
            )
        except marketing_services.ProspectError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        self.audit(
            request, AdminAuditLog.Action.PROSPECT_NOTE_ADDED, target=prospect.company
        )
        return Response(ProspectNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class FollowUpBoardView(ConsoleView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        board = marketing_services.follow_up_board()
        return Response(
            {
                "due_today": ProspectSerializer(board["due_today"], many=True).data,
                "stale": ProspectSerializer(board["stale"], many=True).data,
                "stale_after_days": board["stale_after_days"],
            }
        )


# --- Administrateurs de la plateforme ---------------------------------------


class PlatformAdminListView(ConsoleView):
    def get(self, request):
        return Response(
            {
                "admins": services.list_platform_admins(),
                "levels": [
                    {"value": value, "label": label}
                    for value, label in PlatformAdminProfile.Level.choices
                ],
                "my_level": admin_level(request.user),
            }
        )

    def post(self, request):
        serializer = AdminInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, raw_token = services.invite_platform_admin(
                actor=request.user, **serializer.validated_data
            )
        except services.AdminManagementError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        sent = send_invitation_email(
            user=user, raw_token=raw_token, purpose_label="Votre accès administrateur"
        )
        self.audit(
            request,
            AdminAuditLog.Action.ADMIN_INVITED,
            target=user.email,
            detail=f"Niveau : {serializer.validated_data['level']}.",
        )
        return Response(
            {
                "admin": next(
                    (a for a in services.list_platform_admins() if a["email"] == user.email),
                    None,
                ),
                "invitation": invitation_payload(raw_token, email=user.email, sent=sent),
            },
            status=status.HTTP_201_CREATED,
        )


class PlatformAdminDetailView(ConsoleView):
    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id, is_staff=True)
        serializer = AdminLevelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        previous = admin_level(user)
        try:
            services.change_admin_level(
                user=user, level=serializer.validated_data["level"], actor=request.user
            )
        except services.AdminManagementError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        self.audit(
            request,
            AdminAuditLog.Action.ADMIN_LEVEL_CHANGED,
            target=user.email,
            changes={"level": [previous, serializer.validated_data["level"]]},
        )
        return Response({"admins": services.list_platform_admins()})

    def delete(self, request, user_id):
        user = get_object_or_404(User, id=user_id, is_staff=True)
        try:
            email = services.revoke_platform_admin(user=user, actor=request.user)
        except services.AdminManagementError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        self.audit(request, AdminAuditLog.Action.ADMIN_REVOKED, target=email)
        return Response({"admins": services.list_platform_admins()})


# --- Réglages ---------------------------------------------------------------


class PlatformSettingsView(ConsoleView):
    def get(self, request):
        return Response({"settings": settings_registry.describe()})

    def patch(self, request):
        serializer = SettingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data["key"]
        value = serializer.validated_data["value"]

        warning = ""
        try:
            warning = services.capacity_setting_warning(key=key, new_value=value)
        except (TypeError, ValueError):
            # La valeur sera de toute façon rejetée par ``coerce`` juste après,
            # avec un message qui nomme le réglage.
            warning = ""

        try:
            _setting, change = services.update_setting(
                key=key, raw_value=value, actor=request.user
            )
        except settings_registry.SettingError as exc:
            return self.refused(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)

        self.audit(
            request,
            AdminAuditLog.Action.SETTING_CHANGED,
            target=settings_registry.REGISTRY[key].label,
            changes={key: change},
        )
        return Response({"settings": settings_registry.describe(), "warning": warning})


class PlatformSettingResetView(ConsoleView):
    def post(self, request, key):
        if key not in settings_registry.REGISTRY:
            return Response(
                {"detail": f"Réglage inconnu : {key}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        before = settings_registry.get(key)
        services.reset_setting(key=key)
        self.audit(
            request,
            AdminAuditLog.Action.SETTING_CHANGED,
            target=settings_registry.REGISTRY[key].label,
            changes={key: [before, settings_registry.get(key)]},
            detail="Retour à la valeur du fichier d'environnement.",
        )
        return Response({"settings": settings_registry.describe()})


# --- Recherche et exports ---------------------------------------------------


class GlobalSearchView(ConsoleView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        return Response(services.global_search(request.query_params.get("q", "")))


class ExportView(ConsoleView):
    permission_classes = [IsPlatformAdmin]

    FILENAMES = {
        "tenants": "clients",
        "prospects": "prospects",
        "subscriptions": "abonnements",
    }

    def get(self, request, kind):
        try:
            headers, rows = services.export_rows(kind)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        stamp = timezone.localdate().isoformat()
        filename = f"{self.FILENAMES[kind]}-{stamp}.csv"
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        # BOM : sans lui, Excel lit l'UTF-8 comme du Latin-1 et affiche des
        # accents cassés — l'export finirait retapé à la main.
        response.write("﻿")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)

        services.record_admin_action(
            actor=request.user,
            action=AdminAuditLog.Action.EXPORT_GENERATED,
            target=filename,
            detail=f"{len(rows)} ligne(s).",
            ip_address=_client_ip(request),
        )
        return response
