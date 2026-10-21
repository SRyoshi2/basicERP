from django.db import transaction
from django.utils import timezone

from apps.core.errors import VersionConflict

from .models import (
    Project, ProjectAuditEvent, ProjectNumberSequence, WorkPackage, WorkPackageAuditEvent,
)


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


WORK_PACKAGE_FIELDS = (
    "project", "title", "description", "status", "planned_hours", "assignee",
    "hourly_rate_override",
)


@transaction.atomic
def create_work_package(validated_data, actor):
    work_package = WorkPackage(created_by=actor, updated_by=actor, **validated_data)
    work_package.full_clean()
    work_package.save()
    WorkPackageAuditEvent.objects.create(
        work_package=work_package,
        action=WorkPackageAuditEvent.Action.CREATED,
        version=work_package.version,
        actor=actor,
        changes={"status": work_package.status},
    )
    return work_package


@transaction.atomic
def update_work_package(work_package_id, validated_data, actor):
    expected_version = validated_data.pop("version")
    work_package = WorkPackage.objects.select_for_update().select_related("project").get(
        pk=work_package_id
    )
    if work_package.version != expected_version:
        raise VersionConflict
    changed_fields = []
    for field in WORK_PACKAGE_FIELDS:
        if field in validated_data and getattr(work_package, field) != validated_data[field]:
            setattr(work_package, field, validated_data[field])
            changed_fields.append(field)
    work_package.version += 1
    work_package.updated_by = actor
    work_package.full_clean()
    work_package.save(
        update_fields=(*WORK_PACKAGE_FIELDS, "version", "updated_by", "updated_at")
    )
    WorkPackageAuditEvent.objects.create(
        work_package=work_package,
        action=WorkPackageAuditEvent.Action.UPDATED,
        version=work_package.version,
        actor=actor,
        changes={"changed_fields": sorted(changed_fields)},
    )
    return work_package


@transaction.atomic
def archive_work_package(work_package_id, actor):
    work_package = WorkPackage.objects.select_for_update().get(pk=work_package_id)
    if work_package.archived_at is None:
        work_package.archived_at = timezone.now()
        work_package.version += 1
        work_package.updated_by = actor
        work_package.save(update_fields=("archived_at", "version", "updated_by", "updated_at"))
        WorkPackageAuditEvent.objects.create(
            work_package=work_package,
            action=WorkPackageAuditEvent.Action.ARCHIVED,
            version=work_package.version,
            actor=actor,
            changes={},
        )
    return work_package


def project_plan_controlling(project):
    packages = list(project.work_packages.filter(archived_at__isnull=True))
    planned_hours = sum((item.planned_hours for item in packages), start=0)
    priced_values = [item.planned_value for item in packages if item.planned_value is not None]
    planned_value = sum(priced_values, start=0)
    unpriced_count = sum(1 for item in packages if item.planned_value is None)
    done_hours = sum(
        (item.planned_hours for item in packages if item.status == WorkPackage.Status.DONE), start=0
    )
    if planned_hours:
        progress_percent = done_hours * 100 / planned_hours
    elif packages:
        progress_percent = sum(item.status == WorkPackage.Status.DONE for item in packages) * 100 / len(packages)
    else:
        progress_percent = 0
    return {
        "work_package_count": len(packages),
        "planned_hours": planned_hours,
        "planned_value": planned_value,
        "unpriced_work_package_count": unpriced_count,
        "remaining_hours": None if project.budget_hours is None else project.budget_hours - planned_hours,
        "remaining_amount": None if project.budget_amount is None else project.budget_amount - planned_value,
        "progress_percent": progress_percent,
    }
