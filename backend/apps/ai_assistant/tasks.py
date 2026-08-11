"""Celery tasks for the ai queue. Orchestration only — pipeline logic lives
in services.py, independently unit-testable without Celery (CLAUDE.md:
"les tasks Celery... orchestrent, les services.py contiennent la logique").

Idempotency: each task guards on the job's current status, so a redelivery
of an already-finished (done/failed) job is a no-op — an AI call is neither
free nor safely repeatable (a duplicate document or reply would be a real
user-visible bug), unlike apps.monitoring's checks. A ``running`` job is
NOT treated as already-finished: it's exactly the status a retry attempt
sees (the first attempt marks it running before the failure that triggers
the retry) — rejecting it there would strand the job in ``running``
forever instead of ever reaching ``failed``.
"""

import logging

from celery import shared_task

from . import services
from .models import AIJob

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_document_task(self, job_id: int):
    job = AIJob.all_objects.filter(id=job_id).select_related("tenant").first()
    if job is None or job.status in (AIJob.Status.DONE, AIJob.Status.FAILED):
        return None
    services.mark_job_running(job)

    document = services.get_document(tenant=job.tenant, document_id=job.result_ref["document_id"])
    if document is None:
        services.mark_job_failed(job, "Document introuvable.")
        return None

    try:
        services.generate_charter_document(document=document)
    except Exception as exc:  # noqa: BLE001 - retry on anything unexpected
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        logger.warning("Échec définitif de la génération du document %s : %s", document.id, exc)
        document.status = document.Status.FAILED
        document.save(update_fields=["status", "updated_at"])
        services.mark_job_failed(job, str(exc))
        return None

    services.mark_job_done(job)
    return job.id


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_exposure_synthesis_task(self, job_id: int):
    """Phase 8B. Le résultat est mis en cache côté threat_intelligence
    (ExposureSynthesis) plutôt que pointé par ``result_ref`` : la page
    d'exposition l'affiche sans connaître le job, et un job perdu n'empêche
    jamais de lire la dernière synthèse valide."""
    from apps.threat_intelligence import services as threat_intelligence_services

    job = AIJob.all_objects.filter(id=job_id).select_related("tenant").first()
    if job is None or job.status in (AIJob.Status.DONE, AIJob.Status.FAILED):
        return None
    services.mark_job_running(job)

    try:
        threat_intelligence_services.refresh_exposure_synthesis(job.tenant)
    except Exception as exc:  # noqa: BLE001 - retry on anything unexpected
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        logger.warning("Échec définitif de la synthèse d'exposition (job %s) : %s", job.id, exc)
        services.mark_job_failed(job, str(exc))
        return None

    services.mark_job_done(job)
    return job.id


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_assistant_reply_task(self, job_id: int):
    job = AIJob.all_objects.filter(id=job_id).select_related("tenant").first()
    if job is None or job.status in (AIJob.Status.DONE, AIJob.Status.FAILED):
        return None
    services.mark_job_running(job)

    conversation = services.get_conversation(
        tenant=job.tenant, conversation_id=job.result_ref["conversation_id"]
    )
    if conversation is None:
        services.mark_job_failed(job, "Conversation introuvable.")
        return None

    try:
        reply = services.generate_assistant_reply(conversation=conversation)
    except Exception as exc:  # noqa: BLE001 - retry on anything unexpected
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        logger.warning("Échec définitif de la réponse de l'assistant (job %s) : %s", job.id, exc)
        services.mark_job_failed(job, str(exc))
        return None

    services.mark_job_done(job, {"message_id": reply.id})
    return job.id
