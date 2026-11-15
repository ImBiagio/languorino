"""Login con l'account unico di cornhub (OIDC, ADR 0021).

Il giro: ``/api/auth/sso/start`` manda su cornhub.it con state, nonce e
PKCE salvati in un cookie firmato; cornhub fa entrare l'utente e torna su
``/api/auth/sso/callback`` col codice; qui lo si scambia per l'id_token
(verificato), si trova o si crea l'utente locale e si apre la sessione
dell'app (refresh token nel cookie httpOnly, come prima).
"""

from __future__ import annotations

import logging
import secrets
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.core import cornhub
from apps.core.methods import normalize_email

logger = logging.getLogger(__name__)
User = get_user_model()

COOKIE = "sso_login"
COOKIE_PATH = "/api/auth/sso"
SALT = "sso-login"
MAX_AGE = 10 * 60


def redirect_uri() -> str:
    return f"{settings.API_PUBLIC_URL.rstrip('/')}/api/auth/sso/callback"


def safe_next(value: str | None) -> str:
    """Solo percorsi dell'app: mai un redirect verso un altro dominio."""
    if value and value.startswith("/") and not value.startswith("//") and \
            url_has_allowed_host_and_scheme(value, allowed_hosts=None):
        return value
    return "/"


def _cookie_name() -> str:
    return f"{settings.REFRESH_COOKIE_NAME}_{COOKIE}"


def _front(path: str) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}{path}"


def _fail(reason: str) -> HttpResponseRedirect:
    response = HttpResponseRedirect(_front(f"/accedi?errore={quote(reason)}"))
    response.delete_cookie(_cookie_name(), path=COOKIE_PATH)
    return response


def user_from_claims(claims: dict):
    """L'utente locale dell'account cornhub: per ``sub``, altrimenti per email
    (solo se cornhub l'ha verificata: e' cosi' che gli account che c'erano
    prima di cornhub si agganciano), altrimenti nuovo, senza password."""
    sub = claims["sub"]
    email = normalize_email(claims.get("email", ""))
    name = (claims.get("name") or "").strip()
    language = claims.get("locale") if claims.get("locale") in dict(settings.LANGUAGES) else None

    with transaction.atomic():
        user = User.objects.select_for_update().filter(cornhub_sub=sub).first()
        if user is None and email and claims.get("email_verified"):
            user = User.objects.select_for_update().filter(
                email=email, cornhub_sub__isnull=True
            ).first()
        if user is None:
            if not email:
                return None
            user = User(email=email, cornhub_sub=sub, email_verified_at=timezone.now())
            user.set_unusable_password()
        user.cornhub_sub = sub
        if name:
            user.display_name = name[:120]
        if language:
            user.language = language
        if email and email != user.email and not User.objects.filter(email=email).exclude(
            pk=user.pk
        ).exists():
            user.email = email
        if claims.get("email_verified") and not user.email_verified_at:
            user.email_verified_at = timezone.now()
        try:
            with transaction.atomic():
                user.save()
        except IntegrityError:
            logger.warning("SSO: utente non salvato (email gia' usata?)")
            return None
    return user


class SSOStartView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "auth"

    def get(self, request):
        login = cornhub.new_login()
        login["next"] = safe_next(request.GET.get("next"))
        response = HttpResponseRedirect(cornhub.authorize_url(login, redirect_uri()))
        response.set_cookie(
            _cookie_name(),
            signing.dumps(login, salt=SALT),
            max_age=MAX_AGE,
            httponly=True,
            secure=settings.REFRESH_COOKIE_SECURE,
            # Lax: il ritorno da cornhub e' una navigazione di primo livello.
            samesite="Lax",
            path=COOKIE_PATH,
        )
        return response


class SSOCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "auth"

    def get(self, request):
        from .views import issue_session

        if request.GET.get("error"):
            return _fail("annullato")
        try:
            login = signing.loads(
                request.COOKIES.get(_cookie_name(), ""), salt=SALT, max_age=MAX_AGE
            )
        except signing.BadSignature:
            return _fail("scaduto")
        if not secrets.compare_digest(request.GET.get("state", ""), login["state"]):
            return _fail("stato")
        try:
            claims = cornhub.exchange_code(
                request.GET.get("code", ""), login["verifier"], redirect_uri(), login["nonce"]
            )
        except cornhub.SSOError as exc:
            logger.warning("SSO fallito: %s", exc)
            return _fail("cornhub")
        user = user_from_claims(claims)
        if user is None or not user.is_active:
            return _fail("account")
        response = HttpResponseRedirect(_front(login["next"]))
        response.delete_cookie(_cookie_name(), path=COOKIE_PATH)
        return issue_session(response, user)
