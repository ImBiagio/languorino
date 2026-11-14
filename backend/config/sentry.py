"""Segnalazione degli errori a GlitchTip (stesso protocollo di Sentry).

Si accende solo con ``SENTRY_DSN``: senza, l'SDK non viene nemmeno importato.
La chiamano i settings di sviluppo e di produzione, mai quelli dei test. I
settings li caricano gunicorn, i worker Celery e beat: basta questo perche'
arrivino le eccezioni non gestite delle richieste e dei task.
"""

from __future__ import annotations


def init_sentry(dsn: str, environment: str = "production") -> bool:
    """Avvia l'SDK se c'e' un DSN. Restituisce se l'ha fatto."""
    dsn = (dsn or "").strip()
    if not dsn:
        return False

    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=environment or "production",
        integrations=[DjangoIntegration(), CeleryIntegration()],
        # Solo errori: niente tracce delle prestazioni.
        traces_sample_rate=0,
        # Niente email, IP, cookie o intestazioni dell'utente negli eventi.
        send_default_pii=False,
        # Qui passano dati sulla salute (profilo, piano del nutrizionista,
        # testo delle interviste): fuori dall'app non devono uscire ne' il
        # corpo delle richieste ne' le variabili locali dello stack.
        max_request_body_size="never",
        include_local_variables=False,
    )
    return True
