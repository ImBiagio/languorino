"""Le mail dell'account: conferma dell'indirizzo e reset della password."""

from __future__ import annotations

from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext as _

from apps.core.methods import send_email

from .tokens import email_verification_url, password_reset_url


def _name(user) -> str:
    return user.display_name or user.email


def send_verification_email(user) -> None:
    with translation.override(user.language):
        send_email(
            user.email,
            _("Conferma il tuo indirizzo email"),
            name=_name(user),
            intro=_(
                "Manca un passo: conferma che questo indirizzo e' tuo e il tuo account "
                "%(app)s e' pronto."
            )
            % {"app": settings.APP_NAME},
            cta_label=_("Conferma email"),
            cta_url=email_verification_url(user),
            note=_(
                "Il link vale 3 giorni e una volta sola. Se non ti sei registrato tu, "
                "ignora questa mail."
            ),
        )


def send_password_reset_email(user) -> None:
    with translation.override(user.language):
        send_email(
            user.email,
            _("Reimposta la password di %(app)s") % {"app": settings.APP_NAME},
            name=_name(user),
            intro=_(
                "Qualcuno (speriamo tu) ha chiesto di reimpostare la password del tuo "
                "account %(app)s."
            )
            % {"app": settings.APP_NAME},
            cta_label=_("Scegli una nuova password"),
            cta_url=password_reset_url(user),
            note=_(
                "Il link vale 2 ore e una volta sola. Se non l'hai chiesto tu, ignora "
                "questa mail: la password resta quella di prima."
            ),
        )
