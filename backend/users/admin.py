from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


# Admin de usuarios: extiende UserAdmin de Django con los campos propios (rol y area).
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "area", "position", "is_active")
    list_filter = ("role", "area", "position", "is_active")
    fieldsets = UserAdmin.fieldsets + ((_("Clinic"), {"fields": ("role", "area")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        (_("Clinic"), {"fields": ("email", "first_name", "last_name", "role", "area", "position")}),
    )
