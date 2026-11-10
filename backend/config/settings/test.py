from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, env

DEBUG = False
CELERY_TASK_ALWAYS_EAGER = True
# Niente chiamate vere agli LLM nei test: si fingono nei test che li riguardano.
GEMINI_API_KEY = ""
REQUIRE_EMAIL_VERIFICATION = False
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
    },
}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
DATABASES["default"]["HOST"] = env("POSTGRES_HOST", "db")  # noqa: F405
