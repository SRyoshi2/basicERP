from django.contrib import admin

from .models import ArchiveObject, IncomingInvoice


@admin.register(ArchiveObject)
class ArchiveObjectAdmin(admin.ModelAdmin):
    list_display = ("original_name", "sha256", "mime_type", "size", "source", "created_at")
    readonly_fields = (
        "file",
        "sha256",
        "original_name",
        "mime_type",
        "size",
        "source",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IncomingInvoice)
class IncomingInvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "seller_name", "status", "format", "issue_date", "created_at")
    list_filter = ("status", "format")
    search_fields = ("invoice_number", "seller_name", "buyer_name", "archive_object__original_name")
    readonly_fields = (
        "archive_object",
        "format",
        "status",
        "invoice_number",
        "issue_date",
        "seller_name",
        "buyer_name",
        "currency",
        "payable_amount",
        "embedded_xml_sha256",
        "validation_report",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
