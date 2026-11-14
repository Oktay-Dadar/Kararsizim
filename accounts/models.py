from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.db.models.functions import Lower

from .validators import validate_username_format, validate_username_not_reserved


class UserManager(DjangoUserManager):
    @classmethod
    def normalize_email(cls, email):
        return (email or "").strip().lower()

    def get_by_natural_key(self, username):
        return self.get(username__iexact=username)


class User(AbstractUser):
    username = models.CharField(
        "kullanıcı adı",
        max_length=20,
        unique=True,
        validators=[validate_username_format, validate_username_not_reserved],
        error_messages={"unique": "Bu kullanıcı adı alınmış."},
    )
    email = models.EmailField(
        "e-posta",
        unique=True,
        error_messages={"unique": "Bu e-posta ile kayıtlı bir hesap var."},
    )

    objects = UserManager()

    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = "kullanıcı"
        verbose_name_plural = "kullanıcılar"
        constraints = [
            models.UniqueConstraint(
                Lower("username"),
                name="uniq_username_ci",
                violation_error_message="Bu kullanıcı adı alınmış.",
            ),
            models.UniqueConstraint(
                Lower("email"),
                name="uniq_email_ci",
                violation_error_message="Bu e-posta ile kayıtlı bir hesap var.",
            ),
        ]

    def __str__(self):
        return self.username
