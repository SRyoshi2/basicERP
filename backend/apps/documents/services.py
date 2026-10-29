import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.core.errors import VersionConflict
from apps.core.models import CompanyProfile
from apps.crm.models import Address
from apps.timetracking.models import (
    ServiceEntry, ServiceEntryAuditEvent, TimeEntry, TimeEntryAuditEvent,
)

from .models import (
    BusinessDocument, BusinessDocumentAuditEvent, DocumentLine,
    DocumentNumberSequence, DocumentOutboxEvent, DocumentSnapshot,
)


DOCUMENT_FIELDS = (
    "kind", "customer", "project", "issue_date", "service_date_from", "service_date_to",
    "due_date", "tax_mode", "tax_exemption_note", "introduction", "closing_text",
    "payment_terms",
)

SNAPSHOT_SCHEMA_VERSION = 1
CALCULATION_VERSION = 1


def _source_line_values(document, line_data):
    time_entry = line_data.get("source_time_entry")
    service_entry = line_data.get("source_service_entry")
    if not time_entry and not service_entry:
        return line_data
    if time_entry and service_entry:
        raise ValidationError("Eine Position darf nur eine Projektquelle besitzen.")
    source = time_entry or service_entry
    if document.project_id is None or source.project_id != document.project_id:
        raise ValidationError("Die Projektleistung gehört nicht zum gewählten Projekt.")
    if source.archived_at is not None or not source.billable:
        raise ValidationError("Nur aktive, abrechenbare Projektleistungen können übernommen werden.")
    if source.billing_status != source.BillingStatus.UNBILLED:
        raise ValidationError("Die Projektleistung wurde bereits abgerechnet.")

    description = line_data.get("description", "").strip()
    tax_rate = Decimal("0") if document.tax_mode == BusinessDocument.TaxMode.SMALL_BUSINESS else None
    tax_note = document.tax_exemption_note if tax_rate == 0 else ""
    if time_entry:
        if time_entry.hourly_rate_snapshot is None:
            raise ValidationError("Für den Zeiteintrag fehlt ein abrechenbarer Stundensatz.")
        return {
            "catalog_item": None,
            "source_time_entry": time_entry,
            "source_service_entry": None,
            "description": description or time_entry.description,
            "quantity": time_entry.duration_hours.quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            ),
            "unit": DocumentLine.Unit.HOUR,
            "unit_price_net": time_entry.hourly_rate_snapshot,
            "discount_percent": Decimal("0"),
            "tax_rate": tax_rate if tax_rate is not None else Decimal("19"),
            "tax_note": tax_note,
        }
    return {
        "catalog_item": service_entry.catalog_item,
        "source_time_entry": None,
        "source_service_entry": service_entry,
        "description": description or service_entry.description
        or service_entry.catalog_item_name_snapshot,
        "quantity": service_entry.quantity,
        "unit": service_entry.unit_snapshot,
        "unit_price_net": service_entry.unit_price_snapshot,
        "discount_percent": Decimal("0"),
        "tax_rate": tax_rate if tax_rate is not None else service_entry.tax_rate_snapshot,
        "tax_note": tax_note or service_entry.catalog_item.tax_note,
    }


def _replace_lines(document, lines):
    time_ids = [line["source_time_entry"].id for line in lines if line.get("source_time_entry")]
    service_ids = [
        line["source_service_entry"].id for line in lines if line.get("source_service_entry")
    ]
    if len(time_ids) != len(set(time_ids)) or len(service_ids) != len(set(service_ids)):
        raise ValidationError("Eine Projektleistung darf nur einmal übernommen werden.")
    locked_time = {
        item.id: item
        for item in TimeEntry.objects.select_for_update().filter(id__in=time_ids)
    }
    locked_service = {
        item.id: item
        for item in ServiceEntry.objects.select_for_update().select_related(
            "catalog_item"
        ).filter(id__in=service_ids)
    }
    if len(locked_time) != len(time_ids) or len(locked_service) != len(service_ids):
        raise ValidationError("Mindestens eine Projektleistung fehlt.")
    reserved_time = DocumentLine.objects.filter(source_time_entry_id__in=time_ids).exclude(
        document=document
    ).exists()
    reserved_service = DocumentLine.objects.filter(
        source_service_entry_id__in=service_ids
    ).exclude(document=document).exists()
    if reserved_time or reserved_service:
        raise ValidationError("Mindestens eine Projektleistung ist bereits einem Beleg zugeordnet.")
    document.lines.all().delete()
    instances = []
    for position, line_data in enumerate(lines, start=1):
        line_data = dict(line_data)
        if line_data.get("source_time_entry"):
            line_data["source_time_entry"] = locked_time[line_data["source_time_entry"].id]
        if line_data.get("source_service_entry"):
            line_data["source_service_entry"] = locked_service[
                line_data["source_service_entry"].id
            ]
        line = DocumentLine(
            document=document,
            position=position,
            **_source_line_values(document, line_data),
        )
        line.full_clean()
        instances.append(line)
    try:
        with transaction.atomic():
            DocumentLine.objects.bulk_create(instances)
    except IntegrityError as error:
        raise ValidationError(
            "Mindestens eine Projektleistung wurde parallel einem anderen Beleg zugeordnet."
        ) from error


