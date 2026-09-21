"""Les tâches planifiées du module Formation (F3).

Trois rythmes, trois raisons :

- les **relances** partent une fois par jour. Plus souvent n'aurait pas de
  sens — une relance se compte en jours, pas en heures ;
- les **propositions de preuve** sont calculées une fois par jour aussi, et
  elles ne repassent jamais sur ce que le client a écarté ;
- la **purge** tourne une fois par mois : c'est une obligation de durée de
  conservation, pas une urgence.

Chaque tâche est **idempotente** : la relancer deux fois le même jour
n'envoie rien de plus. C'est la contrainte d'unicité en base qui le garantit,
pas la bonne tenue de la tâche.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.notifications import inbox
from apps.notifications.models import Notification
from apps.tenants.models import Tenant

from . import campagnes, preuves, rapports, services

logger = logging.getLogger(__name__)

#: En deçà, on prévient l'administrateur : une campagne que personne ne suit
#: est un problème d'organisation, pas de produit, et il vaut mieux le lui
#: dire pendant qu'il peut encore agir.
SEUIL_PARTICIPATION_FAIBLE = 50


def _clients_actifs():
    return Tenant.objects.filter(is_active=True, archived_at__isnull=True)


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def envoyer_les_relances(self):
    """Les relances du jour, tous clients confondus."""
    try:
        envoyees = campagnes.envoyer_les_relances()
    except Exception as exc:  # pragma: no cover - dépend du serveur de mail
        logger.warning("Relances de formation : %s", exc)
        raise self.retry(exc=exc) from exc
    if envoyees:
        logger.info("Relances de formation envoyées : %s", envoyees)
    return envoyees


@shared_task
def proposer_les_preuves():
    """Calcule les propositions de renseignement du diagnostic.

    **Ne coche rien.** Elle crée une proposition et prévient l'administrateur ;
    la décision reste humaine (ADR-041).
    """
    total = 0
    for client in _clients_actifs():
        with services.contexte_du_client(client):
            nouvelles = preuves.proposer(client)
            total += len(nouvelles)
            for proposition in nouvelles:
                inbox.notify_tenant_admins(
                    client,
                    kind=Notification.Kind.TRAINING_MEASURE_SUGGESTED,
                    title="Une formation peut renseigner votre diagnostic",
                    body=(
                        f"La campagne « {proposition.course.title} » atteint "
                        f"{proposition.participation_rate} % de participation et "
                        f"{proposition.success_rate} % de réussite. Elle peut servir de preuve "
                        f"pour la mesure « {proposition.measure_title} ». À confirmer."
                    ),
                    link="/formation",
                    dedupe_key=f"preuve:{proposition.id}",
                )
    return total


@shared_task
def surveiller_les_campagnes():
    """Prévient l'administrateur de ce qui mérite son attention.

    Trois événements, et pas un de plus : une campagne terminée, une échéance
    dépassée, une participation faible. Le centre de notifications existe
    depuis le lot C ; on s'y branche au lieu d'inventer un second canal.
    """
    aujourdhui = timezone.localdate()
    envoyees = 0

    for client in _clients_actifs():
        with services.contexte_du_client(client):
            for campagne in rapports.campagnes(client):
                cle = f"{campagne['course_id']}:{campagne['due_date']}"

                if campagne["success_rate"] == 100:
                    envoyees += inbox.notify_tenant_admins(
                        client,
                        kind=Notification.Kind.TRAINING_CAMPAIGN_DONE,
                        title=f"Formation terminée par tous : {campagne['course_title']}",
                        body=(
                            f"Les {campagne['learners_total']} salariés inscrits ont terminé "
                            f"« {campagne['course_title']} »."
                        ),
                        link="/formation",
                        dedupe_key=f"campagne-finie:{cle}",
                    )
                    continue

                if campagne["due_date"] < aujourdhui:
                    envoyees += inbox.notify_tenant_admins(
                        client,
                        kind=Notification.Kind.TRAINING_DUE_PASSED,
                        title=f"Échéance dépassée : {campagne['course_title']}",
                        body=(
                            f"L'échéance du {campagne['due_date']:%d/%m/%Y} est passée et "
                            f"{campagne['success_rate']} % des salariés ont terminé."
                        ),
                        link="/formation",
                        dedupe_key=f"echeance:{cle}",
                    )
                elif campagne["participation_rate"] < SEUIL_PARTICIPATION_FAIBLE:
                    envoyees += inbox.notify_tenant_admins(
                        client,
                        kind=Notification.Kind.TRAINING_LOW_PARTICIPATION,
                        title=f"Participation faible : {campagne['course_title']}",
                        body=(
                            f"{campagne['participation_rate']} % des salariés ont commencé, "
                            f"pour une échéance au {campagne['due_date']:%d/%m/%Y}."
                        ),
                        link="/formation",
                        dedupe_key=f"participation:{cle}",
                    )
    return envoyees


@shared_task
def purger_les_resultats():
    """Efface les résultats détaillés passé la durée de conservation.

    Ce qui est effacé : les **tentatives** et les réponses question par
    question, qui sont la partie nominative et détaillée du traitement.

    Ce qui est conservé : les **attestations**. Elles sont la preuve que
    l'entreprise a formé ses salariés — la détruire lui retirerait le
    bénéfice du traitement qu'elle a déclaré, et c'est le document qu'un
    auditeur demandera. Leur sort est traité séparément (ADR-041).
    """
    from .models import Attempt

    mois = getattr(settings, "TRAINING_RESULTS_RETENTION_MONTHS", 24)
    limite = timezone.now() - timezone.timedelta(days=int(mois) * 30)
    anciennes = Attempt.all_objects.filter(submitted_at__lt=limite)
    combien = anciennes.count()
    # Les réponses partent en cascade avec la tentative.
    anciennes.delete()
    if combien:
        logger.info("Résultats de formation purgés : %s tentative(s)", combien)
    return combien
