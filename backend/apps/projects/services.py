from django.db import transaction
from django.utils import timezone

from apps.core.errors import VersionConflict

from .models import Project, ProjectAuditEvent, ProjectNumberSequence


PROJECT_FIELDS = (
    "customer", "name", "description", "status", "start_date", "end_date",
    "budget_amount", "budget_hours", "default_hourly_rate",
)


@transaction.atomic
def create_project(validated_data, actor):
    sequence = ProjectNumberSequence.objects.select_for_update().get(pk=1)
    project_number = f"P-{sequence.next_value:05d}"
    sequence.next_value += 1
    sequence.save(update_fields=("next_value",))
    project = Project(
        project_number=project_number, created_by=actor, updated_by=actor, **validated_data
    )
    project.full_clean()
    project.save()
    ProjectAuditEvent.objects.create(
        project=project, action=ProjectAuditEvent.Action.CREATED,
        version=project.version, actor=actor, changes={"status": project.status},
    )
    return project


@transaction.atomic
def update_project(project_id, validated_data, actor):
    expected_version = validated_data.pop("version")
    project = Project.objects.select_for_update().get(pk=project_id)
    if project.version != expected_version:
        raise VersionConflict
    changed_fields = []
    for field in PROJECT_FIELDS:
        if field in validated_data and getattr(project, field) != validated_data[field]:
            setattr(project, field, validated_data[field])
            changed_fields.append(field)
    project.version += 1
    project.updated_by = actor
    project.full_clean()
    project.save(update_fields=(*PROJECT_FIELDS, "version", "updated_by", "updated_at"))
    ProjectAuditEvent.objects.create(
        project=project, action=ProjectAuditEvent.Action.UPDATED,
        version=project.version, actor=actor, changes={"changed_fields": sorted(changed_fields)},
    )
    return project


@transaction.atomic
def archive_project(project_id, actor):
    project = Project.objects.select_for_update().get(pk=project_id)
    if project.archived_at is None:
        project.archived_at = timezone.now()
        project.version += 1
        project.updated_by = actor
        project.save(update_fields=("archived_at", "version", "updated_by", "updated_at"))
        ProjectAuditEvent.objects.create(
            project=project, action=ProjectAuditEvent.Action.ARCHIVED,
            version=project.version, actor=actor, changes={},
        )
    return project
