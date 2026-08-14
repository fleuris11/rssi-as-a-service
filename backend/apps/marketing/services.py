"""Interface publique de l'app marketing — logique de la demande de
démonstration (CLAUDE.md : la vue orchestre, le service décide).
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail

from .models import DemoRequest

logger = logging.getLogger(__name__)


def create_demo_request(*, data: dict, ip_address: str = "", user_agent: str = "") -> DemoRequest:
    return DemoRequest.objects.create(
        full_name=data["full_name"],
        company=data["company"],
        role=data.get("role", ""),
        email=data["email"],
        company_size=data.get("company_size", ""),
        preferred_slot=data.get("preferred_slot", ""),
        message=data.get("message", ""),
        ip_address=ip_address or None,
        user_agent=user_agent[:255],
    )


def send_demo_request_emails(demo_request: DemoRequest) -> None:
    """Accusé de réception au prospect + notification à l'exploitant.

    Best-effort et **jamais bloquant** : un incident SMTP ne doit pas faire
    échouer une demande déjà enregistrée en base. Le prospect verrait une
    erreur alors que sa demande est bien arrivée, et il la resoumettrait —
    même logique que la météo quotidienne (ADR-011) : la donnée est acquise,
    l'email est un confort.
    """
    try:
        send_mail(
            subject="Votre demande de démonstration — RSSI as a Service",
            message=(
                f"Bonjour {demo_request.full_name},\n\n"
                "Nous avons bien reçu votre demande de démonstration et nous vous "
                "recontactons sous un jour ouvré pour convenir d'un créneau.\n\n"
                "La démonstration dure une vingtaine de minutes et se fait en partage "
                "d'écran. Elle ne nécessite aucune installation de votre côté.\n\n"
                "À très bientôt,\n"
                "L'équipe RSSI as a Service"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[demo_request.email],
            fail_silently=False,
        )
    except Exception:  # noqa: BLE001 - la demande est enregistrée, l'email est un confort
        logger.warning(
            "Accusé de réception non envoyé pour la demande de démonstration %s",
            demo_request.id,
            exc_info=True,
        )

    operator = getattr(settings, "DEMO_REQUEST_NOTIFICATION_EMAIL", "") or ""
    if not operator:
        return
    try:
        send_mail(
            subject=f"Nouvelle demande de démonstration — {demo_request.company}",
            message=(
                f"Société : {demo_request.company}\n"
                f"Contact : {demo_request.full_name}"
                f"{f' ({demo_request.role})' if demo_request.role else ''}\n"
                f"Email : {demo_request.email}\n"
                f"Taille : {demo_request.get_company_size_display() or 'non renseignée'}\n"
                f"Créneau : {demo_request.get_preferred_slot_display() or 'non renseigné'}\n\n"
                f"Message :\n{demo_request.message or '(aucun)'}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[operator],
            fail_silently=False,
        )
    except Exception:  # noqa: BLE001 - même raison
        logger.warning(
            "Notification exploitant non envoyée pour la demande %s",
            demo_request.id,
            exc_info=True,
        )


def list_demo_requests(*, status: str | None = None):
    qs = DemoRequest.objects.all()
    if status:
        qs = qs.filter(status=status)
    return qs


# --- Chaîne commerciale (phase 11) ------------------------------------------
#
# Un prospect n'arrive pas seulement par le formulaire public : une rencontre,
# une recommandation, un appel entrant en produisent tout autant. Sans saisie
# manuelle, ces affaires-là vivent dans un carnet à côté de l'outil — et la
# vue de suivi ne veut plus rien dire.


class ProspectError(Exception):
    """Violation d'une règle métier de suivi commercial."""


EDITABLE_PROSPECT_FIELDS = (
    "full_name",
    "company",
    "role",
    "email",
    "phone",
    "company_size",
    "preferred_slot",
    "message",
    "status",
    "lost_reason",
    "next_follow_up_on",
)


def snapshot_prospect(prospect: DemoRequest) -> dict:
    return {field: getattr(prospect, field) for field in EDITABLE_PROSPECT_FIELDS}


def create_prospect(*, actor=None, **fields) -> DemoRequest:
    company = (fields.get("company") or "").strip()
    full_name = (fields.get("full_name") or "").strip()
    email = (fields.get("email") or "").strip().lower()
    if not company:
        raise ProspectError("Le nom de l'entreprise est obligatoire.")
    if not full_name:
        raise ProspectError("Le nom du contact est obligatoire.")
    if not email:
        raise ProspectError("L'adresse email est obligatoire.")

    payload = {k: v for k, v in fields.items() if k in EDITABLE_PROSPECT_FIELDS}
    payload.update({"company": company, "full_name": full_name, "email": email})
    return DemoRequest.objects.create(
        source=DemoRequest.Source.MANUAL, created_by=actor, **payload
    )


def update_prospect(*, prospect: DemoRequest, **fields) -> tuple[DemoRequest, dict]:
    from apps.platform_admin.services import diff_fields

    before = snapshot_prospect(prospect)

    status = fields.get("status")
    if status is not None and status not in DemoRequest.Status.values:
        raise ProspectError("Statut inconnu.")
    if status == DemoRequest.Status.LOST and not (
        fields.get("lost_reason") or prospect.lost_reason
    ):
        # Une affaire perdue sans motif ne s'analyse pas six mois plus tard —
        # or c'est exactement l'usage qu'on fera de cette liste.
        raise ProspectError("Indiquez le motif de la perte.")

    for field, value in fields.items():
        if field in EDITABLE_PROSPECT_FIELDS:
            setattr(prospect, field, value)
    prospect.save()
    return prospect, diff_fields(before, snapshot_prospect(prospect))


def add_prospect_note(*, prospect: DemoRequest, body: str, author=None):
    from .models import ProspectNote

    body = (body or "").strip()
    if not body:
        raise ProspectError("La note est vide.")
    return ProspectNote.objects.create(demo_request=prospect, body=body, author=author)


def mark_converted(*, prospect: DemoRequest, tenant) -> DemoRequest:
    """Relie le prospect au client créé. Le lien est conservé : on doit
    pouvoir retrouver d'où vient un compte, et ne pas reproposer la
    conversion d'un prospect déjà transformé."""
    prospect.converted_tenant = tenant
    prospect.status = DemoRequest.Status.WON
    prospect.save(update_fields=["converted_tenant", "status", "updated_at"])
    return prospect


def follow_up_board(*, today=None, stale_after_days: int = 14) -> dict:
    """Ce qui demande une action aujourd'hui.

    Deux questions, et deux seulement : qui dois-je rappeler aujourd'hui, et
    qu'ai-je laissé dormir ? Une liste de tous les prospects ne répond ni à
    l'une ni à l'autre.
    """
    from django.utils import timezone

    today = today or timezone.localdate()
    stale_before = today - timedelta(days=stale_after_days)
    open_prospects = DemoRequest.objects.exclude(status__in=DemoRequest.TERMINAL_STATUSES)

    return {
        "due_today": list(
            open_prospects.filter(next_follow_up_on__lte=today).order_by("next_follow_up_on")
        ),
        "stale": list(
            open_prospects.filter(
                next_follow_up_on__isnull=True, updated_at__date__lte=stale_before
            ).order_by("updated_at")
        ),
        "stale_after_days": stale_after_days,
    }
