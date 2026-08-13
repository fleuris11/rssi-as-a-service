"""Interface publique de l'app marketing — logique de la demande de
démonstration (CLAUDE.md : la vue orchestre, le service décide).
"""

import logging

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
