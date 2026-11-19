"""Client di cornhub: login unico (OIDC) e intelligenza artificiale.

Questo file e' uguale in tutte le app della suite (copiato da templatino):
cambia solo il ``.env``. Due cose passano da qui:

- **login**: l'app non ha password ne' registrazione. Manda l'utente su
  cornhub.it (``authorize_url``), riceve un codice, lo scambia per un
  id_token firmato (``exchange_code``) e lo verifica. Al refresh della
  sessione chiede a cornhub se l'account e' ancora attivo (``user_status``).
- **AI**: l'app non ha chiavi API. Chiede a cornhub (``generate``,
  ``image``, ``live_token``) e cornhub sceglie chi paga: la chiave di casa
  per le funzioni piccole, quella dell'utente per le grandi. Ogni funzione
  deve essere nel listino di cornhub (``apps/ai/features.py``).

Le chiamate da backend a cornhub viaggiano sulla rete interna Docker
"cornhub" (``CORNHUB_INTERNAL_URL``), mai da internet; il browser invece va
su ``CORNHUB_URL``.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt
from django.conf import settings
from django.core.cache import cache
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SCOPES = "openid profile email"


# --------------------------------------------------------------------- login


def _internal(path: str) -> str:
    return f"{settings.CORNHUB_INTERNAL_URL.rstrip('/')}{path}"


def issuer() -> str:
    return f"{settings.CORNHUB_URL.rstrip('/')}/o"


def new_login() -> dict:
    """State, nonce e verificatore PKCE di un login: restano in un cookie
    firmato fino al ritorno da cornhub."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return {
        "state": secrets.token_urlsafe(24),
        "nonce": secrets.token_urlsafe(24),
        "verifier": verifier,
        "challenge": challenge.decode().rstrip("="),
    }


def authorize_url(login: dict, redirect_uri: str) -> str:
    query = urlencode({
        "response_type": "code",
        "client_id": settings.CORNHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": login["state"],
        "nonce": login["nonce"],
        "code_challenge": login["challenge"],
        "code_challenge_method": "S256",
    })
    return f"{issuer()}/authorize/?{query}"


def logout_url(post_logout_redirect: str) -> str:
    query = urlencode({
        "client_id": settings.CORNHUB_CLIENT_ID,
        "post_logout_redirect_uri": post_logout_redirect,
    })
    return f"{issuer()}/logout/?{query}"


class SSOError(Exception):
    pass


def _jwks(refresh: bool = False) -> dict:
    key = "cornhub:jwks"
    data = None if refresh else cache.get(key)
    if data is None:
        response = httpx.get(_internal("/o/.well-known/jwks.json"), timeout=10)
        response.raise_for_status()
        data = response.json()
        cache.set(key, data, 60 * 60)
    return data


def _signing_key(token: str):
    kid = jwt.get_unverified_header(token).get("kid")
    for refresh in (False, True):  # chiave ruotata: si riscarica una volta
        for item in _jwks(refresh).get("keys", []):
            if item.get("kid") == kid:
                return jwt.PyJWK(item).key
    raise SSOError("chiave di firma sconosciuta")


def verify_id_token(token: str, nonce: str) -> dict:
    """Firma RS256, emittente, destinatario, scadenza e nonce: tutto o niente."""
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            audience=settings.CORNHUB_CLIENT_ID,
            issuer=issuer(),
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            leeway=30,
        )
    except jwt.PyJWTError as exc:
        raise SSOError(f"id_token non valido: {exc}") from exc
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise SSOError("nonce diverso")
    return claims


def exchange_code(code: str, verifier: str, redirect_uri: str, nonce: str) -> dict:
    """Codice → id_token verificato (i claim dell'utente)."""
    try:
        response = httpx.post(
            _internal("/o/token/"),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
                "client_id": settings.CORNHUB_CLIENT_ID,
                "client_secret": settings.CORNHUB_CLIENT_SECRET,
            },
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise SSOError("cornhub non risponde") from exc
    if response.status_code != 200:
        raise SSOError(f"scambio del codice rifiutato ({response.status_code})")
    return verify_id_token(response.json().get("id_token", ""), nonce)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.CORNHUB_APP_TOKEN}",
        "X-Cornhub-App": settings.CORNHUB_APP_SLUG,
    }


