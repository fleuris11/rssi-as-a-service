from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import RecoveryCode, TwoFactorCredential, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "is_staff", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations personnelles", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates importantes", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    readonly_fields = ["date_joined"]


@admin.register(TwoFactorCredential)
class TwoFactorCredentialAdmin(admin.ModelAdmin):
    # Never exposes encrypted_secret — the point of encrypting it at rest
    # is defeated if an admin page just prints it back out.
    list_display = ["user", "confirmed", "created_at", "confirmed_at"]
    list_filter = ["confirmed"]
    search_fields = ["user__email"]
    readonly_fields = ["user", "confirmed", "created_at", "confirmed_at"]

    def has_add_permission(self, request):
        return False


@admin.register(RecoveryCode)
class RecoveryCodeAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "used_at"]
    search_fields = ["user__email"]
    readonly_fields = ["user", "code_hash", "created_at", "used_at"]

    def has_add_permission(self, request):
        return False
