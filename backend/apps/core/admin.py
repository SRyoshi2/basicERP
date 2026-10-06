from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CompanyProfile, User


@admin.register(User)
class BasicERPUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("basicERP", {"fields": ("role", "must_change_password")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("basicERP", {"fields": ("email", "role", "must_change_password")}),)
    list_display = ("username", "email", "role", "is_staff", "must_change_password", "is_active")


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    readonly_fields = ("updated_at", "updated_by")

    def has_add_permission(self, request):
        return not CompanyProfile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
