from celery import shared_task

from .artifacts import (
    pending_artifact_event_ids, postpone_dispatched_events, process_artifact_event,
)


@shared_task(name="apps.documents.tasks.process_document_artifact")
def process_document_artifact(event_id):
    artifact = process_artifact_event(event_id)
    return str(artifact.id) if artifact else None


@shared_task(name="apps.documents.tasks.dispatch_document_outbox")
def dispatch_document_outbox():
    event_ids = pending_artifact_event_ids()
    postpone_dispatched_events(event_ids)
    for event_id in event_ids:
        process_document_artifact.delay(str(event_id))
    return len(event_ids)