def _decimal_string(value):
    return format(value, "f")


def _number_sequence(kind, year):
    try:
        with transaction.atomic():
            DocumentNumberSequence.objects.get_or_create(
                kind=kind,
                year=year,
                defaults={"prefix": "RE" if kind == BusinessDocument.Kind.INVOICE else "AN"},
            )
    except IntegrityError:
        # A parallel transaction created the same year/kind row first.
        pass
    return DocumentNumberSequence.objects.select_for_update().get(kind=kind, year=year)


def _next_document_number(document):
    sequence = _number_sequence(document.kind, document.issue_date.year)
    value = sequence.next_value
    sequence.next_value += 1
    sequence.save(update_fields=("next_value",))
    return f"{sequence.prefix}-{sequence.year}-{value:04d}"


def _billing_address(customer):
    return customer.addresses.filter(kind=Address.Kind.BILLING).order_by(
        "-is_default", "label", "id"
    ).first()


def _finalization_context(document):
    company, _ = CompanyProfile.objects.get_or_create(pk=1)
    address = _billing_address(document.customer)
    errors = {}
    if document.kind != BusinessDocument.Kind.INVOICE:
        errors["kind"] = "In diesem Schritt können nur Rechnungen festgeschrieben werden."
    if document.status != BusinessDocument.Status.DRAFT or document.archived_at is not None:
        errors["status"] = "Nur aktive Rechnungsentwürfe können festgeschrieben werden."
    if not (company.legal_name.strip() or company.name.strip()):
        errors["company_name"] = "Im Firmenprofil fehlt der vollständige Unternehmensname."
    if not all((company.street.strip(), company.postal_code.strip(), company.city.strip())):
        errors["company_address"] = "Im Firmenprofil fehlt die vollständige Anschrift."
    if not (company.tax_number.strip() or company.vat_id.strip()):
        errors["company_tax_id"] = "Im Firmenprofil fehlt Steuernummer oder USt-IdNr."
    if address is None:
        errors["customer_address"] = "Der Kunde benötigt eine Rechnungsadresse."
    if not document.service_date_from:
        errors["service_date_from"] = "Für die Rechnung ist ein Leistungsdatum erforderlich."
    if not document.lines.exists():
        errors["lines"] = "Die Rechnung benötigt mindestens eine Position."
    if errors:
        raise ValidationError(errors)
    return company, address


def _snapshot_payload(document, company, address, number, finalized_at):
    totals = document.totals
    lines = []
    for line in document.lines.select_related("catalog_item"):
        lines.append({
            "position": line.position,
            "catalog_item_id": str(line.catalog_item_id) if line.catalog_item_id else None,
            "catalog_item_number": line.catalog_item.item_number if line.catalog_item_id else None,
            "source_time_entry_id": (
                str(line.source_time_entry_id) if line.source_time_entry_id else None
            ),
            "source_service_entry_id": (
                str(line.source_service_entry_id) if line.source_service_entry_id else None
            ),
            "description": line.description,
            "quantity": _decimal_string(line.quantity),
            "unit": line.unit,
            "unit_label": line.get_unit_display(),
            "unit_price_net": _decimal_string(line.unit_price_net),
            "discount_percent": _decimal_string(line.discount_percent),
            "tax_rate": _decimal_string(line.tax_rate),
            "tax_note": line.tax_note,
            "net_amount": _decimal_string(line.net_amount),
        })
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "document_id": str(document.id),
        "document_number": number,
        "kind": document.kind,
        "currency": document.currency,
        "issue_date": document.issue_date.isoformat(),
        "service_date_from": document.service_date_from.isoformat(),
        "service_date_to": (
            document.service_date_to.isoformat() if document.service_date_to else None
        ),
        "due_date": document.due_date.isoformat() if document.due_date else None,
        "tax_mode": document.tax_mode,
        "tax_exemption_note": document.tax_exemption_note,
        "introduction": document.introduction,
        "closing_text": document.closing_text,
        "payment_terms": document.payment_terms,
        "finalized_at": finalized_at.isoformat(),
        "issuer": {
            "name": company.legal_name.strip() or company.name.strip(),
            "street": company.street,
            "postal_code": company.postal_code,
            "city": company.city,
            "country_code": company.country_code,
            "tax_number": company.tax_number,
            "vat_id": company.vat_id,
            "email": company.email,
            "phone": company.phone,
            "website": company.website,
        },
        "recipient": {
            "customer_id": str(document.customer_id),
            "customer_number": document.customer.customer_number,
            "name": document.customer.display_name,
            "street": address.street,
            "postal_code": address.postal_code,
            "city": address.city,
            "country_code": address.country_code,
            "vat_id": document.customer.vat_id,
            "leitweg_id": document.customer.leitweg_id,
        },
        "project": ({
            "id": str(document.project_id),
            "number": document.project.project_number,
            "name": document.project.name,
        } if document.project_id else None),
        "lines": lines,
        "totals": {
            "net_total": _decimal_string(totals["net_total"]),
            "tax_total": _decimal_string(totals["tax_total"]),
            "gross_total": _decimal_string(totals["gross_total"]),
            "tax_breakdown": [
                {key: _decimal_string(value) for key, value in group.items()}
                for group in totals["tax_breakdown"]
            ],
        },
    }


