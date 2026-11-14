from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.i18n import CatalogView, LanguageView
from apps.core.media import serve_public_media


def health(request):
    """Per l'healthcheck del container: risponde senza DB, auth ne' redirect."""
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("api/health", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/i18n/catalog", CatalogView.as_view(), name="i18n-catalog"),
    path("api/i18n/language", LanguageView.as_view(), name="i18n-language"),
    path("api/", include("apps.users.urls")),
    path("api/", include("apps.profiles.urls")),
    path("api/", include("apps.recipes.urls")),
    path("api/", include("apps.jobs.urls")),
    path("api/", include("apps.plans.urls")),
    path("api/", include("apps.shopping.urls")),
    path("api/", include("apps.kitchen.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

# In sviluppo i media li serve Django; in produzione il Caddy di ``web`` legge
# lo stesso volume (deploy/Caddyfile). In entrambi i casi solo quelli pubblici.
if settings.DEBUG:
    urlpatterns += [
        re_path(
            rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$",
            serve_public_media,
            name="media",
        )
    ]
