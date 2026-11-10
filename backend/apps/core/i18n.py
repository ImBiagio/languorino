"""Lingua dell'interfaccia (ADR 0001).

Il frontend usa lo stesso catalogo gettext di Django: le sue stringhe stanno nel
dominio ``djangojs`` di ``locale/<lingua>/LC_MESSAGES`` e arrivano come JSON da
``JSONCatalog``. La lingua scelta si ricorda nel cookie standard di Django
(letto da ``LocaleMiddleware``) e, per chi ha fatto login, su ``User.language``,
cosi' anche le mail partono nella lingua giusta.
"""

from __future__ import annotations

import json

from django.conf import settings
from django.utils import translation
from django.views.i18n import JSONCatalog
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

LANGUAGE_CODES = [code for code, _name in settings.LANGUAGES]


class CatalogView(JSONCatalog):
    """Catalogo ``djangojs`` della lingua attiva, piu' il codice della lingua."""

    domain = "djangojs"

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        payload = json.loads(response.content)
        payload["language"] = translation.get_language()
        # Scelta esplicita (cookie) o solo dedotta da Accept-Language: al login
        # la prima si salva sull'utente, la seconda cede a quella salvata.
        payload["explicit"] = settings.LANGUAGE_COOKIE_NAME in self.request.COOKIES
        payload["languages"] = [
            {"code": code, "name": name} for code, name in settings.LANGUAGES
        ]
        response.content = json.dumps(payload)
        # Dipende dal cookie/Accept-Language: nessuna cache condivisa.
        response["Vary"] = "Cookie, Accept-Language"
        response["Cache-Control"] = "private, no-cache"
        return response


class LanguageSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=LANGUAGE_CODES)


class LanguageView(APIView):
    """Sceglie la lingua: cookie per tutti, ``User.language`` se c'e' il login."""

    permission_classes = [AllowAny]

    @extend_schema(request=LanguageSerializer, responses={200: LanguageSerializer})
    def post(self, request):
        serializer = LanguageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        language = serializer.validated_data["language"]
        if request.user.is_authenticated and request.user.language != language:
            request.user.language = language
            request.user.save(update_fields=["language"])
        response = Response({"language": language})
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
        return response
