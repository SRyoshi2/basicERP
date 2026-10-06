from django.contrib import admin

from .models import Address, Contact, ContactAuditEvent, ContactImportBatch, ContactPerson


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


class ContactPersonInline(admin.TabularInline):
    model = ContactPerson
    extra = 0


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("customer_number", "display_name", "kind", "email", "archived_at")
    search_fields = ("customer_number", "company_name", "first_name", "last_name", "email")
    list_filter = ("kind", "archived_at")
    readonly_fields = ("customer_number", "version", "created_at", "updated_at")
    inlines = (AddressInline, ContactPersonInline)


@admin.register(ContactAuditEvent)
class ContactAuditEventAdmin(admin.ModelAdmin):
    list_display = ("contact", "action", "version", "actor", "created_at")
    readonly_fields = ("contact", "action", "version", "changes", "actor", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContactImportBatch)
class ContactImportBatchAdmin(admin.ModelAdmin):
    list_display = ("source_name", "status", "total_count", "error_count", "created_count", "created_at")
    readonly_fields = (
        "source_name",
        "source_hash",
        "status",
        "rows",
        "total_count",
        "valid_count",
        "error_count",
        "created_count",
        "result",
        "created_by",
        "created_at",
        "completed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
