"""Token per verifica email e reset password.

Verifica: token firmato stateless (niente tabella), monouso perche' la view
rifiuta un utente gia' verificato. Reset: il generatore di Django, che mette
nell'hash password e ultimo login, quindi il link muore appena usato.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.core.methods import sign, unsign

EMAIL_VERIFY_SALT = "languorino.email-verify"
DEFAULT_MAX_AGE = 60 * 60 * 24 * 3  # 3 giorni


def make_token(user_id, salt: str) -> str:
    return sign({"uid": str(user_id)}, salt)


def read_token(token: str, salt: str, max_age: int = DEFAULT_MAX_AGE) -> str | None:
    data = unsign(token, salt, max_age)
    return data.get("uid") if data else None


def email_verification_url(user) -> str:
    token = make_token(user.pk, EMAIL_VERIFY_SALT)
    return f"{settings.FRONTEND_BASE_URL}/verifica-email/{token}"


def password_reset_url(user) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_BASE_URL}/reset-password/{uid}/{token}"


def user_from_reset_token(uid: str, token: str):
    """L'utente del link di reset, o ``None`` se il link e' falso, usato o scaduto."""
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError

    try:
        pk = force_str(urlsafe_base64_decode(uid))
        user = get_user_model().objects.get(pk=pk, is_active=True)
    except (ValueError, TypeError, OverflowError, ValidationError, get_user_model().DoesNotExist):
        return None
    return user if default_token_generator.check_token(user, token) else None
