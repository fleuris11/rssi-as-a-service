from django.conf import settings
from django.db import models

from apps.tenants.models import Tenant, TenantScopedModel


class Referential(models.Model):
    """Un référentiel de conformité : l'ANSSI, l'annexe A d'ISO 27001, le NIST
    CSF, les CIS Controls, ou un référentiel propre à un client.

    Catalogue partagé, **non scopé par tenant** : la structure est chargée une
    fois (``manage.py import_referential``) et lue par tous les clients à qui
    elle est **attribuée** (``ReferentialAssignment``). Un référentiel propre à
    un client fait exception et porte son ``owner_tenant`` — il reste une ligne
    du même catalogue, simplement invisible aux autres.

    ``kind`` porte la question des droits, et elle n'est pas décorative :
    l'ANSSI est sous Licence Ouverte et peut être embarquée dans le dépôt ;
    ISO 27001 et le NIST CSF ne le peuvent pas. Le produit fournit la structure
    d'accueil, l'exploitant ou le client importe ce qu'il a le droit
    d'utiliser. Voir docs/format_import_referentiel.md §Droits.
    """

    class Kind(models.TextChoices):
        # Contenu libre de droits, embarqué dans le dépôt (ANSSI).
        OPEN = "open", "Libre de droits"
        # Contenu soumis à droits : le dépôt ne contient QUE la coquille,
        # l'import est fait par celui qui détient la licence.
        LICENSED = "licensed", "Soumis à droits (importé par l'exploitant)"
        # Référentiel écrit pour un client, ou par lui.
        CUSTOM = "custom", "Propre à un client"

    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    version = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OPEN)
    source_url = models.URLField(blank=True)
    # Mention de droits affichée avec le référentiel. Vide pour l'ANSSI
    # (Licence Ouverte, déjà dite dans le fichier source) ; renseignée à
    # l'import pour tout contenu sous licence, où elle est la seule trace de
    # ce qu'on a le droit d'en faire.
    licence_notice = models.CharField(max_length=300, blank=True)
    # Référentiel écrit pour un seul client : personne d'autre ne le voit,
    # même attribué par erreur (voir services.list_catalog).
    owner_tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.version})"


class Domain(models.Model):
    """A group of measures within a referential (e.g. "Sécuriser les postes")."""

    referential = models.ForeignKey(Referential, on_delete=models.CASCADE, related_name="domains")
    code = models.SlugField(max_length=100)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["referential", "code"], name="unique_domain_code"),
        ]
        ordering = ["referential_id", "order"]

    def __str__(self):
        return self.name


class Measure(models.Model):
    """Une mesure d'un référentiel — une des 42 de l'ANSSI, un contrôle de
    l'annexe A d'ISO 27001, une sous-catégorie du NIST CSF."""

    class Level(models.TextChoices):
        """Niveaux de l'ANSSI. Conservés comme constantes nommées parce que
        l'importateur et les tests s'y réfèrent — mais le champ n'est plus
        contraint à ces deux valeurs : un référentiel sans niveaux laisse le
        champ vide, un autre a les siens."""

        STANDARD = "standard", "Standard"
        RENFORCE = "renforce", "Renforcé"

    class Effort(models.TextChoices):
        LOW = "low", "Faible"
        MEDIUM = "medium", "Moyen"
        HIGH = "high", "Élevé"

    class Impact(models.TextChoices):
        LOW = "low", "Faible"
        MEDIUM = "medium", "Moyen"
        HIGH = "high", "Élevé"

    # Dénormalisé depuis ``domain.referential`` : une contrainte d'unicité
    # Django ne traverse pas une relation, et « le code d'une mesure est unique
    # DANS SON RÉFÉRENTIEL » est exactement la garantie qu'il faut tenir dès
    # qu'il y en a plusieurs. Posé et vérifié par l'importateur
    # (import_referential), jamais saisi à la main.
    referential = models.ForeignKey(Referential, on_delete=models.CASCADE, related_name="measures")
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="measures")
    # L'identifiant tel qu'il figure dans le référentiel : « 1 » pour l'ANSSI,
    # « A.5.1 » pour ISO 27001, « PR.AA-01 » pour le NIST CSF. Une chaîne, donc,
    # et pas un entier — c'était l'hypothèse ANSSI la plus coûteuse du modèle
    # précédent.
    code = models.CharField(max_length=40)
    # Numérotation officielle quand le référentiel en a une (ANSSI : 1-42).
    # Nullable : ISO et le NIST n'en ont pas. Conservée à côté de ``code``
    # parce que le rapport de vérification du référentiel ANSSI
    # (docs/verification_referentiel_anssi.md) épingle ces entiers.
    number = models.PositiveSmallIntegerField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    official_title = models.CharField(max_length=300)
    plain_language = models.TextField()
    level = models.CharField(max_length=40, blank=True)
    # Poids de la mesure dans le score. Explicite depuis V2-4 : le calcul
    # lisait auparavant une table {standard: 1.0, renforcé: 0.5} figée dans le
    # code, ce qui n'a de sens que pour l'ANSSI. Le fichier d'import porte le
    # poids ; à défaut, 1.0 — toutes les mesures comptent pareil.
    weight = models.FloatField(default=1.0)
    effort = models.CharField(max_length=10, choices=Effort.choices)
    impact = models.CharField(max_length=10, choices=Impact.choices)
    # effort/impact (above) are a RSSI as a Service product judgment, not
    # ANSSI data — always True today; kept as a field (rather than a code
    # constant) so the API/frontend carry the disclaimer even if a future
    # referential someday ships ANSSI-sourced ratings instead.
    effort_impact_disclaimer = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["referential", "code"], name="unique_measure_code_per_referential"
            ),
        ]
        ordering = ["domain_id", "order"]

    def __str__(self):
        return f"{self.code} — {self.official_title}"

    @property
    def statement(self) -> str:
        """L'énoncé à afficher. Vaut ``plain_language``, sauf si une surcharge
        client a été posée sur l'instance par ``services.apply_overrides`` —
        qui n'écrit jamais en base. La surcharge vit à côté, jamais à la
        place."""
        return getattr(self, "_override_statement", None) or self.plain_language

    @property
    def context_note(self) -> str:
        return getattr(self, "_override_note", "") or ""

    @property
    def is_overridden(self) -> bool:
        return bool(
            getattr(self, "_override_statement", None) or getattr(self, "_override_note", "")
        )


