from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import SECRET_KEY

DEBUG = False

# Con la chiave di default chiunque potrebbe firmare JWT e link di verifica.
if not SECRET_KEY or SECRET_KEY in {"insecure-dev-key", "change-me-in-production"}:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY va impostata in produzione.")

SECURE_SSL_REDIRECT = True
# L'healthcheck di Docker parla HTTP diretto col container, senza proxy.
SECURE_REDIRECT_EXEMPT = [r"^api/health$"]
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
REFRESH_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# Schema e Swagger solo per lo staff loggato nell'admin: in produzione non
# serve a nessun altro la mappa completa dell'API.
SPECTACULAR_SETTINGS = {
    **SPECTACULAR_SETTINGS,  # noqa: F405
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "SERVE_AUTHENTICATION": ["rest_framework.authentication.SessionAuthentication"],
}
