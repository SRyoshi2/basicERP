from django.contrib import admin

from .models import CatalogAuditEvent, CatalogItem, CatalogNumberSequence, CatalogPrice


class CatalogPriceInline(admin.TabularInline):
    model = CatalogPrice
    extra = 0


@admin.register(CatalogItem)
class CatalogItemAdmin(admin.ModelAdmin):
    list_display = ("item_number", "name", "kind", "unit", "tax_rate", "archived_at")
    list_filter = ("kind", "unit", "tax_rate", "archived_at")
    search_fields = ("item_number", "name", "description")
    inlines = (CatalogPriceInline,)


admin.site.register(CatalogNumberSequence)
admin.site.register(CatalogAuditEvent)
