import hashlib
import logging
from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.archive.models import ArchiveObject

from .models import (
    BusinessDocument, BusinessDocumentAuditEvent, DocumentArtifact,
    DocumentOutboxEvent, DocumentSnapshot,
)
from .rendering import RENDERER_VERSION, TEMPLATE_VERSION, render_invoice_pdf


logger = logging.getLogger(__name__)
CLAIM_TIMEOUT = timedelta(minutes=15)


def pending_artifact_event_ids(limit=20):
    now = timezone.now()
    stale_before = now - CLAIM_TIMEOUT
    stale = DocumentOutboxEvent.objects.filter(
        topic="document.artifact.requested",
        status=DocumentOutboxEvent.Status.PROCESSING,
    ).filter(Q(claimed_at__lt=stale_before) | Q(claimed_at__isnull=True))
    stale.update(
        status=DocumentOutboxEvent.Status.FAILED,
        available_at=now,
        last_error="Vorherige Verarbeitung wurde unterbrochen und erneut eingeplant.",
    )
    return list(
        DocumentOutboxEvent.objects.filter(
            topic="document.artifact.requested",
            status__in=(
                DocumentOutboxEvent.Status.PENDING,
                DocumentOutboxEvent.Status.FAILED,
            ),
            available_at__lte=now,
        ).order_by("available_at").values_list("id", flat=True)[:limit]
    )


@transaction.atomic
def reserve_artifact_event(event_id):
    event = DocumentOutboxEvent.objects.select_for_update().get(pk=event_id)
    if event.status == DocumentOutboxEvent.Status.COMPLETED:
        return None
    now = timezone.now()
    if (
        event.status == DocumentOutboxEvent.Status.PROCESSING
        and event.claimed_at
        and event.claimed_at >= now - CLAIM_TIMEOUT
    ):
        return None
    event.status = DocumentOutboxEvent.Status.PROCESSING
    event.claimed_at = now
    event.attempts += 1
    event.last_error = ""
    event.save(update_fields=("status", "claimed_at", "attempts", "last_error"))
    return str(event.payload["snapshot_id"])


def _archive_pdf(pdf_bytes, snapshot):
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    existing = ArchiveObject.objects.filter(sha256=digest).first()
    if existing:
        return existing
    archive = ArchiveObject(
        sha256=digest,
        original_name=f"{snapshot.payload['document_number']}.pdf",
        mime_type="application/pdf",
        size=len(pdf_bytes),
        source=ArchiveObject.Source.OUTGOING_INVOICE,
        created_by=snapshot.created_by,
    )
    archive.file.save(digest, ContentFile(pdf_bytes), save=False)
    archive.save()
    return archive


@transaction.atomic
def complete_artifact_event(event_id, snapshot_id, pdf_bytes):
    event = DocumentOutboxEvent.objects.select_for_update().get(pk=event_id)
    snapshot = DocumentSnapshot.objects.select_related("document", "created_by").get(
        pk=snapshot_id
    )
    document = BusinessDocument.objects.select_for_update().get(pk=snapshot.document_id)
    artifact = DocumentArtifact.objects.filter(snapshot=snapshot).first()
    if artifact is None:
        archive = _archive_pdf(pdf_bytes, snapshot)
        artifact = DocumentArtifact.objects.create(
            document=document,
            snapshot=snapshot,
            archive_object=archive,
            renderer_version=RENDERER_VERSION,
            template_version=TEMPLATE_VERSION,
        )
        BusinessDocumentAuditEvent.objects.create(
            document=document,
            action=BusinessDocumentAuditEvent.Action.ARTIFACT_CREATED,
            version=document.version,
            actor=snapshot.created_by,
            changes={
                "artifact_id": str(artifact.id),
                "pdf_sha256": archive.sha256,
                "renderer_version": RENDERER_VERSION,
                "template_version": TEMPLATE_VERSION,
            },
        )
    document.status = BusinessDocument.Status.FINALIZED
    document.save(update_fields=("status", "updated_at"))
    event.status = DocumentOutboxEvent.Status.COMPLETED
    event.processed_at = timezone.now()
    event.last_error = ""
    event.save(update_fields=("status", "processed_at", "last_error"))
    return artifact


@transaction.atomic
def fail_artifact_event(event_id, error):
    event = DocumentOutboxEvent.objects.select_for_update().select_related(
        "document"
    ).get(pk=event_id)
    message = str(error)[:2000]
    delay = min(30 * (2 ** max(event.attempts - 1, 0)), 30 * 60)
    event.status = DocumentOutboxEvent.Status.FAILED
    event.available_at = timezone.now() + timedelta(seconds=delay)
    event.last_error = message
    event.save(update_fields=("status", "available_at", "last_error"))
    document = event.document
    document.status = BusinessDocument.Status.ARTIFACT_FAILED
    document.save(update_fields=("status", "updated_at"))
    snapshot = DocumentSnapshot.objects.get(document=document)
    BusinessDocumentAuditEvent.objects.create(
        document=document,
        action=BusinessDocumentAuditEvent.Action.ARTIFACT_FAILED,
        version=document.version,
        actor=snapshot.created_by,
        changes={"attempt": event.attempts, "error": message},
    )
    logger.exception("PDF-Erzeugung für Dokument %s fehlgeschlagen", document.id)


def process_artifact_event(event_id):
    snapshot_id = reserve_artifact_event(event_id)
    if snapshot_id is None:
        return None
    try:
        snapshot = DocumentSnapshot.objects.get(pk=snapshot_id)
        pdf_bytes = render_invoice_pdf(snapshot)
        return complete_artifact_event(event_id, snapshot_id, pdf_bytes)
    except Exception as error:
        fail_artifact_event(event_id, error)
        return None


@transaction.atomic
def postpone_dispatched_events(event_ids):
    if not event_ids:
        return
    DocumentOutboxEvent.objects.filter(
        id__in=event_ids,
        status__in=(DocumentOutboxEvent.Status.PENDING, DocumentOutboxEvent.Status.FAILED),
    ).filter(Q(available_at__lte=timezone.now())).update(
        available_at=timezone.now() + timedelta(seconds=60)
    )
