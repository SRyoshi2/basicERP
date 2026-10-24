from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.errors import VersionConflict

from .models import (
    AbsenceRequest, AbsenceRequestAuditEvent, LeaveEntitlement, count_weekdays,
)


EDITABLE_FIELDS = ("kind", "start_date", "end_date", "note")


def _validate_overlap(employee, start_date, end_date, exclude_id=None):
    queryset = AbsenceRequest.objects.filter(
        employee=employee,
        status__in=(AbsenceRequest.Status.REQUESTED, AbsenceRequest.Status.APPROVED),
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.exists():
        raise ValueError("Für diesen Zeitraum besteht bereits eine offene oder genehmigte Abwesenheit.")


def _days_in_year(absence, year):
    start = max(absence.start_date, date(year, 1, 1))
    end = min(absence.end_date, date(year, 12, 31))
    return count_weekdays(start, end) if start <= end else Decimal("0")


def leave_balance(employee, year):
    entitlement = LeaveEntitlement.objects.filter(employee=employee, year=year).first()
    entitlement_days = entitlement.entitlement_days if entitlement else Decimal("0")
    carryover_days = entitlement.carryover_days if entitlement else Decimal("0")
    vacations = AbsenceRequest.objects.filter(
        employee=employee,
        kind=AbsenceRequest.Kind.VACATION,
        start_date__lte=date(year, 12, 31),
        end_date__gte=date(year, 1, 1),
    )
    approved_days = sum(
        (_days_in_year(item, year) for item in vacations.filter(status=AbsenceRequest.Status.APPROVED)),
        start=Decimal("0"),
    )
    pending_days = sum(
        (_days_in_year(item, year) for item in vacations.filter(status=AbsenceRequest.Status.REQUESTED)),
        start=Decimal("0"),
    )
    return {
        "employee": employee.id,
        "year": year,
        "entitlement_days": entitlement_days,
        "carryover_days": carryover_days,
        "approved_days": approved_days,
        "pending_days": pending_days,
        "remaining_days": entitlement_days + carryover_days - approved_days,
        "version": entitlement.version if entitlement else None,
    }


@transaction.atomic
def create_absence(validated_data, actor):
    _validate_overlap(actor, validated_data["start_date"], validated_data["end_date"])
    absence = AbsenceRequest(employee=actor, **validated_data)
    absence.full_clean()
    absence.save()
    AbsenceRequestAuditEvent.objects.create(
        absence_request=absence,
        action=AbsenceRequestAuditEvent.Action.CREATED,
        version=absence.version,
        actor=actor,
        changes={"status": absence.status},
    )
    return absence


@transaction.atomic
def update_absence(absence_id, validated_data, actor):
    expected_version = validated_data.pop("version")
    absence = AbsenceRequest.objects.select_for_update().get(pk=absence_id)
    if absence.version != expected_version:
        raise VersionConflict
    if absence.status != AbsenceRequest.Status.REQUESTED:
        raise ValueError("Nur beantragte Abwesenheiten können bearbeitet werden.")
    for field in EDITABLE_FIELDS:
        if field in validated_data:
            setattr(absence, field, validated_data[field])
    _validate_overlap(
        absence.employee, absence.start_date, absence.end_date, exclude_id=absence.id
    )
    absence.version += 1
    absence.full_clean()
    absence.save(update_fields=(*EDITABLE_FIELDS, "version", "updated_at"))
    AbsenceRequestAuditEvent.objects.create(
        absence_request=absence,
        action=AbsenceRequestAuditEvent.Action.UPDATED,
        version=absence.version,
        actor=actor,
        changes={"changed_fields": sorted(validated_data)},
    )
    return absence


@transaction.atomic
def review_absence(absence_id, decision, decision_note, actor):
    absence = AbsenceRequest.objects.select_for_update().select_related("employee").get(
        pk=absence_id
    )
    if absence.status != AbsenceRequest.Status.REQUESTED:
        raise ValueError("Nur beantragte Abwesenheiten können entschieden werden.")
    if decision == AbsenceRequest.Status.APPROVED and absence.kind == AbsenceRequest.Kind.VACATION:
        if absence.start_date.year != absence.end_date.year:
            raise ValueError("Urlaubsanträge müssen innerhalb eines Kalenderjahres liegen.")
        balance = leave_balance(absence.employee, absence.start_date.year)
        if absence.working_days > balance["remaining_days"]:
            raise ValueError("Der verfügbare Resturlaub reicht für diesen Antrag nicht aus.")
    absence.status = decision
    absence.decision_note = decision_note
    absence.reviewed_by = actor
    absence.reviewed_at = timezone.now()
    absence.version += 1
    absence.save(
        update_fields=(
            "status", "decision_note", "reviewed_by", "reviewed_at", "version", "updated_at",
        )
    )
    AbsenceRequestAuditEvent.objects.create(
        absence_request=absence,
        action=decision,
        version=absence.version,
        actor=actor,
        changes={"decision_note": decision_note},
    )
    return absence


@transaction.atomic
def cancel_absence(absence_id, actor, is_admin=False):
    absence = AbsenceRequest.objects.select_for_update().get(pk=absence_id)
    allowed = {AbsenceRequest.Status.REQUESTED}
    if is_admin:
        allowed.add(AbsenceRequest.Status.APPROVED)
    if absence.status not in allowed:
        raise ValueError("Diese Abwesenheit kann nicht storniert werden.")
    absence.status = AbsenceRequest.Status.CANCELLED
    absence.version += 1
    absence.save(update_fields=("status", "version", "updated_at"))
    AbsenceRequestAuditEvent.objects.create(
        absence_request=absence,
        action=AbsenceRequestAuditEvent.Action.CANCELLED,
        version=absence.version,
        actor=actor,
        changes={},
    )
    return absence


@transaction.atomic
def set_leave_entitlement(employee, year, entitlement_days, carryover_days, actor, version=None):
    entitlement = LeaveEntitlement.objects.select_for_update().filter(
        employee=employee, year=year
    ).first()
    if entitlement:
        if version is None or entitlement.version != version:
            raise VersionConflict
        entitlement.entitlement_days = entitlement_days
        entitlement.carryover_days = carryover_days
        entitlement.version += 1
        entitlement.updated_by = actor
        entitlement.full_clean()
        entitlement.save()
        return entitlement
    entitlement = LeaveEntitlement(
        employee=employee,
        year=year,
        entitlement_days=entitlement_days,
        carryover_days=carryover_days,
        updated_by=actor,
    )
    entitlement.full_clean()
    entitlement.save()
    return entitlement
