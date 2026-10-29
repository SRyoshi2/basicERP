from django.contrib import admin

from .models import BusinessDocument, BusinessDocumentAuditEvent, DocumentLine


class DocumentLineInline(admin.TabularInline):
    model = DocumentLine
    extra = 0


@admin.register(BusinessDocument)
class BusinessDocumentAdmin(admin.ModelAdmin):
    list_display = ("kind", "status", "customer", "issue_date", "version", "archived_at")
    list_filter = ("kind", "status", "tax_mode")
    search_fields = ("customer__company_name", "customer__last_name", "project__name")
    inlines = (DocumentLineInline,)


@admin.register(BusinessDocumentAuditEvent)
class BusinessDocumentAuditEventAdmin(admin.ModelAdmin):
    list_display = ("document", "action", "version", "actor", "created_at")
    readonly_fields = ("document", "action", "version", "changes", "actor", "created_at")
