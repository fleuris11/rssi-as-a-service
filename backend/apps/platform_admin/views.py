"""API du back-office plateforme.

Toutes les vues sont gardées par ``IsAdminUser`` (``is_staff``) et **non** par
les permissions de tenant : l'administration n'est pas un espace client mieux
doté, c'est un espace distinct. Aucune de ces vues n'expose le contenu des
fuites d'un client (ADR-014 : un administrateur plateforme n'y accède que s'il
est membre du tenant, par les vues client habituelles) — uniquement des
abonnements, des quotas et des compteurs.
"""

import logging

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing import capacity, entitlements
from apps.billing import services as billing_services
from apps.billing.models import Plan, Subscription
from apps.marketing.models import DemoRequest
from apps.tenants.models import Tenant

from . import services
from .models import AdminAuditLog
from .serializers import (
    AdminAuditLogSerializer,
    DemoRequestAdminSerializer,
    PlanAdminSerializer,
    PlanWriteSerializer,
    SubscriptionActionSerializer,
    TenantSummarySerializer,
)

logger = logging.getLogger(__name__)


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class PlatformAdminView(APIView):
    """Base commune : garde d'accès et journalisation."""

    permission_classes = [permissions.IsAdminUser]

    def audit(self, request, action, *, tenant=None, target="", detail=""):
        return services.record_admin_action(
            actor=request.user,
            action=action,
            tenant=tenant,
            target=target,
            detail=detail,
            ip_address=_client_ip(request),
        )


# --- Ressources rares (le cœur) ---------------------------------------------


class PlatformCapacityView(PlatformAdminView):
    """Ce que l'exploitant doit avoir en permanence sous les yeux : ce qui est
    engagé, ce qui reste, et la projection d'une activation à venir."""

    def get(self, request):
        usages = [usage.as_dict() for usage in capacity.snapshot()]

        # Projection : « si j'active ce plan, il restera X ». Sans elle,
        # l'exploitant doit faire le calcul de tête avant chaque vente.
        projections = []
        for plan in billing_services.list_published_plans():
            projected = capacity.projected_monitored_slots(additional=plan.monitored_assets)
            cap = capacity.monitored_slot_capacity()
            projections.append(
                {
                    "plan_code": plan.code,
                    "plan_name": plan.name,
                    "monitored_assets": plan.monitored_assets,
                    "would_use": projected,
                    "capacity": cap,
                    "would_fit": projected <= cap,
                    "remaining_after": max(0, cap - projected),
                }
            )

        # Répartition par client : qui consomme la ressource rare.
        breakdown = []
        for subscription in Subscription.objects.select_related("tenant", "plan").filter(
            status__in=[Subscription.Status.TRIAL, Subscription.Status.ACTIVE]
        ):
            breakdown.append(
                {
                    "tenant_id": str(subscription.tenant_id),
                    "tenant_name": subscription.tenant.name,
                    "plan_name": subscription.plan.name,
                    "status": subscription.status,
                    "monitored_assets": subscription.monitored_assets_quota,
                    "monthly_scans_used": entitlements.monthly_scans_used(subscription.tenant),
                }
            )
        breakdown.sort(key=lambda row: -row["monitored_assets"])

        return Response({"resources": usages, "projections": projections, "by_tenant": breakdown})


# --- Clients ----------------------------------------------------------------


class AdminTenantListView(PlatformAdminView):
    def get(self, request):
        tenants = services.list_tenants_with_subscription()
        return Response(TenantSummarySerializer(tenants, many=True).data)


