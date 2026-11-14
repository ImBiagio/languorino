from config.sentry import init_sentry

from .base import *  # noqa: F403
from .base import SENTRY_DSN, SENTRY_ENVIRONMENT, env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
REFRESH_COOKIE_SECURE = False

# Spento finche' SENTRY_DSN e' vuoto (il default in sviluppo).
init_sentry(SENTRY_DSN, SENTRY_ENVIRONMENT)
