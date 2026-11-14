"""Il piano fatto vedere a un altro account, in sola lettura (ADR 0019).

Si condivide con l'email di chi ha gia' un account. Chi riceve vede il piano
di oggi di chi condivide (``current_plan``), sempre aggiornato, e le sue
ricette; non lo cambia, non ci fa la spesa e non lo copia. Il proprio piano
se lo crea lui. Chi condivide spegne quando vuole, chi riceve puo' toglierlo.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import translation
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.methods import normalize_email, send_email

from .models import PlanShare

# Nel piano condiviso solo le scelte che servono a leggerlo: niente
# obiettivo, note per il generatore o piano del nutrizionista.
VISIBLE_SETTINGS = ("slots", "servings", "prep_mode")


@transaction.atomic
def share_plan(owner, email: str) -> PlanShare:
    email = normalize_email(email or "")
    if email == owner.email:
        raise serializers.ValidationError({"email": _("Il piano è già tuo.")})
    viewer = get_user_model().objects.filter(email=email, is_active=True).first()
    if viewer is None:
        raise serializers.ValidationError(
            {"email": _("Nessun account Languorino con questa email: prima deve registrarsi.")}
        )
    share, created = PlanShare.objects.get_or_create(owner=owner, viewer=viewer)
    if created:
        _notify(share)
    return share


def _notify(share: PlanShare) -> None:
    viewer, owner = share.viewer, share.owner
    with translation.override(viewer.language):
        send_email(
            viewer.email,
            _("%(name)s ti fa vedere il suo piano") % {"name": owner.display_name},
            name=viewer.display_name or viewer.email,
            intro=_(
                "%(name)s ha condiviso con te il suo piano alimentare su %(app)s: "
                "lo vedi così com'è, senza poterlo cambiare."
            )
            % {"name": owner.display_name, "app": settings.APP_NAME},
            cta_label=_("Guarda il piano"),
            cta_url=f"{settings.FRONTEND_BASE_URL}/piano/condivisi/{share.id}",
            note=_("Il tuo piano resta tuo: puoi crearne uno quando vuoi."),
        )


def visible_settings(settings_: dict) -> dict:
    return {key: settings_[key] for key in VISIBLE_SETTINGS if key in settings_}
