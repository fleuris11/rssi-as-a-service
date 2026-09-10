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
        status__in=AccessRequest.OPEN_STATUSES,
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


def open_count() -> int:
    """Ce qui reste à traiter dans la console : nouvelles, contactées et en
    proposition. Compter les seules « nouvelles » sous-estimerait la file —
    une demande contactée mais sans suite demande toujours du travail."""
    return AccessRequest.all_objects.filter(status__in=AccessRequest.OPEN_STATUSES).count()


def pending_count() -> int:
    """Les demandes que personne n'a encore regardées."""
    return AccessRequest.all_objects.filter(status=AccessRequest.Status.PENDING).count()


def get_request(*, request_id, tenant=None):
    queryset = AccessRequest.all_objects.select_related("tenant", "requested_by")
    if tenant is not None:
        queryset = queryset.filter(tenant=tenant)
    return queryset.filter(id=request_id).first()


def cancel_request(access_request, *, user=None):
    """Le client retire sa demande. Réservé aux demandes ouvertes : une
    demande conclue est une trace, et une trace ne se réécrit pas."""
    if not access_request.is_open:
        raise AlreadyHandledError("Cette demande a déjà été traitée.")
    access_request.status = AccessRequest.Status.CANCELLED
    access_request.handled_at = timezone.now()
    access_request.handled_by = user
    access_request.save(update_fields=["status", "handled_at", "handled_by"])
    return access_request


#: Les étapes vers lesquelles la CONSOLE peut faire avancer une demande.
#: Exclut « nouvelle » (on ne rembobine pas) et « annulée » (elle appartient
#: au client). Le sérialiseur propose la même liste ; la règle est ici, pour
#: qu'un appel direct rencontre le même refus.
ADVANCEABLE_STATUSES = (
    AccessRequest.Status.CONTACTED,
    AccessRequest.Status.PROPOSAL,
    AccessRequest.Status.GRANTED,
    AccessRequest.Status.DECLINED,
)

#: Les étapes conclusives : la demande ne bouge plus après.
TERMINAL_STATUSES = (
    AccessRequest.Status.GRANTED,
    AccessRequest.Status.DECLINED,
    AccessRequest.Status.CANCELLED,
)


def advance_request(access_request, *, status: str, response: str = "", actor=None):
    """Fait avancer une demande dans son suivi (V2-6).

    Renvoie ``(demande, attribution_automatique)``. Le second booléen n'est
    vrai que si le passage à « accordée » a réellement attribué quelque chose
    — la console affiche sinon ce qui reste à faire à la main plutôt que de
    laisser croire que c'est réglé.

    Une étape intermédiaire (contacté, proposition) n'attribue rien et ne
    clôt rien : elle dit au client que quelqu'un s'occupe de lui, ce qui est
    précisément ce qui manquait. ``handled_at`` n'est posé qu'à la
    conclusion — c'est la date de la DÉCISION, pas celle du dernier clic.
    """
    if not access_request.is_open:
        raise AlreadyHandledError("Cette demande a déjà été traitée.")
    if status not in ADVANCEABLE_STATUSES:
        # Deux exclusions, deux raisons. « Nouvelle » : la console ne
        # rembobine pas une demande qu'elle a déjà travaillée — le client
        # verrait son suivi reculer. « Annulée » : elle appartient au client,
        # l'exploitant ne retire pas une demande au nom de celui qui l'a
        # déposée.
        raise AccessRequestError("Étape de suivi inconnue.")

    subject = subjects.get(access_request.subject_type)
    attribue = False
    if status == AccessRequest.Status.GRANTED and subject is not None and subject.grant is not None:
        subject.grant(access_request.tenant, access_request.subject_key, actor)
        attribue = True

    access_request.status = status
    if response:
        access_request.response = response
    champs = ["status", "response"]
    if status in TERMINAL_STATUSES:
        access_request.handled_at = timezone.now()
        access_request.handled_by = actor
        champs += ["handled_at", "handled_by"]
    access_request.save(update_fields=champs)
    return access_request, attribue


def handle_request(access_request, *, granted: bool, response: str = "", actor=None):
    """Conclut une demande. Conservé tel quel : c'est le geste le plus
    fréquent, et le réécrire partout en ``advance_request(status=...)`` aurait
    rendu les appelants moins lisibles pour rien."""
    return advance_request(
        access_request,
        status=AccessRequest.Status.GRANTED if granted else AccessRequest.Status.DECLINED,
        response=response,
        actor=actor,
    )