def _snapshot_hash(payload):
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@transaction.atomic
def create_document(validated_data, actor):
    lines = validated_data.pop("lines")
    document = BusinessDocument(created_by=actor, updated_by=actor, **validated_data)
    document.full_clean()
    document.save()
    _replace_lines(document, lines)
    BusinessDocumentAuditEvent.objects.create(
        document=document,
        action=BusinessDocumentAuditEvent.Action.CREATED,
        version=document.version,
        actor=actor,
        changes={"kind": document.kind, "line_count": len(lines)},
    )
    return document


@transaction.atomic
def update_document(document_id, validated_data, actor):
    expected_version = validated_data.pop("version")
    lines = validated_data.pop("lines")
    # Do not select_related the nullable project here: PostgreSQL rejects
    # FOR UPDATE on the nullable side of the resulting outer join.
    document = BusinessDocument.objects.select_for_update().get(pk=document_id)
    if document.version != expected_version:
        raise VersionConflict
    if document.status != BusinessDocument.Status.DRAFT or document.archived_at is not None:
        raise ValueError("Nur aktive Entwürfe können geändert werden.")
    changed_fields = []
    for field in DOCUMENT_FIELDS:
        if field in validated_data and getattr(document, field) != validated_data[field]:
            setattr(document, field, validated_data[field])
            changed_fields.append(field)
    document.version += 1
    document.updated_by = actor
    document.full_clean()
    document.save(update_fields=(*DOCUMENT_FIELDS, "version", "updated_by", "updated_at"))
    _replace_lines(document, lines)
    BusinessDocumentAuditEvent.objects.create(
        document=document,
        action=BusinessDocumentAuditEvent.Action.UPDATED,
        version=document.version,
        actor=actor,
        changes={"changed_fields": sorted(set((*changed_fields, "lines")))},
    )
    return document


@transaction.atomic
def archive_document(document_id, actor):
    document = BusinessDocument.objects.select_for_update().get(pk=document_id)
    if document.status != BusinessDocument.Status.DRAFT:
        raise ValueError("Nur Entwürfe können archiviert werden.")
    if document.archived_at is None:
        document.archived_at = timezone.now()
        document.version += 1
        document.updated_by = actor
        document.save(update_fields=("archived_at", "version", "updated_by", "updated_at"))
        document.lines.update(source_time_entry=None, source_service_entry=None)
        BusinessDocumentAuditEvent.objects.create(
            document=document,
            action=BusinessDocumentAuditEvent.Action.ARCHIVED,
            version=document.version,
            actor=actor,
            changes={},
        )
    return document


def _mark_sources_billed(document, actor):
    lines = list(document.lines.select_related(
        "source_time_entry", "source_service_entry"
    ))
    time_ids = [line.source_time_entry_id for line in lines if line.source_time_entry_id]
    service_ids = [
        line.source_service_entry_id for line in lines if line.source_service_entry_id
    ]
    time_entries = {
        item.id: item for item in TimeEntry.objects.select_for_update().filter(id__in=time_ids)
    }
    service_entries = {
        item.id: item
        for item in ServiceEntry.objects.select_for_update().filter(id__in=service_ids)
    }
    if len(time_entries) != len(time_ids) or len(service_entries) != len(service_ids):
        raise ValidationError("Mindestens eine übernommene Projektleistung fehlt.")
    for source in (*time_entries.values(), *service_entries.values()):
        if (
            source.project_id != document.project_id
            or not source.billable
            or source.archived_at is not None
            or source.billing_status != source.BillingStatus.UNBILLED
        ):
            raise ValidationError(
                "Mindestens eine übernommene Projektleistung ist nicht mehr abrechenbar."
            )
        source.billing_status = source.BillingStatus.BILLED
        source.version += 1
        source.updated_by = actor
        source.save(update_fields=("billing_status", "version", "updated_by", "updated_at"))
        changes = {
            "document_id": str(document.id),
            "document_number": document.document_number,
        }
        if isinstance(source, TimeEntry):
            TimeEntryAuditEvent.objects.create(
                time_entry=source, action=TimeEntryAuditEvent.Action.BILLED,
                version=source.version, actor=actor, changes=changes,
            )
        else:
            ServiceEntryAuditEvent.objects.create(
                service_entry=source, action=ServiceEntryAuditEvent.Action.BILLED,
                version=source.version, actor=actor, changes=changes,
            )


