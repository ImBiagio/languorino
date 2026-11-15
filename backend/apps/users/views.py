"""Sessione dell'app. Registrazione, password e email stanno su cornhub
(login unico della suite): qui si entra solo da ``sso.py``.

La sessione resta quella di sempre: access token in memoria nel frontend,
refresh token in un cookie httpOnly su /api/auth, blacklist al logout.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core import cornhub

from .serializers import TokenPairSerializer, UserSerializer

User = get_user_model()


def _set_refresh_cookie(response, refresh: RefreshToken):
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        str(refresh),
        max_age=settings.REFRESH_TOKEN_LIFETIME,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
    )
    return response


def issue_session(response, user):
    """Apre la sessione dell'app sulla risposta (dopo il login su cornhub)."""
    return _set_refresh_cookie(response, RefreshToken.for_user(user))


def revoke_all_refresh_tokens(user) -> None:
    """Ogni sessione aperta dell'utente non potra' piu' rinnovarsi."""
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in OutstandingToken.objects.filter(user=user)],
        ignore_conflicts=True,
    )


def still_allowed(user) -> bool:
    """L'account su cornhub e' ancora attivo e puo' usare quest'app?
    Controllato a ogni refresh (cache di 2 minuti in ``cornhub.user_status``)."""
    if not user.cornhub_sub:
        return False
    data = cornhub.user_status(str(user.cornhub_sub))
    return bool(data.get("active") and data.get("allowed"))


class AuthConfigView(APIView):
    """Dove sono login e account: il frontend non li scrive a mano."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        base = settings.CORNHUB_URL.rstrip("/")
        return Response({
            "login_url": f"{settings.API_PUBLIC_URL.rstrip('/')}/api/auth/sso/start",
            "account_url": f"{base}/account/",
            "ai_url": f"{base}/account/ai/",
            "register_url": f"{base}/registrati",
        })


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "refresh"

    @extend_schema(request=None, responses={200: TokenPairSerializer})
    def post(self, request):
        # Solo dal cookie: il refresh non deve mai passare dal JavaScript.
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            return Response({"detail": _("Sessione assente.")}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            refresh = RefreshToken(raw)
        except TokenError:
            return Response({"detail": _("Sessione scaduta.")}, status=status.HTTP_401_UNAUTHORIZED)

        user = User.objects.filter(pk=refresh.payload.get("user_id"), is_active=True).first()
        if user is None or not still_allowed(user):
            # Account spento su cornhub: la sessione di quest'app finisce qui.
            if user is not None:
                revoke_all_refresh_tokens(user)
            return Response({"detail": _("Accesso non piu' valido.")},
                            status=status.HTTP_401_UNAUTHORIZED)

        new_refresh = RefreshToken.for_user(user)
        payload = {"access": str(new_refresh.access_token), "user": UserSerializer(user).data}
        return _set_refresh_cookie(Response(payload), new_refresh)


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        # Il cookie cancellato non basta: chi l'avesse copiato potrebbe ancora usarlo.
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        # Il frontend poi va qui: cornhub chiede se uscire anche dall'account.
        response = Response({"logout_url": cornhub.logout_url(f"{settings.FRONTEND_BASE_URL}/")})
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=UserSerializer, responses={200: UserSerializer})
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
