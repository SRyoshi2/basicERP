from decimal import Decimal

from apps.catalog.models import CatalogItem
from apps.core.models import User

from .models import ServiceEntry, TimeEntry


def build_time_report(user, *, date_from, date_to, project_id=None, employee_id=None):
    time_entries = TimeEntry.objects.filter(
        archived_at__isnull=True, work_date__range=(date_from, date_to)
    ).select_related("employee", "project", "work_package")
    service_entries = ServiceEntry.objects.filter(
        archived_at__isnull=True, service_date__range=(date_from, date_to)
    ).select_related("employee", "project", "work_package")

    if user.role != User.Role.ADMIN:
        time_entries = time_entries.filter(employee=user)
        service_entries = service_entries.filter(employee=user)
    elif employee_id:
        time_entries = time_entries.filter(employee_id=employee_id)
        service_entries = service_entries.filter(employee_id=employee_id)
    if project_id:
        time_entries = time_entries.filter(project_id=project_id)
        service_entries = service_entries.filter(project_id=project_id)

    rows = []
    total_minutes = 0
    billable_minutes = 0
    time_value = Decimal("0")
    service_quantity = Decimal("0")
    service_value = Decimal("0")

    for entry in time_entries:
        employee_name = entry.employee.get_full_name().strip() or entry.employee.username
        value = entry.billable_value
        total_minutes += entry.duration_minutes
        if entry.billable:
            billable_minutes += entry.duration_minutes
            if value is not None:
                time_value += value
        rows.append({
            "entry_type": "time",
            "date": entry.work_date,
            "employee_name": employee_name,
            "project_number": entry.project.project_number,
            "project_name": entry.project.name,
            "work_package_title": entry.work_package.title,
            "description": entry.description,
            "hours": entry.duration_hours,
            "quantity": None,
            "unit": "Stunde",
            "billable": entry.billable,
            "net_value": value,
            "billing_status": entry.get_billing_status_display(),
        })

    for entry in service_entries:
        employee_name = entry.employee.get_full_name().strip() or entry.employee.username
        value = entry.total_net if entry.billable else None
        service_quantity += entry.quantity
        if value is not None:
            service_value += value
        rows.append({
            "entry_type": "service",
            "date": entry.service_date,
            "employee_name": employee_name,
            "project_number": entry.project.project_number,
            "project_name": entry.project.name,
            "work_package_title": entry.work_package.title,
            "description": entry.description or entry.catalog_item_name_snapshot,
            "hours": None,
            "quantity": entry.quantity,
            "unit": dict(CatalogItem.Unit.choices).get(entry.unit_snapshot, entry.unit_snapshot),
            "billable": entry.billable,
            "net_value": value,
            "billing_status": entry.get_billing_status_display(),
        })

    rows.sort(key=lambda row: (row["date"], row["employee_name"], row["project_number"], row["entry_type"]))
    return {
        "date_from": date_from,
        "date_to": date_to,
        "summary": {
            "time_entry_count": len(time_entries),
            "total_hours": Decimal(total_minutes) / Decimal("60"),
            "billable_hours": Decimal(billable_minutes) / Decimal("60"),
            "time_value": time_value,
            "service_entry_count": len(service_entries),
            "service_quantity": service_quantity,
            "service_value": service_value,
            "total_value": time_value + service_value,
        },
        "rows": rows,
    }
