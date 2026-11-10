from __future__ import annotations

import smtplib

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives


@shared_task(
    autoretry_for=(OSError, smtplib.SMTPException),
    retry_backoff=30,
    max_retries=4,
)
def deliver_email(subject: str, text: str, html: str, to: str) -> None:
    """Invio vero: se l'SMTP e' giu' riprova con attesa crescente (30 s, 1, 2, 4 min)."""
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to])
    message.attach_alternative(html, "text/html")
    message.send()
