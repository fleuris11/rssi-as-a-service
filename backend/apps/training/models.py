"""Le parcours de formation d'un salarié (F1, ADR-039).

Deux moitiés, et la ligne qui les sépare est la même que celle des
référentiels (ADR-029) : **le catalogue est global, l'usage est cloisonné**.
``Course`` / ``CourseVersion`` / ``Screen`` / ``Question`` / ``Choice``
n'appartiennent à personne — un cours écrit une fois sert tous les clients.
Tout le reste hérite de ``TenantScopedModel``.

Une seule source de vérité pour la progression
----------------------------------------------
La question se pose dès qu'on écrit trois tables qui parlent d'avancement, et
elle se règle ici une fois pour toutes :

- **où en est-il dans le cours** → les lignes de ``ScreenProgress``, et rien
  d'autre. ``Enrollment`` ne porte ni curseur, ni compteur d'écrans vus : un
  champ « dernier écran » se désynchroniserait du jour où une reprise, une
  révision ciblée ou une nouvelle version le mettrait à jour ailleurs.
- **où en est-il du quiz** → les lignes d'``Attempt``, et rien d'autre. Le
  nombre d'essais consommés se compte, il ne se stocke pas.
- **a-t-il réussi** → l'existence d'un ``Certificate``. Pas de ``completed_at``
  sur l'inscription : ce serait la même information écrite deux fois, et c'est
  toujours la copie qui finit par mentir.

``Enrollment`` ne porte donc que des faits qui ne sont déductibles de rien
d'autre : l'échéance, le jeton, la première ouverture, la révocation, le
réarmement.
"""

import secrets
import uuid
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenants.models import Tenant, TenantScopedModel

from . import blocks as blocs_de_contenu

#: Combien de temps un lien survit à l'échéance de la campagne.
#:
#: Une durée fixe (« 30 jours ») ne pouvait pas convenir : sur une campagne de
#: deux semaines elle laisse seize jours de lien vivant pour rien, et sur une
#: campagne de deux mois elle oblige à renouveler au milieu. La validité suit
#: donc l'usage. La marge existe pour le salarié qui s'y prend le dernier jour
#: et revient le lendemain — lui refuser l'accès à ce moment-là ne protège
#: rien et lui fait abandonner.
MARGE_APRES_ECHEANCE_JOURS = 7

#: Valeurs par défaut d'un quiz, reprises par chaque nouvelle version de cours.
#:
#: 70 % et non 80 % : sur cinq questions, un seuil de 80 % fait échouer à la
#: première erreur. C'est punitif, et surtout contre-productif — cela pousse à
#: cliquer au hasard pour en finir plutôt qu'à relire.
SEUIL_REUSSITE_DEFAUT = 70
#: Trois essais et non un (punitif) ni illimité (à la fin, on tombe juste).
ESSAIS_DEFAUT = 3
#: En deçà, un seuil en pourcentage ne veut plus dire grand-chose : sur trois
#: questions, 70 % est arithmétiquement un quiz de deux questions. Le service
#: d'écriture avertit, il n'interdit pas — un micro-cours peut le vouloir.
QUESTIONS_MINIMUM_POUR_UN_SEUIL = 5


