from django.contrib import admin

from .models import (
    Project, ProjectAuditEvent, ProjectNumberSequence, WorkPackage, WorkPackageAuditEvent,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("project_number", "name", "customer", "status", "start_date", "end_date", "archived_at")
    list_filter = ("status", "archived_at")
    search_fields = ("project_number", "name", "customer__customer_number", "customer__company_name")


admin.site.register(ProjectNumberSequence)
admin.site.register(ProjectAuditEvent)
admin.site.register(WorkPackage)
admin.site.register(WorkPackageAuditEvent)