def billable_project_items(project_id, document_id=None):
    own_time_ids = []
    own_service_ids = []
    if document_id:
        own_time_ids = DocumentLine.objects.filter(document_id=document_id).exclude(
            source_time_entry=None
        ).values_list("source_time_entry_id", flat=True)
        own_service_ids = DocumentLine.objects.filter(document_id=document_id).exclude(
            source_service_entry=None
        ).values_list("source_service_entry_id", flat=True)
    time_entries = TimeEntry.objects.filter(
        project_id=project_id, archived_at__isnull=True, billable=True,
        billing_status=TimeEntry.BillingStatus.UNBILLED,
        hourly_rate_snapshot__isnull=False,
    ).filter(
        models.Q(document_line__isnull=True) | models.Q(id__in=own_time_ids)
    ).select_related("employee", "work_package").order_by("work_date", "created_at")
    service_entries = ServiceEntry.objects.filter(
        project_id=project_id, archived_at__isnull=True, billable=True,
        billing_status=ServiceEntry.BillingStatus.UNBILLED,
    ).filter(
        models.Q(document_line__isnull=True) | models.Q(id__in=own_service_ids)
    ).select_related("employee", "work_package", "catalog_item").order_by(
        "service_date", "created_at"
    )
    items = []
    for entry in time_entries:
        items.append({
            "id": entry.id, "source_type": "time", "date": entry.work_date,
            "description": entry.description, "quantity": entry.duration_hours,
            "unit": DocumentLine.Unit.HOUR, "unit_label": "Stunde",
            "unit_price_net": entry.hourly_rate_snapshot, "tax_rate": Decimal("19"),
            "net_amount": entry.billable_value, "employee": entry.employee.get_full_name()
            or entry.employee.username, "work_package": entry.work_package.title,
        })
    for entry in service_entries:
        items.append({
            "id": entry.id, "source_type": "service", "date": entry.service_date,
            "description": entry.description or entry.catalog_item_name_snapshot,
            "quantity": entry.quantity, "unit": entry.unit_snapshot,
            "unit_label": DocumentLine.Unit(entry.unit_snapshot).label,
            "unit_price_net": entry.unit_price_snapshot,
            "tax_rate": entry.tax_rate_snapshot, "net_amount": entry.total_net,
            "employee": entry.employee.get_full_name() or entry.employee.username,
            "work_package": entry.work_package.title,
            "catalog_item": entry.catalog_item_id,
            "tax_note": entry.catalog_item.tax_note,
        })
    return sorted(items, key=lambda item: (item["date"], item["source_type"], str(item["id"])))


@transaction.atomic
def finalize_document(document_id, expected_version, actor):
    document = BusinessDocument.objects.select_for_update().select_related(
        "customer"
    ).get(pk=document_id)
    if document.version != expected_version:
        raise VersionConflict
    company, address = _finalization_context(document)
    finalized_at = timezone.now()
    number = _next_document_number(document)
    payload = _snapshot_payload(document, company, address, number, finalized_at)
    snapshot = DocumentSnapshot.objects.create(
        document=document,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        calculation_version=CALCULATION_VERSION,
        payload=payload,
        sha256=_snapshot_hash(payload),
        created_by=actor,
    )
    document.document_number = number
    document.status = BusinessDocument.Status.FINALIZING
    document.finalized_at = finalized_at
    document.finalized_by = actor
    document.updated_by = actor
    _mark_sources_billed(document, actor)
    document.version += 1
    document.save(update_fields=(
        "document_number", "status", "finalized_at", "finalized_by", "updated_by",
        "version", "updated_at",
    ))
    BusinessDocumentAuditEvent.objects.create(
        document=document,
        action=BusinessDocumentAuditEvent.Action.FINALIZED,
        version=document.version,
        actor=actor,
        changes={"document_number": number, "snapshot_sha256": snapshot.sha256},
    )
    DocumentOutboxEvent.objects.create(
        document=document,
        topic="document.artifact.requested",
        event_key=f"document.artifact.requested:{document.id}:v{snapshot.schema_version}",
        payload={
            "document_id": str(document.id),
            "snapshot_id": str(snapshot.id),
            "snapshot_sha256": snapshot.sha256,
        },
        available_at=finalized_at,
    )
    return document