class Course(models.Model):
    """L'identité d'un cours, stable dans le temps.

    Ne porte **aucun contenu** : le contenu vit dans ``CourseVersion``. La
    séparation existe dès F1, alors que le studio n'arrive qu'en F2, parce que
    le versionnage est une propriété du modèle et non une fonctionnalité de
    l'outil d'édition. L'introduire après coup aurait demandé de rattacher
    après coup des inscriptions et des progressions déjà en base — la migration
    qu'on ne veut pas écrire en production.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # F2 — à qui appartient ce cours.
    #
    # Nul = cours de LA BIBLIOTHÈQUE, écrit par l'exploitant et proposé à ses
    # clients. Renseigné = cours écrit par un client, invisible aux autres.
    #
    # Ce modèle reste volontairement hors de ``TenantScopedModel`` : un cours
    # de bibliothèque n'appartient à personne, et le rendre cloisonné aurait
    # obligé à en dupliquer un exemplaire par client — soit exactement ce que
    # la séparation catalogue/attribution évite depuis ADR-029.
    owner_tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    # D'où vient ce cours, quand il a été dérivé d'un autre. Sert à retrouver
    # l'original — et à ne pas croire qu'un client a écrit de zéro ce qu'il a
    # en réalité adapté.
    derived_from = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    @property
    def est_de_la_bibliotheque(self) -> bool:
        return self.owner_tenant_id is None

    @property
    def draft_version(self):
        """La version en cours d'écriture, s'il y en a une. Au plus une par
        cours : deux brouillons simultanés poseraient la question insoluble de
        savoir lequel publier."""
        return self.versions.filter(published_at__isnull=True).order_by("-number").first()

    @property
    def published_version(self):
        """La version publiée la plus récente, ou None. C'est elle qu'on
        inscrit — jamais un brouillon."""
        return self.versions.filter(published_at__isnull=False).order_by("-number").first()


class CourseVersion(models.Model):
    """Le contenu publié d'un cours, et les règles de son quiz.

    Une inscription pointe vers une VERSION. Conséquence voulue : republier un
    cours corrigé ne réécrit pas ce qu'ont suivi les salariés déjà inscrits, et
    une attestation reste adossée au contenu réellement suivi.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveSmallIntegerField(default=1)
    # Nul tant que la version est un brouillon. En F1 le cours de démonstration
    # est publié par sa commande de chargement ; en F2 ce sera le studio.
    published_at = models.DateTimeField(null=True, blank=True)
    pass_threshold = models.PositiveSmallIntegerField(default=SEUIL_REUSSITE_DEFAUT)
    max_attempts = models.PositiveSmallIntegerField(default=ESSAIS_DEFAUT)
    change_note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "number"], name="unique_version_number_per_course"
            ),
        ]
        ordering = ["course_id", "-number"]

    def __str__(self):
        return f"{self.course.title} — v{self.number}"

    @property
    def is_published(self) -> bool:
        return self.published_at is not None

    @property
    def estimated_minutes(self) -> int:
        """La durée annoncée au salarié, calculée depuis les écrans plutôt que
        saisie : une durée saisie à la main devient fausse au premier écran
        ajouté, et c'est précisément le chiffre sur lequel il décide de
        commencer maintenant ou plus tard."""
        total = sum(ecran.estimated_seconds for ecran in self.screens.all())
        return max(1, round(total / 60))


class Screen(models.Model):
    """Un écran : un titre, des blocs typés, une durée indicative.

    Pas de vidéo dans ce lot — trop lourd à produire, à héberger et à
    sous-titrer, et une vidéo non sous-titrée exclurait les salariés sourds.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(CourseVersion, on_delete=models.CASCADE, related_name="screens")
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    content = models.JSONField(default=list)
    estimated_seconds = models.PositiveSmallIntegerField(default=60)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["version", "order"], name="unique_screen_order"),
        ]
        ordering = ["version_id", "order"]

    def __str__(self):
        return f"{self.order}. {self.title}"

    def save(self, *args, **kwargs):
        # La validation est ici et non dans un sérialiseur : un sérialiseur ne
        # couvre que le chemin HTTP, alors que les écrans de F1 sont créés par
        # une commande de chargement, et ceux de F2 le seront par le studio.
        # Un seul point d'écriture, une seule garantie.
        self.content = blocs_de_contenu.valider(self.content)
        super().save(*args, **kwargs)


class Question(models.Model):
    """Une question de quiz, son explication, et l'écran qui y répond."""

    class Kind(models.TextChoices):
        SINGLE = "single", "Choix unique"
        MULTIPLE = "multiple", "Choix multiple"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(CourseVersion, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveSmallIntegerField()
    text = models.TextField()
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.SINGLE)
    # Obligatoire — contrainte portée en base par une condition d'unicité ne
    # suffirait pas, c'est le service d'écriture qui refuse une explication
    # vide. Un quiz qui dit seulement « faux » n'apprend rien : l'explication
    # est la seule partie du quiz qui forme.
    explanation = models.TextField()
    # L'écran à revoir quand cette question est ratée. C'est ce qui rend
    # possible de proposer trois écrans plutôt que le cours entier — sans ce
    # rattachement, « revoir ce que vous avez raté » n'a aucune source.
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, related_name="questions")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["version", "order"], name="unique_question_order"),
        ]
        ordering = ["version_id", "order"]

    def __str__(self):
        return f"Q{self.order} — {self.text[:60]}"

    @property
    def correct_choice_ids(self) -> set:
        return {choix.id for choix in self.choices.all() if choix.is_correct}


