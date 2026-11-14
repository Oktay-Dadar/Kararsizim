from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm, UsernameField
from django.core.exceptions import ValidationError

from .models import User


class RegisterForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email")
        field_classes = {"username": UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Kullanıcı adı"
        self.fields["username"].help_text = "3–20 karakter: harf, rakam ve alt çizgi."
        self.fields["username"].widget.attrs.update(autocomplete="username", autocapitalize="none")
        self.fields["email"].label = "E-posta"
        self.fields["email"].help_text = "Kimseye gösterilmez."
        self.fields["email"].widget.attrs.update(autocomplete="email")
        self.fields["password1"].label = "Parola"
        self.fields["password1"].help_text = "En az 8 karakter; sadece rakamdan oluşamaz."
        self.fields["password2"].label = "Parola (tekrar)"
        self.fields["password2"].help_text = ""

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Bu kullanıcı adı alınmış.", code="duplicate_username")
        return username

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Bu e-posta ile kayıtlı bir hesap var.", code="duplicate_email")
        return email


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Kullanıcı adı veya parola hatalı.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Kullanıcı adı"
        self.fields["username"].widget.attrs.update(autocapitalize="none")
        self.fields["password"].label = "Parola"