class MeasureStatementOverride(TenantScopedModel):
    """Reformulation d'une mesure **pour un client**, à côté du référentiel.

    Ne touche jamais ``Measure`` : le référentiel d'origine reste intact pour
    tous les autres clients, et le retrait de la surcharge fait réapparaître
    l'énoncé d'origine sans reconstruction.

    Seul l'énoncé en langage clair est surchargeable. **Pas l'intitulé
    officiel** : c'est la citation du référentiel, et la réécrire ferait dire à
    l'ANSSI ou à l'ISO ce qu'ils ne disent pas. Un client qui veut préciser le
    contexte ajoute ``context_note``, affichée sous l'énoncé.
    """

    measure = models.ForeignKey(Measure, on_delete=models.CASCADE, related_name="overrides")
    plain_language = models.TextField(blank=True)
    context_note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "measure"], name="unique_override_per_measure"
            ),
        ]
        ordering = ["measure__order"]

    def __str__(self):
        return f"{self.tenant_id} — {self.measure_id}"


class MeasureSubset(models.Model):
    """Un sous-ensemble de mesures d'un référentiel, enregistré comme modèle
    réutilisable : « ANSSI — 10 mesures essentielles », un questionnaire de 30
    mesures pour une TPE qui ne tiendrait pas les 42.

    ``owner_tenant`` nul = modèle de plateforme, proposable à tout client à qui
    le référentiel est attribué. Renseigné = composition écrite pour un client.
    """

    referential = models.ForeignKey(Referential, on_delete=models.CASCADE, related_name="subsets")
    slug = models.SlugField(max_length=100)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner_tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["referential", "slug"], name="unique_subset_slug"),
        ]
        ordering = ["referential_id", "name"]

    def __str__(self):
        return f"{self.name} ({self.referential.slug})"


class SubsetMeasure(models.Model):
    """Appartenance d'une mesure à un sous-ensemble, et son rang dedans."""

    subset = models.ForeignKey(MeasureSubset, on_delete=models.CASCADE, related_name="items")
    measure = models.ForeignKey(Measure, on_delete=models.CASCADE, related_name="+")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["subset", "measure"], name="unique_subset_measure"),
        ]
        ordering = ["subset_id", "order"]

    def __str__(self):
        return f"{self.subset_id} — {self.measure_id}"


class ReferentialAssignment(TenantScopedModel):
    """Attribution d'un référentiel à un client, depuis la console.

    Le retrait est **logique** (``revoked_at``) et jamais une suppression : un
    client qui perd l'accès à un référentiel garde en lecture les évaluations
    qu'il a produites dessus. On ne prend pas en otage des données déjà
    produites — et la ligne reste la trace de qui a donné puis retiré l'accès,
    et quand.
    """

    referential = models.ForeignKey(
        Referential, on_delete=models.PROTECT, related_name="assignments"
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "referential"], name="unique_assignment_per_referential"
            ),
        ]
        ordering = ["tenant_id", "referential__name"]

    def __str__(self):
        etat = "retiré" if self.revoked_at else "actif"
        return f"{self.tenant_id} — {self.referential_id} ({etat})"

    @property
    def is_granted(self) -> bool:
        return self.revoked_at is None


class Assessment(TenantScopedModel):
    """One diagnostic session for a tenant against a referential. A tenant
    may have several over time (US-2.3: re-run periodically, track score
    evolution) — history is simply the list of completed assessments.

    Depuis V2-4, un client peut en mener plusieurs en parallèle : une par
    référentiel attribué. « L'évaluation en cours » n'est donc plus unique —
    elle l'est *par référentiel*.
    """

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "En cours"
        COMPLETED = "completed", "Terminée"

    referential = models.ForeignKey(Referential, on_delete=models.PROTECT, related_name="+")
    # Périmètre restreint : quand il est posé, le questionnaire, la progression
    # et le score ne portent que sur les mesures du sous-ensemble. Nul = le
    # référentiel entier.
    subset = models.ForeignKey(
        MeasureSubset, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Snapshot of the global score at completion time — deliberately not
    # recomputed later, so historical trend data stays stable even if the
    # referential's measures evolve in a future version.
    score_global = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.tenant_id} — {self.referential.slug} ({self.status})"


class Answer(TenantScopedModel):
    """One answer to one measure within one assessment."""

    class Value(models.TextChoices):
        YES = "yes", "Oui"
        PARTIAL = "partial", "Partiellement"
        NO = "no", "Non"
        NOT_APPLICABLE = "na", "Non applicable"

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="answers")
    measure = models.ForeignKey(Measure, on_delete=models.PROTECT, related_name="+")
    value = models.CharField(max_length=10, choices=Value.choices)
    note = models.TextField(blank=True)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "measure"], name="unique_answer_per_measure"
            ),
        ]
        ordering = ["assessment_id", "measure__domain_id", "measure__order"]

    def __str__(self):
        return f"{self.assessment_id} — {self.measure.code}: {self.value}"
