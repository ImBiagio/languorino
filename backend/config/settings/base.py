"""Settings condivisi. Tutto cio' che cambia tra ambienti sta in dev.py / prod.py."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parents[2]


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    return env(key, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    raw = env(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# Nome mostrato nelle mail e nell'API: fuori dalle stringhe tradotte, cosi'
# rinominare il progetto non rompe i cataloghi gettext.
APP_NAME = "Templatino"

SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-dev-key")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:5190")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "simple_history",
    "django_celery_beat",
    # local
    "apps.core",
    "apps.users",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "templatino"),
        "USER": env("POSTGRES_USER", "templatino"),
        "PASSWORD": env("POSTGRES_PASSWORD", "templatino"),
        "HOST": env("POSTGRES_HOST", "db"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": True,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Lingue (ADR 0001): l'italiano e' la lingua sorgente dei msgid, l'inglese sta
# in locale/en. LocaleMiddleware sceglie dal cookie `django_language` (scritto
# da /api/i18n/language) e poi da Accept-Language.
LANGUAGE_CODE = "it"
LANGUAGES = [("it", "Italiano"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
LANGUAGE_COOKIE_SAMESITE = "Lax"
TIME_ZONE = "Europe/Rome"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
    # Solo le view con ``throttle_scope`` sono limitate: login, registrazione e
    # le chiamate agli LLM. I contatori stanno nella cache Django, cioe' Redis.
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "auth": env("THROTTLE_AUTH", "10/min"),
        "refresh": env("THROTTLE_REFRESH", "60/min"),
        # Ogni chiamata a Gemini consuma la quota della chiave.
        "ai": env("THROTTLE_AI", "60/hour"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": f"{APP_NAME} API",
    "DESCRIPTION": APP_NAME,
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api",
}

ACCESS_TOKEN_LIFETIME = int(env("ACCESS_TOKEN_LIFETIME", "900"))
REFRESH_TOKEN_LIFETIME = int(env("REFRESH_TOKEN_LIFETIME", "1209600"))

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(seconds=ACCESS_TOKEN_LIFETIME),
    "REFRESH_TOKEN_LIFETIME": timedelta(seconds=REFRESH_TOKEN_LIFETIME),
    "ROTATE_REFRESH_TOKENS": True,
    # La blacklist serve a logout e cambio password, non alla rotazione: con
    # due schede aperte che rinnovano insieme, blacklistare il token ruotato
    # butterebbe fuori una delle due.
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Il refresh token vive in un cookie httpOnly; l'access token sta in memoria nel frontend.
# I cookie non distinguono le porte: due stack sullo stesso host (due progetti
# in locale, o un worktree) devono usare nomi diversi, altrimenti il login su
# uno sovrascrive il cookie dell'altro.
REFRESH_COOKIE_NAME = env("REFRESH_COOKIE_NAME", "templatino_refresh")
REFRESH_COOKIE_SECURE = env_bool("REFRESH_COOKIE_SECURE", True)
REFRESH_COOKIE_SAMESITE = env("REFRESH_COOKIE_SAMESITE", "Lax")
REFRESH_COOKIE_PATH = "/api/auth"

REQUIRE_EMAIL_VERIFICATION = env_bool("REQUIRE_EMAIL_VERIFICATION", True)

# --- Celery ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://redis:6379/1")
# Nessuno legge il valore di ritorno dei task: lo stato sta nel DB. Senza
# result backend Redis non accumula risultati mai letti.
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = False

# Sincronizzato nel DB da django-celery-beat all'avvio dello scheduler.
CELERY_BEAT_SCHEDULE = {
    "flush-expired-tokens": {
        "task": "apps.users.tasks.flush_expired_tokens",
        "schedule": crontab(hour=4, minute=0),
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", "redis://redis:6379/0"),
    }
}

# --- Email ---
# In sviluppo le mail vanno nella console del worker. In produzione SMTP di
# Brevo, lo stesso account di tutti i progetti (dominio inoo.it).
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Templatino <no-reply@templatino.local>")

# --- Upload ---
UPLOAD_MAX_BYTES = int(env("UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = UPLOAD_MAX_BYTES
DATA_UPLOAD_MAX_MEMORY_SIZE = UPLOAD_MAX_BYTES + 1024 * 1024

# --- LLM (Gemini, Google AI Studio) ---
# Vuota: le funzioni che usano l'LLM restano spente.
GEMINI_API_KEY = env("GEMINI_API_KEY", "")
# flash-lite: risponde in 1-2 s; i flash piu' grandi davano spesso 503 o 6-20 s.
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-3.5-flash-lite")
# Col piano gratuito a tratti ci mette 20 secondi.
GEMINI_TIMEOUT = float(env("GEMINI_TIMEOUT", "30"))

# Il link di reset vale 2 ore (il default di Django sono 3 giorni).
PASSWORD_RESET_TIMEOUT = int(env("PASSWORD_RESET_TIMEOUT", str(2 * 60 * 60)))
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", "http://localhost:5190")

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:5190")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{levelname} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
