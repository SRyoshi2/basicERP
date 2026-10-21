import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ProjectNumberSequence(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    next_value = models.PositiveBigIntegerField(default=1001)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_project_sequence")]


class Project(models.Model):
    class Status(models.TextChoices):
        QUOTATION = "quotation", "Angebot"
        ACTIVE = "active", "Aktiv"
        PAUSED = "paused", "Pausiert"
        COMPLETED = "completed", "Abgeschlossen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_number = models.CharField(max_length=24, unique=True, editable=False)
    customer = models.ForeignKey("crm.Contact", on_delete=models.PROTECT, related_name="projects")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUOTATION)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    budget_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    default_hourly_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_projects"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="updated_projects"
    )

    class Meta:
        ordering = ("project_number",)
        indexes = [
            models.Index(fields=("status", "archived_at")),
            models.Index(fields=("customer", "archived_at")),
            models.Index(fields=("name",)),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True) | models.Q(start_date__isnull=True) | models.Q(end_date__gte=models.F("start_date")),
                name="project_valid_period",
            ),
            models.CheckConstraint(condition=models.Q(budget_amount__isnull=True) | models.Q(budget_amount__gte=0), name="project_budget_amount_non_negative"),
            models.CheckConstraint(condition=models.Q(budget_hours__isnull=True) | models.Q(budget_hours__gte=0), name="project_budget_hours_non_negative"),
            models.CheckConstraint(condition=models.Q(default_hourly_rate__isnull=True) | models.Q(default_hourly_rate__gte=0), name="project_hourly_rate_non_negative"),
        ]

    def clean(self):
        if self.customer_id and self.customer.archived_at is not None:
            raise ValidationError({"customer": "Archivierte Kontakte können keinem Projekt zugeordnet werden."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "Das Enddatum darf nicht vor dem Startdatum liegen."})

    def __str__(self):
        return f"{self.project_number} · {self.name}"


class ProjectAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Erstellt"
        UPDATED = "updated", "Geändert"
        ARCHIVED = "archived", "Archiviert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=16, choices=Action.choices)
    version = models.PositiveIntegerField()
    changes = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="project_audit_events"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
