import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TimeEntry(models.Model):
    class BillingStatus(models.TextChoices):
        UNBILLED = "unbilled", "Nicht abgerechnet"
        BILLED = "billed", "Abgerechnet"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="time_entries"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="time_entries"
    )
    work_package = models.ForeignKey(
        "projects.WorkPackage", on_delete=models.PROTECT, related_name="time_entries"
    )
    work_date = models.DateField()
    duration_minutes = models.PositiveIntegerField()
    description = models.TextField()
    billable = models.BooleanField(default=True)
    billing_status = models.CharField(
        max_length=16, choices=BillingStatus.choices, default=BillingStatus.UNBILLED
    )
    hourly_rate_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, editable=False
    )
    version = models.PositiveIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_time_entries",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="updated_time_entries",
    )

    class Meta:
        ordering = ("-work_date", "-created_at")
        indexes = [
            models.Index(fields=("employee", "work_date", "archived_at")),
            models.Index(fields=("project", "work_date", "archived_at")),
            models.Index(fields=("work_package", "work_date", "archived_at")),
            models.Index(fields=("billing_status", "billable", "archived_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_minutes__gte=1) & models.Q(duration_minutes__lte=1440),
                name="time_entry_duration_range",
            ),
            models.CheckConstraint(
                condition=models.Q(hourly_rate_snapshot__isnull=True)
                | models.Q(hourly_rate_snapshot__gte=0),
                name="time_entry_rate_non_negative",
            ),
        ]

    @property
    def duration_hours(self):
        return Decimal(self.duration_minutes) / Decimal("60")

    @property
    def billable_value(self):
        if not self.billable or self.hourly_rate_snapshot is None:
            return None
        return self.hourly_rate_snapshot * self.duration_minutes / 60

    def clean(self):
        errors = {}
        if self.project_id and self.project.archived_at is not None:
            errors["project"] = "Für archivierte Projekte können keine Zeiten erfasst werden."
        if self.work_package_id:
            if self.work_package.archived_at is not None:
                errors["work_package"] = "Für archivierte Arbeitspakete können keine Zeiten erfasst werden."
            elif self.project_id and self.work_package.project_id != self.project_id:
                errors["work_package"] = "Das Arbeitspaket gehört nicht zum gewählten Projekt."
        if self.employee_id and not self.employee.is_active:
            errors["employee"] = "Zeiten können nur aktiven Benutzern zugeordnet werden."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.work_date} · {self.employee} · {self.duration_minutes} min"


class TimeEntryAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Erstellt"
        UPDATED = "updated", "Geändert"
        ARCHIVED = "archived", "Archiviert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    time_entry = models.ForeignKey(TimeEntry, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=16, choices=Action.choices)
    version = models.PositiveIntegerField()
    changes = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="time_entry_audit_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class ServiceEntry(models.Model):
    class BillingStatus(models.TextChoices):
        UNBILLED = "unbilled", "Nicht abgerechnet"
        BILLED = "billed", "Abgerechnet"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="service_entries"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="service_entries"
    )
    work_package = models.ForeignKey(
        "projects.WorkPackage", on_delete=models.PROTECT, related_name="service_entries"
    )
    catalog_item = models.ForeignKey(
        "catalog.CatalogItem", on_delete=models.PROTECT, related_name="service_entries"
    )
    service_date = models.DateField()
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    description = models.TextField(blank=True)
    billable = models.BooleanField(default=True)
    billing_status = models.CharField(
        max_length=16, choices=BillingStatus.choices, default=BillingStatus.UNBILLED
    )
    catalog_item_number_snapshot = models.CharField(max_length=24, editable=False)
    catalog_item_name_snapshot = models.CharField(max_length=200, editable=False)
    unit_snapshot = models.CharField(max_length=16, editable=False)
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    tax_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2, editable=False)
    version = models.PositiveIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_service_entries",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="updated_service_entries",
    )

    class Meta:
        ordering = ("-service_date", "-created_at")
        indexes = [
            models.Index(fields=("employee", "service_date", "archived_at")),
            models.Index(fields=("project", "service_date", "archived_at")),
            models.Index(fields=("billing_status", "billable", "archived_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="service_entry_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price_snapshot__gte=0),
                name="service_entry_price_non_negative",
            ),
        ]

    @property
    def total_net(self):
        return self.quantity * self.unit_price_snapshot

    def clean(self):
        errors = {}
        if self.project_id and self.project.archived_at is not None:
            errors["project"] = "Für archivierte Projekte können keine Leistungen erfasst werden."
        if self.work_package_id:
            if self.work_package.archived_at is not None:
                errors["work_package"] = "Für archivierte Arbeitspakete können keine Leistungen erfasst werden."
            elif self.project_id and self.work_package.project_id != self.project_id:
                errors["work_package"] = "Das Arbeitspaket gehört nicht zum gewählten Projekt."
        if self.catalog_item_id:
            if self.catalog_item.archived_at is not None:
                errors["catalog_item"] = "Archivierte Katalogleistungen können nicht erfasst werden."
            elif self.catalog_item.kind != "service":
                errors["catalog_item"] = "Es können nur Katalogeinträge vom Typ Leistung erfasst werden."
        if self.employee_id and not self.employee.is_active:
            errors["employee"] = "Leistungen können nur aktiven Benutzern zugeordnet werden."
        if errors:
            raise ValidationError(errors)


class ServiceEntryAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Erstellt"
        UPDATED = "updated", "Geändert"
        ARCHIVED = "archived", "Archiviert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_entry = models.ForeignKey(
        ServiceEntry, on_delete=models.PROTECT, related_name="audit_events"
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    version = models.PositiveIntegerField()
    changes = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="service_entry_audit_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
