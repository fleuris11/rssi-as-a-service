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
        """Le suivi d'une demande, du dépôt à sa conclusion (V2-6).

        V2-4 n'avait que trois états : en attente, accordée, refusée. C'était
        suffisant pour un référentiel qu'on attribue d'un clic ; ça ne l'est
        plus pour une fonctionnalité, dont l'ouverture passe par une
        conversation commerciale. Un client qui a demandé il y a dix jours et
        lit toujours « en attente » ne sait pas si quelqu'un l'a vu.

        Les trois premiers états sont OUVERTS (``OPEN_STATUSES``) : la
        demande vit toujours. Une nouvelle demande sur le même sujet est
        refusée tant qu'elle l'est — sans quoi relancer remplirait la console
        de doublons.

        La valeur ``pending`` est conservée telle quelle malgré son libellé
        « Nouvelle » : la renommer aurait demandé une migration de données
        pour un gain d'esthétique, et aurait cassé la contrainte partielle qui
        s'y réfère.
        """

        PENDING = "pending", "Nouvelle"
        CONTACTED = "contacted", "Client contacté"
        PROPOSAL = "proposal", "Proposition envoyée"
        GRANTED = "granted", "Accordée"
        DECLINED = "declined", "Refusée"
        CANCELLED = "cancelled", "Annulée par le client"

    #: Une demande en cours de traitement. Sert à la fois à la contrainte
    #: d'unicité et à ce que le client voit comme « en cours ».
    OPEN_STATUSES = ("pending", "contacted", "proposal")

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
            # Une seule demande OUVERTE par sujet et par client : renvoyer
            # trois fois le formulaire ne doit pas remplir la console de trois
            # lignes identiques. Les demandes conclues, elles, s'accumulent —
            # c'est l'historique.
            #
            # V2-6 : la condition couvre les trois états ouverts, et non le
            # seul « pending ». Sans cela, une demande passée en « client
            # contacté » aurait laissé le client en redéposer une deuxième,
            # et le commercial aurait travaillé deux lignes pour une seule
            # conversation.
            models.UniqueConstraint(
                fields=["tenant", "subject_type", "subject_key"],
                condition=models.Q(status__in=["pending", "contacted", "proposal"]),
                name="unique_open_access_request",
            ),
        ]
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"{self.tenant_id} — {self.subject_type}:{self.subject_key} ({self.status})"

    @property
    def is_open(self) -> bool:
        """La demande vit toujours : elle attend, ou elle est en cours de
        traitement commercial."""
        return self.status in self.OPEN_STATUSES

    @property
    def is_pending(self) -> bool:
        """Conservé : ``is_open`` a remplacé cet usage partout, mais le nom
        reste lisible là où l'on veut vraiment dire « pas encore regardée »."""
        return self.status == self.Status.PENDING