class AdminTenantDetailView(PlatformAdminView):
    def get(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        return Response(services.tenant_detail(tenant))

    def patch(self, request, tenant_id):
        """Notes internes uniquement — le reste de la fiche se pilote par les
        actions d'abonnement, qui sont tracées individuellement."""
        tenant = get_object_or_404(Tenant, id=tenant_id)
        subscription = entitlements.get_subscription(tenant)
        if subscription is None:
            return Response(
                {"detail": "Cette entreprise n'a pas d'abonnement."},
                status=status.HTTP_404_NOT_FOUND,
            )
        notes = request.data.get("internal_notes")
        if notes is not None:
            subscription.internal_notes = notes
            subscription.save(update_fields=["internal_notes", "updated_at"])
        return Response(services.tenant_detail(tenant))


class AdminSubscriptionActionView(PlatformAdminView):
    """Activation, suspension, résiliation, changement d'offre.

    Chaque action passe par ``apps.billing.services``, qui applique la garde de
    capacité **avant** d'écrire. Une ``PlatformCapacityError`` remonte en 409 :
    la demande est légitime mais l'état de la plateforme la rend impossible,
    ce qui n'est ni une erreur du client (4xx classique) ni une panne (5xx).
    """

    ACTION_TO_AUDIT = {
        "activate": AdminAuditLog.Action.SUBSCRIPTION_ACTIVATED,
        "suspend": AdminAuditLog.Action.SUBSCRIPTION_SUSPENDED,
        "cancel": AdminAuditLog.Action.SUBSCRIPTION_CANCELLED,
        "change_plan": AdminAuditLog.Action.PLAN_CHANGED,
    }

    def post(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        subscription = entitlements.get_subscription(tenant)
        if subscription is None:
            return Response(
                {"detail": "Cette entreprise n'a pas d'abonnement."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")

        try:
            if action == "activate":
                billing_services.activate(
                    subscription=subscription,
                    period=serializer.validated_data.get("period") or None,
                    actor=request.user,
                    reason=reason,
                )
                detail = "Abonnement activé."
            elif action == "suspend":
                billing_services.suspend(
                    subscription=subscription, actor=request.user, reason=reason
                )
                detail = "Abonnement suspendu."
            elif action == "cancel":
                billing_services.cancel(
                    subscription=subscription, actor=request.user, reason=reason
                )
                detail = "Abonnement résilié."
            else:  # change_plan
                plan = get_object_or_404(Plan, code=serializer.validated_data["plan_code"])
                billing_services.change_plan(
                    subscription=subscription, plan=plan, actor=request.user, reason=reason
                )
                detail = f"Offre changée pour {plan.name}."
        except capacity.PlatformCapacityError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except billing_services.BillingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        self.audit(
            request,
            self.ACTION_TO_AUDIT[action],
            tenant=tenant,
            target=tenant.name,
            detail=f"{detail} {reason}".strip(),
        )
        return Response(services.tenant_detail(tenant))


# --- Offres -----------------------------------------------------------------


class AdminPlanListView(PlatformAdminView):
    def get(self, request):
        return Response(PlanAdminSerializer(Plan.objects.all(), many=True).data)

    def post(self, request):
        serializer = PlanWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        self.audit(request, AdminAuditLog.Action.PLAN_CREATED, target=plan.name, detail=plan.code)
        return Response(PlanAdminSerializer(plan).data, status=status.HTTP_201_CREATED)


class AdminPlanDetailView(PlatformAdminView):
    def patch(self, request, plan_code):
        plan = get_object_or_404(Plan, code=plan_code)
        previous_status = plan.status
        serializer = PlanWriteSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()

        if plan.status != previous_status:
            action = (
                AdminAuditLog.Action.PLAN_PUBLISHED
                if plan.status == Plan.Status.PUBLISHED
                else AdminAuditLog.Action.PLAN_RETIRED
            )
            self.audit(
                request, action, target=plan.name, detail=f"{previous_status} -> {plan.status}"
            )
        else:
            self.audit(request, AdminAuditLog.Action.PLAN_UPDATED, target=plan.name)
        return Response(PlanAdminSerializer(plan).data)


# --- Demandes de démonstration ----------------------------------------------


class AdminDemoRequestListView(PlatformAdminView):
    """Demandes reçues depuis le site public, les plus récentes d'abord.

    Les demandes closes restent listées : une demande convertie en client ne
    disparaît pas, on doit pouvoir retrouver d'où vient un compte.
    """

    def get(self, request):
        requests = DemoRequest.objects.all()[:100]
        return Response(
            {
                "requests": DemoRequestAdminSerializer(requests, many=True).data,
                "open_count": DemoRequest.objects.exclude(
                    status=DemoRequest.Status.CLOSED
                ).count(),
            }
        )

    def patch(self, request, demo_request_id):
        """Fait avancer une demande dans son suivi commercial (contactée,
        planifiée, close) sans créer de client."""
        demo_request = get_object_or_404(DemoRequest, id=demo_request_id)
        new_status = request.data.get("status")
        if new_status not in DemoRequest.Status.values:
            return Response(
                {"detail": "Statut inconnu."}, status=status.HTTP_400_BAD_REQUEST
            )
        demo_request.status = new_status
        demo_request.save(update_fields=["status"])
        self.audit(
            request,
            AdminAuditLog.Action.DEMO_REQUEST_UPDATED,
            target=demo_request.company,
            detail=f"Statut -> {new_status}",
        )
        return Response(DemoRequestAdminSerializer(demo_request).data)


class AdminDemoRequestConvertView(PlatformAdminView):
    """Convertit une demande en client : crée l'entreprise, son utilisateur
    administrateur et son essai. La garde de capacité s'applique — une
    conversion qui ferait déborder la plateforme est refusée avant toute
    écriture."""

    def post(self, request, demo_request_id):
        demo_request = get_object_or_404(DemoRequest, id=demo_request_id)
        if Tenant.objects.filter(name=demo_request.company).exists():
            return Response(
                {"detail": "Une entreprise portant ce nom existe déjà."},
                status=status.HTTP_409_CONFLICT,
            )

        from django.contrib.auth import get_user_model

        from apps.tenants.services import create_tenant_with_owner

        User = get_user_model()
        user, _created = User.objects.get_or_create(
            email=demo_request.email,
            defaults={"first_name": demo_request.full_name.split(" ")[0]},
        )
        try:
            tenant = create_tenant_with_owner(name=demo_request.company, owner=user)
        except capacity.PlatformCapacityError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        demo_request.status = DemoRequest.Status.CLOSED
        demo_request.save(update_fields=["status"])

        self.audit(
            request,
            AdminAuditLog.Action.TENANT_CREATED,
            tenant=tenant,
            target=tenant.name,
            detail=f"Converti depuis la demande de démonstration {demo_request.id}.",
        )
        return Response(services.tenant_detail(tenant), status=status.HTTP_201_CREATED)


# --- Santé, configuration, audit --------------------------------------------


class PlatformHealthView(PlatformAdminView):
    def get(self, request):
        return Response(services.platform_health())


class PlatformConfigurationView(PlatformAdminView):
    def get(self, request):
        return Response(services.technical_configuration())


class AdminAuditView(PlatformAdminView):
    """Journal consolidé : actions d'administration **et** révélations de
    secrets. Les deux répondent à la même question — qui a fait quoi — et les
    séparer obligerait à croiser deux écrans à la main."""

    def get(self, request):
        from apps.threat_intelligence.models import SecretRevealAudit

        admin_entries = [
            {
                "kind": "admin",
                "at": entry.created_at,
                "actor": entry.actor.email if entry.actor else "",
                "action": entry.get_action_display(),
                "tenant": entry.tenant.name if entry.tenant else "",
                "detail": entry.detail or entry.target,
            }
            for entry in services.list_admin_audit(limit=100)
        ]
        reveal_entries = [
            {
                "kind": "reveal",
                "at": entry.created_at,
                "actor": entry.user.email if entry.user else "",
                "action": "Révélation accordée" if entry.success else "Révélation refusée",
                "tenant": entry.tenant.name if entry.tenant else "",
                "detail": entry.denial_reason or "",
            }
            for entry in SecretRevealAudit.all_objects.select_related("tenant", "user").order_by(
                "-created_at"
            )[:100]
        ]
        entries = sorted(admin_entries + reveal_entries, key=lambda e: e["at"], reverse=True)[:150]
        return Response({"entries": entries})


class AdminAuditRawView(PlatformAdminView):
    def get(self, request):
        return Response(
            AdminAuditLogSerializer(services.list_admin_audit(limit=200), many=True).data
        )
