from django.contrib import admin

from .models import AbsenceRequest, AbsenceRequestAuditEvent, LeaveEntitlement


@admin.register(AbsenceRequest)
class AbsenceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "employee", "kind", "start_date", "end_date", "status", "reviewed_by",
    )
    list_filter = ("kind", "status", "start_date")
    search_fields = ("employee__username", "employee__email", "note", "decision_note")


admin.site.register(LeaveEntitlement)
admin.site.register(AbsenceRequestAuditEvent)
