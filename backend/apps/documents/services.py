import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.errors import VersionConflict
from apps.core.models import CompanyProfile
from apps.crm.models import Address

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


def _replace_lines(document, lines):
    document.lines.all().delete()
    instances = []
    for position, line_data in enumerate(lines, start=1):
        line = DocumentLine(document=document, position=position, **line_data)
        line.full_clean()
        instances.append(line)
    DocumentLine.objects.bulk_create(instances)


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
        BusinessDocumentAuditEvent.objects.create(
            document=document,
            action=BusinessDocumentAuditEvent.Action.ARCHIVED,
            version=document.version,
            actor=actor,
            changes={},
        )
    return document


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
