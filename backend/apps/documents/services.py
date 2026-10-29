from django.db import transaction
from django.utils import timezone

from apps.core.errors import VersionConflict

from .models import BusinessDocument, BusinessDocumentAuditEvent, DocumentLine


DOCUMENT_FIELDS = (
    "kind", "customer", "project", "issue_date", "service_date_from", "service_date_to",
    "due_date", "tax_mode", "tax_exemption_note", "introduction", "closing_text",
    "payment_terms",
)


def _replace_lines(document, lines):
    document.lines.all().delete()
    instances = []
    for position, line_data in enumerate(lines, start=1):
        line = DocumentLine(document=document, position=position, **line_data)
        line.full_clean()
        instances.append(line)
    DocumentLine.objects.bulk_create(instances)


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