class Choice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    order = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["question", "order"], name="unique_choice_order"),
        ]
        ordering = ["question_id", "order"]

    def __str__(self):
        return self.text[:60]


# --- Côté client : tout ce qui suit est cloisonné par entreprise -------------


class CourseAssignment(TenantScopedModel):
    """Les cours qu'une entreprise peut proposer à ses salariés.

    Sans cette table, tout client verrait tout le catalogue — y compris un
    cours écrit pour un autre. Même rôle que ``ReferentialAssignment``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="+")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "course"], name="unique_course_assignment"),
        ]
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.tenant_id} — {self.course_id}"


class Learner(TenantScopedModel):
    """Un salarié qui suit des cours. **Pas nécessairement un utilisateur.**

    ``user`` nul est le cas courant : le salarié reçoit un lien nominatif et
    n'a jamais de compte (ADR-039). ``user`` renseigné est le cas de ceux qui
    pilotent et ont déjà un compte — ils suivent le même cours depuis leur
    espace, sur la même inscription, sans qu'on leur envoie par courriel un
    lien vers une page qu'ils atteignent par leur menu.

    Ce champ est la seule différence entre les deux portes. Tout le reste du
    module ignore laquelle a été empruntée.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="training_profiles",
    )
    # Un salarié parti n'est pas supprimé : ses attestations et sa progression
    # restent la preuve que l'entreprise l'a formé. Il est désactivé, et ses
    # liens cessent de fonctionner.
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "email"], name="unique_learner_email"),
        ]
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Enrollment(TenantScopedModel):
    """Un salarié, un cours dans une version donnée, une échéance.

    Ne porte aucune progression (voir l'en-tête du module). Réinscrire le même
    salarié l'an prochain crée une **nouvelle** inscription : l'historique est
    conservé au lieu d'être écrasé, ce qui rend possible le « il l'a suivi en
    2026 et refait en 2027 » sans migration au moment où on en aura besoin.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="enrollments")
    version = models.ForeignKey(CourseVersion, on_delete=models.PROTECT, related_name="+")
    # L'échéance de la campagne. C'est elle qui commande la durée de vie du
    # lien : ``expires_at`` = échéance + marge.
    due_date = models.DateField()

    # Le lien nominatif. Stocké HACHÉ, comme un mot de passe l'est : une fuite
    # de cette table ne doit pas suffire à se faire passer pour un salarié.
    # SHA-256 et non un hacheur lent — le jeton fait 256 bits d'aléa, il n'est
    # pas devinable, et le coût d'un hacheur lent serait payé à chaque page.
    token_hash = models.CharField(max_length=64, unique=True)
    token_issued_at = models.DateTimeField()

    # Première ouverture du cours. Fait distinct de la progression : quelqu'un
    # peut ouvrir et ne terminer aucun écran, et c'est une information utile.
    first_opened_at = models.DateTimeField(null=True, blank=True)

    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    # Dernière demande d'accès déposée depuis la page d'expiration. Sert à ne
    # pas laisser quelqu'un qui détient un lien mort relancer les
    # administrateurs du client dix fois dans la journée.
    access_requested_at = models.DateTimeField(null=True, blank=True)

    # Réarmement après épuisement des essais. Un blocage définitif sans recours
    # crée un appel au support, et il y aura toujours un cas légitime — une
    # coupure réseau au milieu d'un quiz, par exemple.
    extra_attempts = models.PositiveSmallIntegerField(default=0)
    attempts_granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    attempts_granted_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Une seule inscription VIVANTE par salarié et par version. Les
            # inscriptions révoquées s'accumulent — c'est l'historique. Même
            # forme que la contrainte partielle d'``AccessRequest``.
            models.UniqueConstraint(
                fields=["tenant", "learner", "version"],
                condition=models.Q(revoked_at__isnull=True),
                name="unique_active_enrollment",
            ),
        ]
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "due_date"])]

    def __str__(self):
        return f"{self.learner_id} — {self.version_id}"

    @property
    def expires_at(self):
        """La validité suit la campagne, pas un compteur arbitraire."""
        fin = self.due_date + timedelta(days=MARGE_APRES_ECHEANCE_JOURS)
        # Fin de journée et non minuit : « valable jusqu'au 12 » doit inclure
        # le 12. Un lien qui meurt à 00 h 00 du jour annoncé retire un jour
        # entier sans le dire.
        return timezone.make_aware(datetime.combine(fin, time.max), timezone.get_current_timezone())

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_usable(self) -> bool:
        return not self.is_revoked and not self.is_expired and self.learner.is_active

    @property
    def attempts_allowed(self) -> int:
        return self.version.max_attempts + self.extra_attempts


class ScreenProgress(TenantScopedModel):
    """Un écran terminé. La source unique de « où en est-il ».

    Revenir en arrière ne supprime jamais une ligne : la navigation est libre,
    la progression enregistrée reste la progression réelle.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="progress")
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, related_name="+")
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "screen"], name="unique_screen_progress"),
        ]
        ordering = ["enrollment_id", "screen_id"]

    def __str__(self):
        return f"{self.enrollment_id} — écran {self.screen_id}"


