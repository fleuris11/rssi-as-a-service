from django.conf import settings
from django.db import models

from apps.tenants.models import TenantScopedModel


class Referential(models.Model):
    """A compliance framework (ANSSI hygiene guide, and later NIS2/ISO 27001 —
    cadrage §3.2). Shared catalog data, not tenant-scoped: loaded once via
    the ``load_anssi_referential`` management command, read-only from the API."""

    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    version = models.CharField(max_length=20)
    description = models.TextField(blank=True)
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
    """One of the 42 ANSSI hygiene measures (or a future referential's)."""

    class Level(models.TextChoices):
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

    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="measures")
    # The official ANSSI numbering (1-42), reproduced exactly — not a
    # product-invented code. See docs/verification_referentiel_anssi.md.
    number = models.PositiveSmallIntegerField(unique=True)
    order = models.PositiveSmallIntegerField(default=0)
    official_title = models.CharField(max_length=300)
    plain_language = models.TextField()
    level = models.CharField(max_length=20, choices=Level.choices)
    effort = models.CharField(max_length=10, choices=Effort.choices)
    impact = models.CharField(max_length=10, choices=Impact.choices)
    # effort/impact (above) are a RSSI as a Service product judgment, not
    # ANSSI data — always True today; kept as a field (rather than a code
    # constant) so the API/frontend carry the disclaimer even if a future
    # referential someday ships ANSSI-sourced ratings instead.
    effort_impact_disclaimer = models.BooleanField(default=True)

    class Meta:
        ordering = ["domain_id", "order"]

    def __str__(self):
        return f"{self.number} — {self.official_title}"


class Assessment(TenantScopedModel):
    """One diagnostic session for a tenant against a referential. A tenant
    may have several over time (US-2.3: re-run periodically, track score
    evolution) — history is simply the list of completed assessments."""

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "En cours"
        COMPLETED = "completed", "Terminée"

    referential = models.ForeignKey(Referential, on_delete=models.PROTECT, related_name="+")
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
        return f"{self.assessment_id} — {self.measure.number}: {self.value}"
