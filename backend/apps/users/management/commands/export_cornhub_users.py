"""Esporta gli utenti per portarli su cornhub (una volta, al passaggio; ADR 0021).

    docker compose exec -T backend python manage.py export_cornhub_users > utenti.json

Su cornhub: ``manage.py import_users utenti.json --app languorino``. Dentro ci
sono gli hash delle password (non le password): il file resta sul server e
si cancella appena importato. Le password funzionano uguali su cornhub
(stesso formato di Django) e si aggiornano ad argon2 al primo login.

Nome e cognome: quelli del profilo alimentare se l'utente li ha scritti,
altrimenti dal nome visibile (prima parola = nome, il resto = cognome).
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.profiles.models import Profile


def _split(name: str) -> tuple[str, str]:
    first, _, last = (name or "").strip().partition(" ")
    return first, last.strip()


def _last_seen(user):
    """L'ultimo accesso vero: il login JWT non aggiorna ``last_login``, ma
    ogni login e ogni rinnovo della sessione emette un refresh token. Su
    cornhub serve a far vincere la password dell'app usata per ultima."""
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

    token = OutstandingToken.objects.filter(user=user).order_by("-created_at").first()
    seen = [d for d in (user.last_login, token.created_at if token else None) if d]
    return max(seen).isoformat() if seen else None


class Command(BaseCommand):
    help = "Stampa in JSON gli utenti da importare su cornhub."

    def handle(self, *args, **options):
        names = {
            user_id: (first.strip(), last.strip())
            for user_id, first, last in Profile.objects.values_list(
                "user_id", "first_name", "last_name"
            )
        }
        out = []
        for user in get_user_model().objects.order_by("date_joined"):
            first, last = names.get(user.pk, ("", ""))
            if not first and not last:
                first, last = _split(user.display_name)
            out.append({
                "email": user.email,
                "password": user.password if user.has_usable_password() else "",
                "first_name": first,
                "last_name": last,
                "display_name": user.display_name,
                "language": user.language,
                "email_verified": user.email_verified_at is not None,
                "is_active": user.is_active,
                "date_joined": user.date_joined.isoformat(),
                "last_login": _last_seen(user),
            })
        self.stdout.write(json.dumps(out, ensure_ascii=False, indent=1))
