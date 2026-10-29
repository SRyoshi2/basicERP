import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-key")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:8080")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.core",
    "apps.crm",
    "apps.catalog",
    "apps.projects",
    "apps.timetracking",
    "apps.hr",
    "apps.archive",
    "apps.documents",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

if env_bool("USE_SQLITE", False):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    database_url = urlparse(
        os.getenv("DATABASE_URL", "postgresql://basicerp:basicerp@localhost:5432/basicerp")
    )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": database_url.path.lstrip("/"),
            "USER": database_url.username,
            "PASSWORD": database_url.password,
            "HOST": database_url.hostname,
            "PORT": database_url.port or 5432,
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "core.User"
AUTHENTICATION_BACKENDS = ["apps.core.backends.EmailOrUsernameBackend"]

LANGUAGE_CODE = "de-de"
TIME_ZONE = os.getenv("APP_TIME_ZONE", "Europe/Berlin")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
ARCHIVE_ROOT = Path(os.getenv("ARCHIVE_ROOT", BASE_DIR / "archive"))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": MEDIA_ROOT, "base_url": MEDIA_URL},
    },
    "archive": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": ARCHIVE_ROOT},
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "apps.core.permissions.HasCompletedPasswordChange",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.errors.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "basicERP API",
    "DESCRIPTION": "API-first ERP für kleine Unternehmen",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+",
    "SCHEMA_PATH_PREFIX_TRIM": False,
    "ENUM_NAME_OVERRIDES": {
        "AddressKindEnum": (("billing", "Rechnung"), ("shipping", "Lieferung"), ("other", "Sonstige")),
        "ContactKindEnum": (("organization", "Firma"), ("person", "Person")),
        "ContactActivityKindEnum": (("note", "Notiz"), ("call", "Anruf"), ("email", "E-Mail"), ("meeting", "Termin")),
        "CatalogItemKindEnum": (("product", "Artikel"), ("service", "Leistung")),
        "CatalogUnitEnum": (("hour", "Stunde"), ("day", "Tag"), ("piece", "Stück"), ("flat", "Pauschal")),
        "CatalogTaxRateEnum": (("19.00", "19 %"), ("7.00", "7 %"), ("0.00", "0 %")),
        "DocumentKindEnum": (("quote", "Angebot"), ("invoice", "Rechnung")),
        "ProjectStatusEnum": (("quotation", "Angebot"), ("active", "Aktiv"), ("paused", "Pausiert"), ("completed", "Abgeschlossen")),
        "WorkPackageStatusEnum": (("planned", "Geplant"), ("in_progress", "In Arbeit"), ("blocked", "Blockiert"), ("done", "Erledigt")),
        "TimeEntryBillingStatusEnum": (("unbilled", "Nicht abgerechnet"), ("billed", "Abgerechnet")),
        "AbsenceKindEnum": (("vacation", "Urlaub"), ("sickness", "Krankheit"), ("other", "Sonstiges")),
        "AbsenceStatusEnum": (("requested", "Beantragt"), ("approved", "Genehmigt"), ("rejected", "Abgelehnt"), ("cancelled", "Storniert")),
        "AbsenceActionEnum": (("created", "Erstellt"), ("updated", "Geändert"), ("approved", "Genehmigt"), ("rejected", "Abgelehnt"), ("cancelled", "Storniert")),
        "AuditActionEnum": (("created", "Erstellt"), ("updated", "Geändert"), ("archived", "Archiviert")),
        "IncomingInvoiceFormatEnum": (
            ("standard_pdf", "Normale PDF-Rechnung"),
            ("xrechnung_ubl", "XRechnung UBL"),
            ("xrechnung_cii", "XRechnung CII"),
            ("zugferd", "ZUGFeRD"),
            ("unknown", "Unbekannt"),
        ),
        "IncomingInvoiceStatusEnum": (("valid", "Basisprüfung bestanden"), ("invalid", "Prüfung fehlgeschlagen")),
    },
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "apps.core.errors.csrf_failure"
secure_cookies = os.getenv("APP_PUBLIC_SCHEME", "http") == "https"
SESSION_COOKIE_SECURE = secure_cookies
CSRF_COOKIE_SECURE = secure_cookies
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
