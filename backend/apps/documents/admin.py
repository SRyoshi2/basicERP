from django.contrib import admin

from .models import (
    BusinessDocument, BusinessDocumentAuditEvent, DocumentLine,
    DocumentNumberSequence, DocumentOutboxEvent, DocumentSnapshot,
)


class DocumentLineInline(admin.TabularInline):
    model = DocumentLine
    extra = 0

    def has_change_permission(self, request, obj=None):
        return bool(obj and obj.status == BusinessDocument.Status.DRAFT)

    def has_add_permission(self, request, obj=None):
        return bool(obj and obj.status == BusinessDocument.Status.DRAFT)

    def has_delete_permission(self, request, obj=None):
        return bool(obj and obj.status == BusinessDocument.Status.DRAFT)


@admin.register(BusinessDocument)
class BusinessDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "document_number", "kind", "status", "customer", "issue_date", "version",
        "archived_at",
    )
    list_filter = ("kind", "status", "tax_mode")
    search_fields = ("customer__company_name", "customer__last_name", "project__name")
    inlines = (DocumentLineInline,)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status != BusinessDocument.Status.DRAFT:
            return tuple(field.name for field in obj._meta.fields)
        return ()


@admin.register(BusinessDocumentAuditEvent)
class BusinessDocumentAuditEventAdmin(admin.ModelAdmin):
    list_display = ("document", "action", "version", "actor", "created_at")
    readonly_fields = ("document", "action", "version", "changes", "actor", "created_at")


@admin.register(DocumentSnapshot)
class DocumentSnapshotAdmin(admin.ModelAdmin):
    list_display = ("document", "schema_version", "calculation_version", "sha256", "created_at")
    readonly_fields = (
        "document", "schema_version", "calculation_version", "payload", "sha256",
        "created_by", "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DocumentNumberSequence)
class DocumentNumberSequenceAdmin(admin.ModelAdmin):
    list_display = ("kind", "year", "prefix", "next_value")
    readonly_fields = ("kind", "year", "next_value")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DocumentOutboxEvent)
class DocumentOutboxEventAdmin(admin.ModelAdmin):
    list_display = ("topic", "document", "status", "attempts", "available_at", "created_at")
    readonly_fields = (
        "document", "topic", "event_key", "payload", "status", "attempts",
        "available_at", "processed_at", "last_error", "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
