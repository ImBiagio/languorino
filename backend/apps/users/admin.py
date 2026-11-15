from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "display_name", "is_active", "cornhub_sub", "is_staff"]
    # Nome, email e password stanno su cornhub (ADR 0021): qui solo da leggere.
    readonly_fields = ["cornhub_sub"]
    search_fields = ["email", "display_name"]
    fieldsets = (
        (None, {"fields": ("email", "cornhub_sub")}),
        ("Profilo", {"fields": ("display_name", "handle", "avatar", "email_verified_at",
                                "language")}),
        ("Permessi", {"fields": ("is_active", "is_staff", "is_superuser", "groups",
                                 "user_permissions")}),
        ("Date", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
