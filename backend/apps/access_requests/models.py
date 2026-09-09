from django.conf import settings
from django.db import models

from apps.tenants.models import TenantScopedModel


class AccessRequest(TenantScopedModel):
    """Une demande d'un client à l'exploitant : « je voudrais ce référentiel »,
    et demain « je voudrais cette fonctionnalité ».

    ``subject_type`` / ``subject_key`` désignent l'objet demandé sans que ce
    modèle sache ce qu'il est : le registre (``subjects.py``) fait la
    traduction. C'est ce qui rend le mécanisme réutilisable — la table n'a pas
    de colonne ``referential``.

    ``subject_label`` est **figé à la demande**. Un référentiel renommé, ou
    retiré du catalogue, ne doit pas rendre illisible une demande vieille de
    trois mois : le journal dirait « demande de  » sans dire de quoi.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        GRANTED = "granted", "Accordée"
        DECLINED = "declined", "Refusée"
        CANCELLED = "cancelled", "Annulée par le client"

    subject_type = models.CharField(max_length=40)
    subject_key = models.CharField(max_length=100)
    subject_label = models.CharField(max_length=200)
    # Le « pourquoi » demandé par la fiche V2-4. Facultatif : exiger une
    # justification pour demander ce que le produit sait déjà faire
    # découragerait la demande, qui est ce qu'on veut voir arriver.
    reason = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    # La réponse écrite au client. Un refus sans phrase est un mur ; celui-ci
    # remonte dans son espace, à côté de sa demande.
    response = models.TextField(blank=True)
    handled_at = models.DateTimeField(null=True, blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            # Une seule demande EN ATTENTE par sujet et par client : renvoyer
            # trois fois le formulaire ne doit pas remplir la console de trois
            # lignes identiques. Les demandes traitées, elles, s'accumulent —
            # c'est l'historique.
            models.UniqueConstraint(
                fields=["tenant", "subject_type", "subject_key"],
                condition=models.Q(status="pending"),
                name="unique_pending_access_request",
            ),
        ]
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"{self.tenant_id} — {self.subject_type}:{self.subject_key} ({self.status})"

    @property
    def is_pending(self) -> bool:
        return self.status == self.Status.PENDING
