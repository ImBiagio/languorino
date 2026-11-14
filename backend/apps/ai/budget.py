"""Tetto giornaliero alle chiamate a Gemini: per utente e per tutta l'app.

La registrazione e' aperta e il limite orario (``THROTTLE_AI``) da solo lascia
a un account 60 richieste l'ora per sempre, ognuna delle quali puo' far
partire decine di chiamate in Celery (un ricettario PDF, un mese di piano).
Qui si contano le chiamate vere, quelle scritte in ``AiCall``, e si chiude in
due punti: all'ingresso (le view con ``throttle_scope = "ai"`` rispondono 429)
e dentro il client, cosi' si ferma anche un lavoro gia' in coda.

Come per le immagini (``images_today``) contano solo le chiamate riuscite: un
503 di Gemini non costa e non deve togliere richieste a nessuno.
"""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.throttling import ScopedRateThrottle

from .models import AiCall

# Scritto da apps/profiles/live.py: una sessione a voce costa molto piu' di una
# chiamata di testo, quindi ha anche un tetto suo.
LIVE_FEATURE = "interview_live"


def _today():
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return AiCall.objects.filter(created_at__gte=start, ok=True)


def _is_user(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def calls_today(user=None) -> int:
    """Chiamate riuscite da mezzanotte: dell'utente, o di tutti senza utente."""
    calls = _today()
    return calls.filter(user=user).count() if _is_user(user) else calls.count()


def exhausted(user=None, *, live: bool = False) -> str:
    """Il messaggio da mostrare se il tetto di oggi e' finito, altrimenti "".

    Un tetto a 0 e' spento. ``live``: controlla anche le sessioni a voce.
    """
    per_user = settings.AI_CALLS_PER_DAY
    if per_user and _is_user(user) and calls_today(user) >= per_user:
        return _(
            "Per oggi hai finito le richieste all'intelligenza artificiale "
            "(%(n)d al giorno). Riprova domani."
        ) % {"n": per_user}
    total = settings.AI_CALLS_PER_DAY_GLOBAL
    if total and calls_today() >= total:
        return _(
            "Per oggi sono finite le richieste all'intelligenza artificiale di tutta l'app. "
            "Riprova domani."
        )
    sessions = settings.AI_LIVE_SESSIONS_PER_DAY
    if live and sessions and _is_user(user):
        if _today().filter(user=user, feature=LIVE_FEATURE).count() >= sessions:
            return _(
                "Per oggi hai finito le conversazioni a voce (%(n)d al giorno). Riprova domani."
            ) % {"n": sessions}
    return ""


class BudgetThrottled(APIException):
    """429 con il messaggio in ``detail``: il frontend lo mostra cosi' com'e'."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "ai_budget_exceeded"


class AiBudgetThrottle(ScopedRateThrottle):
    """Il limite orario di sempre, piu' il tetto del giorno sulle view "ai".

    Sta nel throttle e non in ogni view: chi mette ``throttle_scope = "ai"``
    ha gia' detto che la view chiama Gemini, e non puo' dimenticarsi il tetto.
    """

    def allow_request(self, request, view):
        if getattr(view, self.scope_attr, None) == "ai":
            message = exhausted(request.user)
            if message:
                raise BudgetThrottled(message)
        return super().allow_request(request, view)
