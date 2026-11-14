import os
import sys
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


VERCEL_HOST_ENV_NAMES = ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL", "VERCEL_URL")


def vercel_hosts(environ=os.environ):
    """Hostnames Vercel assigns to this deployment, so no *.vercel.app wildcard is needed."""
    hosts = []
    for name in VERCEL_HOST_ENV_NAMES:
        host = environ.get(name, "").strip().lower()
        if host and host not in hosts:
            hosts.append(host)
    return hosts


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG")
VOTER_KEY_SALT = os.environ["VOTER_KEY_SALT"]

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
for _host in vercel_hosts():
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)
    if f"https://{_host}" not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")

if not DEBUG:
    # Vercel terminates TLS and forwards the original scheme; og:url/og:image rely on it.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
    # *.vercel.app is already on the browsers' HSTS preload list; see docs/PROJECT.md §15.
    SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
    # Django only prints errors to the console when DEBUG is on; Vercel logs read stdout/stderr.
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {"console": {"class": "logging.StreamHandler"}},
        "root": {"handlers": ["console"], "level": "WARNING"},
    }

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "polls",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Migrations must go through the session pooler (DATABASE_URL_DIRECT); see docs/PROJECT.md §11.1.
DATABASE_URL_ENV = "DATABASE_URL_DIRECT" if env_bool("DJANGO_DB_DIRECT") else "DATABASE_URL"

DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get(DATABASE_URL_ENV) or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=0,
    )
}

# Supabase transaction pooler does not support server-side cursors or prepared statements.
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    db_options = DATABASES["default"].setdefault("OPTIONS", {})
    db_options["prepare_threshold"] = None
    db_options.setdefault("sslmode", "require")

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/giris/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SESSION_ENGINE = "django.contrib.sessions.backends.db"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Tests never touch Supabase; see docs/PROJECT.md §15.
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"
if TESTING:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    WHITENOISE_AUTOREFRESH = True
    SECURE_SSL_REDIRECT = False

# v1 sends no email (docs/PROJECT.md §1); the console backend is only for local development.
if DEBUG:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.console.EmailBackend",
        },
    }
