"""L'unico punto d'accesso a Gemini (progettazione, principio 5; ADR 0005).

Lo schema e' quello di soldino, gia' provato in produzione: risposta JSON
vincolata a un modello pydantic, API ``v1beta`` esplicita (google-genai 3
passava a ``v1`` e ogni modello rispondeva 404), un modello principale e delle
riserve. Un modello che risponde "sovraccarico" resta giu' per qualche minuto
nella cache condivisa, cosi' anche gli altri worker partono da quello che va.

Le altre app non chiamano Gemini: chiamano ``generate`` con i loro contenuti e
il loro schema, e qui si registra ogni chiamata in ``AiCall``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _
from pydantic import BaseModel

from .models import AiCall

logger = logging.getLogger(__name__)

API_VERSION = "v1beta"
# 429 troppe richieste, 500/503 sovraccarico, 504 timeout di Google: passano da soli.
TRANSIENT_CODES = {429, 500, 503, 504}
RETRY_PAUSES = (4, 12)


class AIError(Exception):
    """Errore da mostrare all'utente cosi' com'e' (finisce in ``Job.error``)."""


class AIOverloaded(AIError):
    """Tutti i modelli sovraccarichi o irraggiungibili: passa da solo, si puo'
    riprovare piu' tardi (i ricettari PDF lo fanno senza fermarsi)."""


def is_enabled() -> bool:
    return bool(settings.GEMINI_API_KEY)


def _down_key(model: str) -> str:
    return f"gemini:down:{model}"


def mark_down(model: str, seconds: int | None = None) -> None:
    cache.set(_down_key(model), True, seconds or settings.GEMINI_MODEL_COOLDOWN)


def models_in_order() -> list[str]:
    """Principale e riserve; quelli segnati giu' in fondo (non tolti: se sono
    giu' tutti si riprova comunque)."""
    models = list(dict.fromkeys([settings.GEMINI_MODEL, *settings.GEMINI_FALLBACK_MODELS]))
    return sorted(models, key=lambda model: bool(cache.get(_down_key(model))))


def _log(user, feature: str, model: str, started: float, response=None, error: str = "") -> None:
    usage = getattr(response, "usage_metadata", None)
    AiCall.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        feature=feature,
        model=model,
        input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
        output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        duration_ms=int((time.monotonic() - started) * 1000),
        ok=not error,
        error=error[:200],
    )


def _parse[Schema: BaseModel](response, schema: type[Schema]) -> Schema:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, schema):
        return parsed
    try:
        return schema.model_validate_json(response.text or "")
    except Exception as exc:
        raise AIError(
            _("La risposta dell'intelligenza artificiale non è nel formato atteso.")
        ) from exc


def generate[Schema: BaseModel](
    contents: Callable[[Any], list],
    schema: type[Schema],
    *,
    feature: str,
    user=None,
    timeout_ms: int = 60_000,
    temperature: float = 0.2,
) -> tuple[Schema, str]:
    """Chiama Gemini e restituisce ``(risposta validata, modello usato)``.

    ``contents`` riceve il modulo ``google.genai.types`` e restituisce le parti
    della richiesta (testo, ``Part.from_bytes`` per immagini e PDF): cosi' chi
    chiama non importa l'SDK. Errori temporanei passano al modello successivo;
    finito il giro si aspetta e si riprova. Chiave rifiutata o richiesta non
    valida non dipendono dal modello e si fermano subito.
    """
    if not is_enabled():
        raise AIError(
            _("Chiave Gemini non configurata: imposta GEMINI_API_KEY nel file .env e riavvia.")
        )

    from google import genai
    from google.genai import errors, types

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=timeout_ms, api_version=API_VERSION),
    )
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=temperature,
    )
    parts = contents(types)

    tried: list[str] = []
    last_error = ""
    for pause in (*RETRY_PAUSES, None):
        for model in models_in_order():
            started = time.monotonic()
            try:
                response = client.models.generate_content(
                    model=model, contents=parts, config=config
                )
            except errors.APIError as exc:
                _log(user, feature, model, started, error=f"{exc.code} {exc.message or ''}")
                if exc.code == 404:
                    # Modello inesistente per questa chiave: inutile riprovarlo oggi.
                    mark_down(model, 24 * 60 * 60)
                elif exc.code in TRANSIENT_CODES:
                    mark_down(model)
                elif exc.code in (401, 403):
                    raise AIError(
                        _("Gemini ha rifiutato la chiave: controlla GEMINI_API_KEY.")
                    ) from exc
                else:
                    raise AIError(
                        _("Gemini ha risposto con un errore (%(code)s).") % {"code": exc.code}
                    ) from exc
                tried.append(model)
                last_error = _("errore %(code)s") % {"code": exc.code}
                continue
            except SoftTimeLimitExceeded:
                raise
            except Exception as exc:  # rete, timeout
                _log(user, feature, model, started, error=str(exc) or type(exc).__name__)
                mark_down(model)
                tried.append(model)
                last_error = str(exc)[:120] or type(exc).__name__
                continue
            _log(user, feature, model, started, response=response)
            cache.delete(_down_key(model))
            return _parse(response, schema), model
        if pause is not None:
            time.sleep(pause)

    raise AIOverloaded(
        _(
            "Gemini è sovraccarico in questo momento (%(models)s; ultimo: %(error)s). "
            "Riprova tra qualche minuto."
        )
        % {"models": ", ".join(dict.fromkeys(tried)), "error": last_error}
    )


def generate_image(
    prompt: str, *, feature: str, user=None, timeout_ms: int = 120_000
) -> tuple[bytes, str, str]:
    """Un'immagine da un testo: ``(byte, tipo, modello)``. Un solo modello,
    senza riserve: le immagini non sono urgenti e costano."""
    if not is_enabled():
        raise AIError(
            _("Chiave Gemini non configurata: imposta GEMINI_API_KEY nel file .env e riavvia.")
        )

    from google import genai
    from google.genai import errors, types

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=timeout_ms, api_version=API_VERSION),
    )
    model = settings.GEMINI_MODEL_IMAGE
    started = time.monotonic()
    try:
        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
    except errors.APIError as exc:
        _log(user, feature, model, started, error=f"{exc.code} {exc.message or ''}")
        if exc.code == 429 and "limit: 0" in str(exc):
            # Piano gratuito: per le immagini la quota e' zero, non passa aspettando.
            raise AIError(
                _(
                    "La chiave Gemini non ha quota per le immagini (piano gratuito): "
                    "attiva la fatturazione su Google AI Studio."
                )
            ) from exc
        if exc.code in TRANSIENT_CODES:
            raise AIOverloaded(
                _("Gemini è sovraccarico in questo momento. Riprova tra qualche minuto.")
            ) from exc
        if exc.code in (401, 403):
            raise AIError(_("Gemini ha rifiutato la chiave: controlla GEMINI_API_KEY.")) from exc
        raise AIError(
            _("Gemini ha risposto con un errore (%(code)s).") % {"code": exc.code}
        ) from exc
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:  # rete, timeout
        _log(user, feature, model, started, error=str(exc) or type(exc).__name__)
        raise AIOverloaded(_("Gemini non risponde. Riprova tra qualche minuto.")) from exc
    _log(user, feature, model, started, response=response)
    for candidate in response.candidates or []:
        for part in getattr(candidate.content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and inline.data:
                return inline.data, inline.mime_type or "image/png", model
    raise AIError(_("Gemini non ha disegnato niente questa volta. Riprova."))
