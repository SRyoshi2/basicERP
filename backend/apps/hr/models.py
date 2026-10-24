import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def count_weekdays(start_date, end_date):
    current = start_date
    days = 0
    while current <= end_date:
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    return Decimal(days)


class LeaveEntitlement(models.Model):
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leave_entitlements"
    )
    year = models.PositiveSmallIntegerField()
    entitlement_days = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    carryover_days = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="updated_leave_entitlements",
    )

    class Meta:
        ordering = ("-year", "employee__username")
        constraints = [
            models.UniqueConstraint(
                fields=("employee", "year"), name="leave_entitlement_employee_year_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(entitlement_days__gte=0),
                name="leave_entitlement_days_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(carryover_days__gte=0),
                name="leave_entitlement_carryover_non_negative",
            ),
        ]


class AbsenceRequest(models.Model):
    class Kind(models.TextChoices):
        VACATION = "vacation", "Urlaub"
        SICKNESS = "sickness", "Krankheit"
        OTHER = "other", "Sonstiges"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Beantragt"
        APPROVED = "approved", "Genehmigt"
        REJECTED = "rejected", "Abgelehnt"
        CANCELLED = "cancelled", "Storniert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="absence_requests"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    note = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.REQUESTED
    )
    decision_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_absence_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-start_date", "-created_at")
        indexes = [
            models.Index(fields=("employee", "start_date", "end_date")),
            models.Index(fields=("status", "start_date")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="absence_end_not_before_start",
            ),
        ]

    @property
    def working_days(self):
        return count_weekdays(self.start_date, self.end_date)

    def clean(self):
        errors = {}
        if self.end_date and self.start_date and self.end_date < self.start_date:
            errors["end_date"] = "Das Enddatum darf nicht vor dem Startdatum liegen."
        if self.employee_id and not self.employee.is_active:
            errors["employee"] = "Abwesenheiten können nur für aktive Benutzer erfasst werden."
        if errors:
            raise ValidationError(errors)


class AbsenceRequestAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Erstellt"
        UPDATED = "updated", "Geändert"
        APPROVED = "approved", "Genehmigt"
        REJECTED = "rejected", "Abgelehnt"
        CANCELLED = "cancelled", "Storniert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    absence_request = models.ForeignKey(
        AbsenceRequest, on_delete=models.PROTECT, related_name="audit_events"
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    version = models.PositiveIntegerField()
    changes = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="absence_request_audit_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