def user_status(sub: str) -> dict:
    """Stato dell'account su cornhub (cache 2 minuti).

    Solo un guasto di cornhub (rete, 5xx) lascia passare, segnato
    ``unknown``: un riavvio di cornhub non deve buttare fuori tutti, e
    l'account spento perde l'accesso al primo controllo riuscito. Un rifiuto
    (401/403: token dell'app vuoto, sbagliato o app disattivata; 404: utente
    sconosciuto) chiude: altrimenti un errore di configurazione terrebbe
    dentro per sempre chi e' stato spento.
    """
    key = f"cornhub:user:{sub}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        response = httpx.get(_internal(f"/internal/users/{sub}"), headers=_headers(), timeout=5)
    except httpx.HTTPError:
        logger.warning("cornhub non risponde al controllo dell'utente")
        return {"active": True, "allowed": True, "unknown": True}
    if response.status_code >= 500:
        logger.warning("cornhub: stato utente %s", response.status_code)
        return {"active": True, "allowed": True, "unknown": True}
    if response.status_code == 200:
        data = response.json()
    else:
        if response.status_code in (401, 403):
            logger.error("cornhub rifiuta l'app (%s): controlla CORNHUB_APP_TOKEN",
                         response.status_code)
        data = {"active": False, "allowed": False}
    cache.set(key, data, 120)
    return data


# ------------------------------------------------------------------ fra app


class AppLinkError(Exception):
    """L'altra app non si puo' chiamare. ``code``: not_linked (l'utente non
    l'ha mai aperta), denied (coppia non ammessa su cornhub), unavailable
    (cornhub giu': riprovare), disabled (app senza CORNHUB_APP_TOKEN)."""

    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.message = message
        self.code = code


def app_token(audience: str, scope: str, *, user) -> str:
    """Token per chiamare l'app ``audience`` a nome di ``user`` (ADR 0004 di
    scontrino): lo firma cornhub, solo per le coppie ammesse e se l'utente
    le ha aperte tutte e due. Vive 5 minuti: si chiede a ogni invio."""
    sub = _sub(user)
    if not is_enabled() or sub is None:
        raise AppLinkError("cornhub non e' configurato (CORNHUB_APP_TOKEN).", "disabled")
    try:
        response = httpx.post(
            _internal("/internal/apps/token"),
            json={"audience": audience, "user": sub, "scope": scope},
            headers=_headers(),
            timeout=10,
        )
    except httpx.HTTPError as exc:
        raise AppLinkError("cornhub non risponde: riprova tra poco.", "unavailable") from exc
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code == 200 and payload.get("token"):
        return payload["token"]
    code = payload.get("code") or ("unavailable" if response.status_code >= 500 else "denied")
    raise AppLinkError(payload.get("detail") or f"errore {response.status_code}", code)


# ------------------------------------------------------------------------ AI


class AIError(Exception):
    """Errore da mostrare all'utente cosi' com'e'. ``code``: needs_key (serve
    la chiave dell'utente), limit (limite di spesa), house_empty (pannocchie
    o budget di casa finiti), overloaded (riprovare piu' tardi), ..."""

    def __init__(self, message: str, code: str = "error", account_url: str = ""):
        super().__init__(message)
        self.message = message
        self.code = code
        self.account_url = account_url

    @property
    def retry_later(self) -> bool:
        return self.code == "overloaded"


class AIOverloaded(AIError):
    pass


@dataclass
class AIResult:
    data: object
    text: str
    provider: str
    model: str
    billed_to: str
    cost_eur: str
    pannocchie: int


def is_enabled() -> bool:
    return bool(settings.CORNHUB_APP_TOKEN)


def file_part(data: bytes, mime: str) -> dict:
    return {"mime": mime, "data": base64.b64encode(data).decode()}


def _sub(user) -> str | None:
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return str(user.cornhub_sub) if getattr(user, "cornhub_sub", None) else None


