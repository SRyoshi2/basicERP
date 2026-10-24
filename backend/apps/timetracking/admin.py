from django.contrib import admin

from .models import ServiceEntry, ServiceEntryAuditEvent, TimeEntry, TimeEntryAuditEvent


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = (
        "work_date", "employee", "project", "work_package", "duration_minutes", "billable",
        "billing_status", "archived_at",
    )
    list_filter = ("billable", "billing_status", "work_date", "archived_at")
    search_fields = (
        "description", "employee__username", "project__project_number", "project__name",
        "work_package__title",
    )


admin.site.register(TimeEntryAuditEvent)


@admin.register(ServiceEntry)
class ServiceEntryAdmin(admin.ModelAdmin):
    list_display = (
        "service_date", "employee", "project", "catalog_item_name_snapshot", "quantity",
        "unit_price_snapshot", "billable", "billing_status", "archived_at",
    )
    list_filter = ("billable", "billing_status", "service_date", "archived_at")
    search_fields = (
        "description", "employee__username", "project__project_number", "project__name",
        "catalog_item_number_snapshot", "catalog_item_name_snapshot",
    )


admin.site.register(ServiceEntryAuditEvent)
