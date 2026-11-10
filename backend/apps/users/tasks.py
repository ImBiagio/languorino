from celery import shared_task
from django.core.management import call_command


@shared_task
def flush_expired_tokens() -> None:
    """Toglie dalla blacklist i refresh token scaduti: non servono piu' a niente."""
    call_command("flushexpiredtokens")
