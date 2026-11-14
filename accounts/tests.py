from django.contrib.auth import SESSION_KEY
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from .forms import RegisterForm
from .models import User

PASSWORD = "kararsiz-test-parola-1"


def register_data(**overrides):
    data = {
        "username": "yeni_kisi",
        "email": "yeni@example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(overrides)
    return data


class RegisterFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user("Mevcut", "mevcut@example.com", PASSWORD)

    def test_duplicate_email_is_rejected(self):
        form = RegisterForm(register_data(email="mevcut@example.com"))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["email"], ["Bu e-posta ile kayıtlı bir hesap var."])

    def test_duplicate_email_is_case_insensitive(self):
        form = RegisterForm(register_data(email="MEVCUT@Example.com"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_username_is_case_insensitive_unique(self):
        form = RegisterForm(register_data(username="mevcut"))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["username"], ["Bu kullanıcı adı alınmış."])

    def test_invalid_username_characters_are_rejected(self):
        for username in ("ali veli", "ali!", "çağrı", "ab", "a" * 21):
            with self.subTest(username=username):
                form = RegisterForm(register_data(username=username))
                self.assertFalse(form.is_valid())
                self.assertIn("username", form.errors)

    def test_reserved_username_is_rejected(self):
        form = RegisterForm(register_data(username="Admin"))
        self.assertFalse(form.is_valid())
        self.assertIn("Bu kullanıcı adı kullanılamaz.", form.errors["username"])

    def test_short_password_is_rejected(self):
        form = RegisterForm(register_data(password1="kisa1", password2="kisa1"))
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_email_is_stored_lowercase(self):
        form = RegisterForm(register_data(email="Yeni@Example.COM"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().email, "yeni@example.com")


class RegisterViewTests(TestCase):
    def test_success_logs_in_and_redirects_with_welcome(self):
        response = self.client.post(reverse("accounts:register"), register_data())
        self.assertRedirects(response, reverse("polls:index"))
        user = User.objects.get(username="yeni_kisi")
        self.assertEqual(int(self.client.session[SESSION_KEY]), user.pk)
        self.assertEqual([str(m) for m in get_messages(response.wsgi_request)], ["Hoş geldin, @yeni_kisi"])

    def test_error_is_shown_under_field(self):
        User.objects.create_user("baska", "yeni@example.com", PASSWORD)
        response = self.client.post(reverse("accounts:register"), register_data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<p class="field__error">Bu e-posta ile kayıtlı bir hesap var.</p>', html=True)

    def test_authenticated_user_is_redirected(self):
        self.client.force_login(User.objects.create_user("uye", "uye@example.com", PASSWORD))
        self.assertRedirects(self.client.get(reverse("accounts:register")), reverse("polls:index"))


class LoginLogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("KararVer", "karar@example.com", PASSWORD)

    def test_login_is_case_insensitive(self):
        response = self.client.post(reverse("accounts:login"), {"username": "kararver", "password": PASSWORD})
        self.assertRedirects(response, reverse("polls:index"))
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)

    def test_wrong_password_shows_turkish_error(self):
        response = self.client.post(reverse("accounts:login"), {"username": "KararVer", "password": "yanlis"})
        self.assertContains(response, "Kullanıcı adı veya parola hatalı.")

    def test_login_follows_safe_next(self):
        url = reverse("accounts:login") + "?next=" + reverse("polls:create")
        response = self.client.post(url, {"username": "KararVer", "password": PASSWORD, "next": reverse("polls:create")})
        self.assertRedirects(response, reverse("polls:create"))

    def test_login_ignores_external_next(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "KararVer", "password": PASSWORD, "next": "https://example.org/"},
        )
        self.assertRedirects(response, reverse("polls:index"))

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("polls:index"))
        self.assertNotIn(SESSION_KEY, self.client.session)


class CreateRedirectTests(TestCase):
    def test_anonymous_create_redirects_to_login_with_notice(self):
        create_url = reverse("polls:create")
        response = self.client.get(create_url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={create_url}")
        login_page = self.client.get(response.url)
        self.assertContains(login_page, "Anket oluşturmak için giriş yapman gerekiyor.")

    def test_plain_login_page_has_no_notice(self):
        self.assertNotContains(self.client.get(reverse("accounts:login")), "Anket oluşturmak için giriş")


class EmailPrivacyTests(TestCase):
    def test_email_never_rendered_for_logged_in_user(self):
        user = User.objects.create_user("gizli", "gizli.adres@example.com", PASSWORD)
        self.client.force_login(user)
        for url in (reverse("polls:index"), reverse("polls:create")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "@gizli")
                self.assertNotContains(response, "gizli.adres")
