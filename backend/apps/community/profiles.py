"""Profili pubblici (ADR 0017): ``/u/<handle>`` mostra le ricette pubbliche
di un utente. Il profilo e' pubblico solo se ha almeno una ricetta pubblica:
l'indirizzo puo' esistere, ma senza ricette pubbliche la pagina non si apre."""

from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.methods import random_token
from apps.recipes.models import Recipe

HANDLE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])?$")
# Parole che sembrerebbero pagine dell'app o del sito.
RESERVED = {"admin", "api", "languorino", "staff", "support", "help", "me", "u", "r"}


def validate_handle(value: str, user=None) -> str:
    value = value.strip().lower()
    if not HANDLE.match(value) or len(value) < 3:
        raise serializers.ValidationError(
            _("Da 3 a 40 caratteri: lettere minuscole, numeri e trattini.")
        )
    if value in RESERVED:
        raise serializers.ValidationError(_("Questo nome non si può usare."))
    taken = get_user_model().objects.filter(handle=value)
    if user is not None:
        taken = taken.exclude(pk=user.pk)
    if taken.exists():
        raise serializers.ValidationError(_("Questo nome è già preso."))
    return value


def ensure_handle(user) -> str:
    """L'indirizzo del profilo, creato dal nome visibile la prima volta."""
    if user.handle:
        return user.handle
    base = slugify(user.display_name or "")[:30].strip("-")
    if len(base) < 3 or base in RESERVED:
        base = "cuoco"
    User = get_user_model()
    candidate = base
    while User.objects.filter(handle=candidate).exists():
        candidate = f"{base}-{random_token(3).lower().replace('_', '').replace('-', '')[:4]}"
    user.handle = candidate
    user.save(update_fields=["handle"])
    return candidate


def public_recipes(user):
    return Recipe.objects.filter(
        owner=user,
        visibility=Recipe.Visibility.PUBLIC,
        share_token__isnull=False,
        in_cookbook=True,
    )


def public_handle(user) -> str | None:
    """L'indirizzo del profilo, solo se il profilo e' pubblico."""
    if user.handle and public_recipes(user).exists():
        return user.handle
    return None
