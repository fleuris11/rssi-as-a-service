"""Interface publique des demandes d'accès.

Comme les autres apps métier, les fonctions reçoivent un tenant déjà résolu et
lisent par ``all_objects`` avec un filtre ``tenant=`` explicite : elles restent
justes qu'on les appelle depuis une requête client (scopée par le middleware)
ou depuis la console d'administration (qui ne l'est pas).
"""

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import subjects
from .models import AccessRequest

logger = logging.getLogger(__name__)


class AccessRequestError(Exception):
    """Base des refus métier de ce module."""


class UnknownSubjectError(AccessRequestError):
    pass


class AlreadyHeldError(AccessRequestError):
    pass


class DuplicateRequestError(AccessRequestError):
    pass


class AlreadyHandledError(AccessRequestError):
    pass


def create_request(*, tenant, user, subject_type: str, subject_key: str, reason: str = ""):
    """Enregistre une demande. Trois refus, dans cet ordre : sujet inconnu,
    déjà détenu, déjà demandé."""
    subject = subjects.get(subject_type)
    if subject is None:
        raise UnknownSubjectError("Ce type de demande n'existe pas.")

    label = subject.describe(subject_key)
    if label is None:
        raise UnknownSubjectError("L'élément demandé est introuvable.")

    if subject.is_held(tenant, subject_key):
        raise AlreadyHeldError(f"« {label} » vous est déjà accessible.")

    deja_en_cours = DuplicateRequestError(
        f"Une demande pour « {label} » est déjà en cours d'examen."
    )
    if AccessRequest.all_objects.filter(
        tenant=tenant,
        subject_type=subject_type,
        subject_key=subject_key,
        status=AccessRequest.Status.PENDING,
    ).exists():
        raise deja_en_cours

    try:
        # ``atomic`` : sans point de reprise, l'IntegrityError laisserait la
        # transaction de la requête cassée, et le refus poli deviendrait une
        # erreur 500 sur l'appel suivant.
        with transaction.atomic():
            return AccessRequest.all_objects.create(
                tenant=tenant,
                requested_by=user,
                subject_type=subject_type,
                subject_key=subject_key,
                subject_label=label,
                reason=reason,
            )
    except IntegrityError as exc:
        # Deux envois simultanés : la contrainte partielle a tranché.
        raise deja_en_cours from exc


def list_requests(tenant, *, status=None):
    queryset = AccessRequest.all_objects.filter(tenant=tenant).select_related(
        "requested_by", "handled_by"
    )
    if status:
        queryset = queryset.filter(status=status)
    return queryset.order_by("-created_at")


def list_all_requests(*, status=None, subject_type=None):
    """Toutes les demandes, tous clients — la file de la console."""
    queryset = AccessRequest.all_objects.select_related("tenant", "requested_by", "handled_by")
    if status:
        queryset = queryset.filter(status=status)
    if subject_type:
        queryset = queryset.filter(subject_type=subject_type)
    return queryset.order_by("-created_at")


def pending_count() -> int:
    return AccessRequest.all_objects.filter(status=AccessRequest.Status.PENDING).count()


def get_request(*, request_id, tenant=None):
    queryset = AccessRequest.all_objects.select_related("tenant", "requested_by")
    if tenant is not None:
        queryset = queryset.filter(tenant=tenant)
    return queryset.filter(id=request_id).first()


def cancel_request(access_request, *, user=None):
    """Le client retire sa demande. Réservé aux demandes en attente : une
    demande déjà traitée est une trace, et une trace ne se réécrit pas."""
    if not access_request.is_pending:
        raise AlreadyHandledError("Cette demande a déjà été traitée.")
    access_request.status = AccessRequest.Status.CANCELLED
    access_request.handled_at = timezone.now()
    access_request.handled_by = user
    access_request.save(update_fields=["status", "handled_at", "handled_by"])
    return access_request


def handle_request(access_request, *, granted: bool, response: str = "", actor=None):
    """Répond à une demande, et attribue si le sujet sait le faire.

    Renvoie ``(demande, attribution_automatique)``. Le second booléen est faux
    quand le sujet n'a pas de ``grant`` — la console affiche alors ce qui reste
    à faire à la main plutôt que de laisser croire que c'est réglé.
    """
    if not access_request.is_pending:
        raise AlreadyHandledError("Cette demande a déjà été traitée.")

    subject = subjects.get(access_request.subject_type)
    attribue = False
    if granted and subject is not None and subject.grant is not None:
        subject.grant(access_request.tenant, access_request.subject_key, actor)
        attribue = True

    access_request.status = (
        AccessRequest.Status.GRANTED if granted else AccessRequest.Status.DECLINED
    )
    access_request.response = response
    access_request.handled_at = timezone.now()
    access_request.handled_by = actor
    access_request.save(update_fields=["status", "response", "handled_at", "handled_by"])
    return access_request, attribue
