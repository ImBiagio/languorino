"""Funzioni generiche riusate da piu' app.

Niente regole di dominio qui (quelle stanno nelle app): solo gli attrezzi che
servono in piu' punti.
"""

from __future__ import annotations

import hashlib
import secrets

from django.core import signing
from django.template.loader import render_to_string


def normalize_email(value: str) -> str:
    """Le email si confrontano sempre minuscole e senza spazi."""
    return (value or "").strip().lower()


def sign(payload: dict, salt: str) -> str:
    """Token firmato e stateless (verifica email): niente tabella."""
    return signing.dumps(payload, salt=salt)


def unsign(token: str, salt: str, max_age: int) -> dict | None:
    """Il payload di un token firmato, o ``None`` se e' falso o scaduto."""
    try:
        return signing.loads(token, salt=salt, max_age=max_age)
    except signing.BadSignature:
        return None


def send_email(
    to: str,
    subject: str,
    *,
    name: str,
    intro: str,
    cta_label: str,
    cta_url: str,
    body: str = "",
    note: str = "",
) -> None:
    """Mail di servizio con un bottone (testo + HTML, stesso layout per tutte).

    La lingua e' quella attiva: chi chiama la sceglie con
    ``translation.override(<lingua del destinatario>)`` attorno ai testi.

    Parte dal worker Celery dopo il commit: l'SMTP puo' metterci secondi o
    non rispondere, e la richiesta dell'utente non deve aspettarlo. Se la
    transazione fallisce la mail non parte.
    """
    from django.db import transaction

    from .tasks import deliver_email

    context = {
        "subject": subject,
        "name": name,
        "intro": intro,
        "body": body,
        "note": note,
        "cta_label": cta_label,
        "cta_url": cta_url,
    }
    text = render_to_string("emails/base.txt", context)
    html = render_to_string("emails/base.html", context)
    transaction.on_commit(lambda: deliver_email.delay(subject, text, html, to))


def random_token(nbytes: int = 18) -> str:
    """Stringa casuale per URL (link di condivisione, chiavi di chi spunta)."""
    return secrets.token_urlsafe(nbytes)


def hash_secret(value: str) -> str:
    """Hash di un segreto che il server deve solo riconoscere, mai restituire."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
