import re

from django.core.exceptions import ValidationError

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,20}$")

RESERVED_USERNAMES = frozenset(
    {"admin", "root", "api", "static", "anket", "giris", "kayit", "cikis", "kullanici", "hakkinda"}
)


def validate_username_format(value):
    if not USERNAME_PATTERN.fullmatch(value or ""):
        raise ValidationError(
            "Kullanıcı adı 3–20 karakter olmalı; sadece harf, rakam ve alt çizgi kullanabilirsin.",
            code="invalid_username",
        )


def validate_username_not_reserved(value):
    if (value or "").lower() in RESERVED_USERNAMES:
        raise ValidationError("Bu kullanıcı adı kullanılamaz.", code="reserved_username")
