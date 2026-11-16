"""L'unico punto d'accesso all'intelligenza artificiale (ADR 0005, 0021).

Languorino non chiama piu' Gemini: chiede tutto a cornhub
(``apps.core.cornhub``), che sceglie modello, riserve e chi paga (la chiave
di casa per le funzioni piccole, quella dell'utente per le grandi) e tiene i
limiti di spesa. Questo modulo e' un adattatore sottile: tiene le firme e le
eccezioni di sempre, cosi' chi chiama cambia solo come passa i file.

- ``generate(parts, Schema, feature=..., user=...)`` -> ``(Schema, modello)``;
  ``parts`` sono stringhe e ``file_part(byte, mime)``.
- ``generate_image(prompt, feature=..., user=...)`` -> ``(byte, mime, modello)``.

Errori di cornhub tradotti:

- ``overloaded`` -> ``AIOverloaded``: passa da solo, i lavori lunghi
  riprovano piu' tardi come prima;
- ``needs_key``, ``limit``, ``house_empty`` -> ``AIBudgetExceeded``: serve
  la chiave dell'utente o un limite piu' alto, aspettare non basta (i
  ricettari si fermano col messaggio, niente riprova all'infinito);
- tutto il resto -> ``AIError``.

Il messaggio va mostrato cosi' com'e'; ``account_url`` porta alla pagina di
cornhub dove si aggiunge la chiave o si alza il limite.
"""

from __future__ import annotations

from pydantic import BaseModel

from apps.core import cornhub

# Errori che non passano aspettando qualche minuto: serve fare qualcosa su cornhub.
STOP_CODES = {"needs_key", "limit", "house_empty"}


class AIError(Exception):
    """Errore da mostrare all'utente cosi' com'e' (finisce in ``Job.error``)."""

    def __init__(self, message: str = "", code: str = "error", account_url: str = ""):
        super().__init__(message)
        self.message = message
        self.code = code
        self.account_url = account_url


class AIOverloaded(AIError):
    """L'AI non risponde (tutti i modelli e i provider provati da cornhub):
    passa da solo, si puo' riprovare piu' tardi."""


class AIBudgetExceeded(AIError):
    """Serve la chiave API dell'utente, il limite di spesa e' raggiunto o la
    quota di casa e' finita: ci si ferma con il messaggio e il link a cornhub."""


class AINoImage(AIOverloaded):
    """Il modello non ha disegnato niente. cornhub lo segnala come
    ``overloaded`` (riprovando di solito va): resta per chi lo distingue."""


def is_enabled() -> bool:
    return cornhub.is_enabled()


def file_part(data: bytes, mime: str) -> dict:
    """Un file (foto, PDF, audio) da mettere tra le ``parts``."""
    return cornhub.file_part(data, mime)


def _translate(exc: cornhub.AIError) -> AIError:
    if isinstance(exc, cornhub.AIOverloaded) or exc.code == "overloaded":
        kind: type[AIError] = AIOverloaded
    elif exc.code in STOP_CODES:
        kind = AIBudgetExceeded
    else:
        kind = AIError
    return kind(exc.message, exc.code, exc.account_url)


# Il massimo che cornhub accetta (GenerateCall.max_output_tokens <= 32000).
# Serve alle risposte lunghe: i modelli Gemini che "pensano" spendono parte del
# budget nel ragionamento, e col default di cornhub (8192) una settimana con
# cinque pasti al giorno o un pezzo di ricettario arrivava troncata.
MAX_OUTPUT_TOKENS = 32_000


def _seconds(timeout_ms: int) -> int:
    # cornhub prova piu' modelli in fila: almeno il suo tempo di default.
    return max(150, timeout_ms // 1000)


def generate[Schema: BaseModel](
    parts: list[str | dict],
    schema: type[Schema],
    *,
    feature: str,
    user=None,
    timeout_ms: int = 60_000,
    temperature: float = 0.2,
    fast: bool = False,
    media_resolution: str = "",
    max_output_tokens: int | None = None,
) -> tuple[Schema, str]:
    """Chiede a cornhub e restituisce ``(risposta validata, modello usato)``.

    ``feature``: il nome nel listino di cornhub (``apps/ai/features.py`` di
    cornhub). ``user``: chi la chiede, decide chi paga. ``fast``: per chi
    aspetta guardando lo schermo (intervista, frigo; ADR 0014).
    ``media_resolution``: "high" per leggere testo piccolo o scritto a mano
    nelle foto e nei PDF. ``max_output_tokens``: per le risposte lunghe (le
    ricette trascritte riga per riga, le settimane del piano); altrimenti il
    default di cornhub.
    """
    extra = {"max_output_tokens": max_output_tokens} if max_output_tokens else {}
    try:
        result = cornhub.generate(
            feature,
            parts,
            schema,
            user=user,
            fast=fast,
            temperature=temperature,
            media_resolution=media_resolution,
            timeout=_seconds(timeout_ms),
            **extra,
        )
    except cornhub.AIError as exc:
        raise _translate(exc) from exc
    return result.data, result.model


def generate_image(
    prompt: str, *, feature: str, user=None, timeout_ms: int = 120_000
) -> tuple[bytes, str, str]:
    """Un'immagine da un testo: ``(byte, tipo, modello)``."""
    try:
        data, mime, result = cornhub.image(feature, prompt, user=user, timeout=_seconds(timeout_ms))
    except cornhub.AIError as exc:
        raise _translate(exc) from exc
    except KeyError as exc:  # risposta senza immagine
        message = "Non e' stato disegnato niente questa volta. Riprova."
        raise AINoImage(message, "overloaded") from exc
    return data, mime, result.model


def live_token(feature: str, config: dict, *, user=None) -> dict:
    """Token monouso di Gemini Live per il browser: ``{"token", "model"}``."""
    try:
        token, result = cornhub.live_token(feature, config, user=user)
    except cornhub.AIError as exc:
        raise _translate(exc) from exc
    return {"token": token, "model": result.model}
