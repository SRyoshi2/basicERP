from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.errors import VersionConflict

from .models import TimeEntry, TimeEntryAuditEvent


TIME_ENTRY_FIELDS = (
    "project", "work_package", "work_date", "duration_minutes", "description", "billable",
)


def resolve_hourly_rate(work_package):
    return work_package.resolved_hourly_rate


@transaction.atomic
def create_time_entry(validated_data, actor):
    work_package = validated_data["work_package"]
    entry = TimeEntry(
        employee=actor,
        hourly_rate_snapshot=resolve_hourly_rate(work_package),
        created_by=actor,
        updated_by=actor,
        **validated_data,
    )
    entry.full_clean()
    entry.save()
    TimeEntryAuditEvent.objects.create(
        time_entry=entry,
        action=TimeEntryAuditEvent.Action.CREATED,
        version=entry.version,
        actor=actor,
        changes={"billable": entry.billable},
    )
    return entry


@transaction.atomic
def update_time_entry(entry_id, validated_data, actor):
    expected_version = validated_data.pop("version")
    entry = TimeEntry.objects.select_for_update().select_related(
        "project", "work_package", "employee"
    ).get(pk=entry_id)
    if entry.version != expected_version:
        raise VersionConflict
    if entry.billing_status == TimeEntry.BillingStatus.BILLED:
        raise ValueError("Abgerechnete Zeiteinträge sind unveränderbar.")
    changed_fields = []
    for field in TIME_ENTRY_FIELDS:
        if field in validated_data and getattr(entry, field) != validated_data[field]:
            setattr(entry, field, validated_data[field])
            changed_fields.append(field)
    if "work_package" in changed_fields:
        entry.hourly_rate_snapshot = resolve_hourly_rate(entry.work_package)
        changed_fields.append("hourly_rate_snapshot")
    entry.version += 1
    entry.updated_by = actor
    entry.full_clean()
    entry.save(
        update_fields=(
            *TIME_ENTRY_FIELDS, "hourly_rate_snapshot", "version", "updated_by", "updated_at",
        )
    )
    TimeEntryAuditEvent.objects.create(
        time_entry=entry,
        action=TimeEntryAuditEvent.Action.UPDATED,
        version=entry.version,
        actor=actor,
        changes={"changed_fields": sorted(set(changed_fields))},
    )
    return entry


@transaction.atomic
def archive_time_entry(entry_id, actor):
    entry = TimeEntry.objects.select_for_update().get(pk=entry_id)
    if entry.billing_status == TimeEntry.BillingStatus.BILLED:
        raise ValueError("Abgerechnete Zeiteinträge sind unveränderbar.")
    if entry.archived_at is None:
        entry.archived_at = timezone.now()
        entry.version += 1
        entry.updated_by = actor
        entry.save(update_fields=("archived_at", "version", "updated_by", "updated_at"))
        TimeEntryAuditEvent.objects.create(
            time_entry=entry,
            action=TimeEntryAuditEvent.Action.ARCHIVED,
            version=entry.version,
            actor=actor,
            changes={},
        )
    return entry


def project_time_summary(project):
    entries = list(project.time_entries.filter(archived_at__isnull=True))
    actual_minutes = sum(item.duration_minutes for item in entries)
    billable = [item for item in entries if item.billable]
    unbilled = [item for item in billable if item.billing_status == TimeEntry.BillingStatus.UNBILLED]
    actual_value = sum(
        (item.billable_value for item in billable if item.billable_value is not None),
        start=Decimal("0"),
    )
    unbilled_value = sum(
        (item.billable_value for item in unbilled if item.billable_value is not None),
        start=Decimal("0"),
    )
    actual_hours = Decimal(actual_minutes) / Decimal("60")
    billable_hours = Decimal(sum(item.duration_minutes for item in billable)) / Decimal("60")
    unbilled_hours = Decimal(sum(item.duration_minutes for item in unbilled)) / Decimal("60")
    return {
        "entry_count": len(entries),
        "actual_hours": actual_hours,
        "billable_hours": billable_hours,
        "unbilled_hours": unbilled_hours,
        "non_billable_hours": actual_hours - billable_hours,
        "actual_value": actual_value,
        "unbilled_value": unbilled_value,
        "remaining_budget_hours": None
        if project.budget_hours is None
        else project.budget_hours - actual_hours,
        "remaining_budget_amount": None
        if project.budget_amount is None
        else project.budget_amount - actual_value,
    }
