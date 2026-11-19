from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, env

DEBUG = False
CELERY_TASK_ALWAYS_EAGER = True
# Niente chiamate vere a cornhub nei test: si fingono con httpx finto o
# sostituendo le funzioni che chiamano l'AI.
CORNHUB_URL = "https://cornhub.test"
CORNHUB_INTERNAL_URL = "http://cornhub-backend:8000"
CORNHUB_APP_SLUG = "languorino"
CORNHUB_CLIENT_ID = "client-test"
CORNHUB_CLIENT_SECRET = "secret-test"
CORNHUB_APP_TOKEN = "token-test"
SCONTRINO_INTERNAL_URL = "http://scontrino-backend:8000"
API_PUBLIC_URL = "https://app.test"
FRONTEND_BASE_URL = "https://app.test"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
# La cache locmem vive per tutta la sessione di test: con i limiti veri i test
# che fanno login si toglierebbero il posto a vicenda. Il throttling ha un test suo.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "auth": "10000/min",
        "refresh": "10000/min",
        "ai": "10000/min",
        "public": "10000/min",
        "comments": "10000/min",
        "invites": "10000/min",
    },
}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
DATABASES["default"]["HOST"] = env("POSTGRES_HOST", "db")  # noqa: F405
