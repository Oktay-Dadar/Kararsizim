from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User

_default_add_fields = DjangoUserAdmin.add_fieldsets[0][1]["fields"]


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "is_staff", "is_active", "date_joined")
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", *(f for f in _default_add_fields if f != "username")),
            },
        ),
    )
