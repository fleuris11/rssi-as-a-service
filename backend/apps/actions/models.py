from django.conf import settings
from django.db import models

from apps.tenants.models import TenantScopedModel


class ActionItem(TenantScopedModel):
    """One item of a tenant's action plan — a gap (non/partial answer) on
    one measure of one assessment, auto-generated on assessment completion
    (see apps.actions.services.generate_action_plan).

    ``assessment``/``measure`` reference apps.assessments models by string
    (not a direct import) — the FK relationship is a schema-level need,
    Django's lazy string reference is exactly the tool for declaring it
    without coupling this app's models module to assessments' internals.
    """

    class Status(models.TextChoices):
        TODO = "todo", "À faire"
        IN_PROGRESS = "in_progress", "En cours"
        DONE = "done", "Fait"

    assessment = models.ForeignKey(
        "assessments.Assessment", on_delete=models.CASCADE, related_name="action_items"
    )
    measure = models.ForeignKey("assessments.Measure", on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "measure"], name="unique_action_item_per_measure"
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.measure_id} ({self.status})"
