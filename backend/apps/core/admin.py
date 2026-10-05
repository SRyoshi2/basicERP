from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class BasicERPUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("basicERP", {"fields": ("must_change_password",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("basicERP", {"fields": ("email", "must_change_password")}),)
    list_display = ("username", "email", "is_staff", "must_change_password", "is_active")