class Attempt(TenantScopedModel):
    """Une tentative de quiz. Les compter donne les essais consommés."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="attempts")
    number = models.PositiveSmallIntegerField()
    score = models.PositiveSmallIntegerField()
    passed = models.BooleanField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "number"], name="unique_attempt_number"),
        ]
        ordering = ["enrollment_id", "number"]

    def __str__(self):
        return f"Essai {self.number} — {self.score}%"


class AttemptAnswer(TenantScopedModel):
    """Ce qui a été répondu, question par question.

    Sans cette trace, « revoir les écrans concernés par vos erreurs » n'aurait
    aucune source et on ne pourrait proposer que le cours entier.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="+")
    # Les identifiants retenus, tels qu'envoyés. Une liste JSON plutôt qu'une
    # table de liaison : on ne requête jamais « qui a coché ce choix », on
    # relit toujours une tentative entière.
    selected_choice_ids = models.JSONField(default=list)
    is_correct = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="unique_attempt_answer"),
        ]
        ordering = ["attempt_id", "question_id"]

    def __str__(self):
        return f"{self.attempt_id} — Q{self.question_id}"


class ReminderPolicy(TenantScopedModel):
    """Le rythme des relances, réglé par l'entreprise (F3).

    **Désactivable, et c'est la première exigence.** Une relance qu'on ne peut
    pas couper devient du harcèlement — et le harcèlement d'un salarié par un
    outil que son employeur a acheté reste du harcèlement.

    Trois moments seulement, parce qu'un quatrième serait du remplissage : à
    mi-parcours, peu avant l'échéance, peu après. Chacun se coupe séparément :
    une entreprise peut vouloir prévenir avant l'échéance sans jamais relancer
    après.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enabled = models.BooleanField(default=True)
    #: Relance à mi-parcours de la campagne (entre l'inscription et l'échéance).
    mid_course = models.BooleanField(default=True)
    #: Jours AVANT l'échéance. 0 = pas de relance à ce moment.
    before_due_days = models.PositiveSmallIntegerField(default=3)
    #: Jours APRÈS l'échéance. 0 = on ne relance pas une fois le délai passé.
    after_due_days = models.PositiveSmallIntegerField(default=2)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="unique_reminder_policy_per_tenant"),
        ]

    def __str__(self):
        return f"Relances de {self.tenant_id} ({'actives' if self.enabled else 'coupées'})"


class ReminderLog(TenantScopedModel):
    """Une relance envoyée. Sa raison d'être est l'unicité.

    ``unique(enrollment, kind)`` est le garde-fou contre le défaut le plus
    facile à produire ici : une tâche quotidienne qui renvoie le même message
    tous les jours parce que la condition reste vraie. Chaque nature de relance
    part **une fois** par inscription, et jamais plus.
    """

    class Kind(models.TextChoices):
        MID = "mid", "À mi-parcours"
        BEFORE = "before", "Avant l'échéance"
        AFTER = "after", "Après l'échéance"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="reminders")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "kind"], name="unique_reminder_per_kind"),
        ]
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.enrollment_id}"


class NominativeAccessLog(TenantScopedModel):
    """Qui a consulté le suivi NOMINATIF des salariés, et quand (F3, ADR-041).

    Le module publie des agrégats. La liste par salarié existe pour une seule
    raison — savoir qui relancer — et cet usage-là se trace : c'est la
    contrepartie que le RGPD attend d'un traitement des données de salariés
    par leur employeur.

    On enregistre le NOMBRE de lignes consultées, pas les lignes : un journal
    d'accès qui recopierait les données qu'il protège serait un second fichier
    du même traitement.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    #: Le cours consulté, ou vide pour « tous ».
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    rows = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "-created_at"])]

    def __str__(self):
        return f"{self.actor_id} → {self.rows} ligne(s) le {self.created_at:%d/%m/%Y}"