def _post(path: str, body: dict, timeout: int):
    if not is_enabled():
        raise AIError("L'intelligenza artificiale non e' configurata (CORNHUB_APP_TOKEN).",
                      "disabled")
    try:
        response = httpx.post(_internal(path), json=body, headers=_headers(), timeout=timeout)
    except httpx.HTTPError as exc:
        raise AIOverloaded("cornhub non risponde: riprova tra poco.", "overloaded") from exc
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code == 200:
        return payload
    detail = payload.get("detail") or f"errore {response.status_code}"
    code = payload.get("code", "error")
    error = AIOverloaded if code == "overloaded" else AIError
    raise error(detail, code, payload.get("account_url", ""))


def _meta(payload: dict, data=None) -> AIResult:
    return AIResult(
        data=data, text=payload.get("text", ""), provider=payload.get("provider", ""),
        model=payload.get("model", ""), billed_to=payload.get("billed_to", ""),
        cost_eur=payload.get("cost_eur", "0"), pannocchie=payload.get("pannocchie", 0),
    )


def generate[Schema: BaseModel](
    feature: str,
    parts: list[str | dict],
    schema: type[Schema] | None = None,
    *,
    user=None,
    system: str = "",
    fast: bool = False,
    temperature: float | None = None,
    max_output_tokens: int = 8192,
    media_resolution: str = "",
    timeout: int = 300,
) -> AIResult:
    """Una richiesta di testo (con foto, PDF o audio da ``file_part``).

    Con ``schema`` (modello pydantic) la risposta e' JSON vincolato a quello
    schema e ``result.data`` e' gia' il modello validato. ``fast``: per chi
    aspetta guardando lo schermo. ``user``: chi la chiede (decide chi paga);
    ``None`` solo per le funzioni pubbliche segnate ``anon_ok`` su cornhub.
    """
    body = {
        "feature": feature,
        "user": _sub(user),
        "fast": fast,
        "system": system,
        "parts": [p if isinstance(p, dict) else {"text": p} for p in parts],
        "json_schema": schema.model_json_schema() if schema else None,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "media_resolution": media_resolution,
    }
    payload = _post("/internal/ai/generate", body, timeout)
    data = payload.get("data")
    if schema is not None:
        try:
            data = schema.model_validate(data)
        except Exception as exc:
            raise AIError("La risposta dell'intelligenza artificiale non e' nel formato atteso.",
                          "bad_output") from exc
    return _meta(payload, data)


def image(
    feature: str, prompt: str, *, user=None, timeout: int = 300
) -> tuple[bytes, str, AIResult]:
    """Un'immagine disegnata: (byte, tipo MIME, dettagli)."""
    body = {"feature": feature, "user": _sub(user), "prompt": prompt}
    payload = _post("/internal/ai/image", body, timeout)
    return base64.b64decode(payload["image"]), payload.get("mime", "image/png"), _meta(payload)


def live_token(feature: str, config: dict, *, user=None) -> tuple[str, AIResult]:
    """Token monouso per una sessione di voce dal vivo (Gemini Live) aperta
    dal browser; la configurazione resta chiusa nel token."""
    payload = _post("/internal/ai/live-token",
                    {"feature": feature, "user": _sub(user), "config": config}, 45)
    return payload["token"], _meta(payload)


def wallet(*, user=None) -> dict:
    """Pannocchie rimaste oggi e chiavi dell'utente, per l'intestazione
    dell'app. Se cornhub non risponde: ``{}`` (il contatore si nasconde)."""
    try:
        response = httpx.get(
            _internal("/internal/ai/wallet"),
            params={"user": _sub(user) or ""},
            headers=_headers(),
            timeout=5,
        )
    except httpx.HTTPError:
        return {}
    return response.json() if response.status_code == 200 else {}


def quote(features: list[str] | dict[str, int], *, user=None, fast: bool = False) -> dict:
    """Stima per l'interfaccia: chi paga e quanto, prima di premere il bottone."""
    items = features.items() if isinstance(features, dict) else ((f, 1) for f in features)
    return _post("/internal/ai/quote", {
        "user": _sub(user), "fast": fast,
        "items": [{"feature": f, "count": n} for f, n in items],
    }, 10)


__all__ = [
    "AIError", "AIOverloaded", "AIResult", "SSOError", "authorize_url", "exchange_code",
    "file_part", "generate", "image", "is_enabled", "live_token", "logout_url",
    "new_login", "quote", "user_status", "wallet",
]