class MeasureSuggestion(TenantScopedModel):
    """Une campagne de formation propose de renseigner une mesure du
    diagnostic, **preuve à l'appui** (F3, ADR-041).

    Le mot qui compte est *propose*. Une mesure de conformité cochée sans que
    personne l'ait décidée serait une affirmation que le client n'a pas faite,
    et qu'il découvrirait devant un auditeur. La proposition attend donc une
    confirmation humaine, et conserve la trace de qui a tranché.

    Les chiffres sont **figés à la proposition** : ils constituent la preuve.
    Relire le taux de participation six mois plus tard donnerait un autre
    nombre, et la preuve ne prouverait plus ce qu'elle disait.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "À confirmer"
        ACCEPTED = "accepted", "Confirmée"
        DISMISSED = "dismissed", "Écartée"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="+")
    referential_slug = models.SlugField(max_length=220)
    measure_code = models.CharField(max_length=50)
    #: Figé : une mesure renommée ne doit pas rendre illisible une preuve.
    measure_title = models.CharField(max_length=300)

    learners_total = models.PositiveIntegerField()
    learners_done = models.PositiveIntegerField()
    participation_rate = models.PositiveSmallIntegerField()
    success_rate = models.PositiveSmallIntegerField()
    period_start = models.DateField()
    period_end = models.DateField()

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Une seule proposition VIVANTE par cours et par mesure : la tâche
            # quotidienne ne doit pas empiler des doublons.
            models.UniqueConstraint(
                fields=["tenant", "course", "measure_code"],
                condition=models.Q(status="pending"),
                name="unique_pending_measure_suggestion",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.measure_code} ← {self.course_id} ({self.status})"


class Certificate(TenantScopedModel):
    """L'attestation de suivi. Son existence EST la preuve de réussite.

    Tous les libellés sont **figés à l'émission**. Un cours renommé, une
    entreprise rebaptisée ou un salarié dont on corrige l'orthographe ne
    doivent pas réécrire une attestation délivrée il y a huit mois : c'est la
    différence entre une trace et une affirmation. Même raisonnement que
    ``AccessRequest.subject_label`` et que le texte de déclaration d'ADR-033.

    Le PDF n'est pas stocké : il est réimprimé à la demande depuis ces champs.
    Rien à sauvegarder, rien à purger, et deux impressions donnent le même
    document.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.OneToOneField(
        Enrollment, on_delete=models.CASCADE, related_name="certificate"
    )
    serial = models.CharField(max_length=20)
    issued_at = models.DateTimeField(auto_now_add=True)

    learner_name = models.CharField(max_length=150)
    course_title = models.CharField(max_length=200)
    course_version = models.PositiveSmallIntegerField()
    company_name = models.CharField(max_length=200)
    score = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "serial"], name="unique_certificate_serial"),
        ]
        ordering = ["-issued_at"]

    def __str__(self):
        return f"{self.serial} — {self.learner_name}"

    @staticmethod
    def build_serial() -> str:
        """Lisible, triable par année, et sans compteur partagé : deux
        émissions simultanées ne peuvent pas se disputer un numéro."""
        return f"{timezone.now().year}-{secrets.token_hex(4).upper()}"
