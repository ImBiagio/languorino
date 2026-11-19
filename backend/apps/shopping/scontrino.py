"""Il cibo del piano va nella lista di Scontrino (ADR 0026).

Scontrino tiene la spesa della casa: cibo, cose per la casa, ricorrenti
(ADR 0004 di scontrino). Languorino gli manda solo il **cibo del piano**,
tutto insieme e sempre con lo stesso riferimento ``plan:<id>``: a ogni invio
Scontrino sostituisce solo quelle righe e lascia stare quelle scritte a mano
o cambiate a mano. Per questo si puo' rimandare quante volte si vuole: dopo
il primo invio ogni cambio di pasti si rimanda da solo (``schedule_push``).

Le chiamate sono da server a server, a nome del proprietario del piano, con
un token d'app chiesto a cornhub (``cornhub.app_token``): niente segreti
condivisi fra le app. I ricorrenti non si mandano: in Scontrino sono della
casa. Nemmeno i basilari (sale, olio, pepe), che si danno per gia' in casa.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import httpx
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import formats, timezone
from django.utils.translation import gettext as _
from django.utils.translation import override

from apps.core import cornhub
from apps.plans.models import MealPlan

from .aggregate import build_items, plan_meals

logger = logging.getLogger(__name__)

AUDIENCE = "scontrino"
SCOPE = "shopping:food"
# Dopo un cambio di pasti si aspetta un po': una sostituzione o un piano che
# si rigenera cambiano tanti pasti di fila, e basta un invio per tutti.
PUSH_DELAY = 20


class ScontrinoError(Exception):
    """``code``: not_linked (l'utente non ha mai aperto Scontrino),
    unavailable (Scontrino o cornhub giu': si riprova), disabled, error."""

    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.message = message
        self.code = code


def is_enabled() -> bool:
    return bool(settings.SCONTRINO_INTERNAL_URL) and cornhub.is_enabled()


def plan_ref(plan_id) -> str:
    return f"plan:{plan_id}"


def plan_label(plan: MealPlan) -> str:
    """Cosa si legge in Scontrino accanto alle voci: "Piano dal 16 al 22 novembre"."""

    def day(value, fmt="j F"):
        text = formats.date_format(value, fmt)
        # In italiano i mesi vanno minuscoli; Django li scrive con la maiuscola.
        return text.lower() if plan.language.startswith("it") else text

    end = plan.start_date + timedelta(days=plan.days - 1)
    same_month = (plan.start_date.year, plan.start_date.month) == (end.year, end.month)
    with override(plan.language or "it"):
        # "dal 16 al 22 novembre"; a cavallo di due mesi "dal 28 novembre al 4 dicembre".
        return _("Piano dal %(start)s al %(end)s") % {
            "start": day(plan.start_date, "j" if same_month else "j F"),
            "end": day(end),
        }


def food_items(plan: MealPlan) -> list[dict]:
    """Il cibo di tutto il piano, sommato come nella spesa di Languorino."""
    end = plan.start_date + timedelta(days=plan.days - 1)
    items = build_items(list(plan_meals(plan, plan.start_date, end)))
    return [
        {
            "label": item["label"],
            "quantity": None if item["quantity"] is None else str(item["quantity"]),
            "unit": item["unit"],
            # I reparti di Languorino hanno gia' le chiavi di Scontrino.
            "department": item["category"],
        }
        for item in items
        if not item["in_pantry"]
    ]


def _call(method: str, path: str, *, user, json: dict | None = None) -> dict:
    if not is_enabled():
        raise ScontrinoError(_("Scontrino non è collegato."), "disabled")
    try:
        token = cornhub.app_token(AUDIENCE, SCOPE, user=user)
    except cornhub.AppLinkError as exc:
        if exc.code == "not_linked":
            raise ScontrinoError(
                _("Apri Scontrino una volta con il tuo account, poi riprova."), "not_linked"
            ) from exc
        code = "unavailable" if exc.code == "unavailable" else "error"
        logger.warning("token per scontrino rifiutato: %s (%s)", exc.message, exc.code)
        raise ScontrinoError(_("Scontrino non risponde: riprova tra poco."), code) from exc
    try:
        response = httpx.request(
            method,
            f"{settings.SCONTRINO_INTERNAL_URL.rstrip('/')}{path}",
            json=json,
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
    except httpx.HTTPError as exc:
        raise ScontrinoError(_("Scontrino non risponde: riprova tra poco."), "unavailable") from exc
    if response.status_code == 409:
        raise ScontrinoError(
            _("Apri Scontrino una volta con il tuo account, poi riprova."), "not_linked"
        )
    if response.status_code >= 500:
        raise ScontrinoError(_("Scontrino non risponde: riprova tra poco."), "unavailable")
    if response.status_code >= 400:
        logger.warning("scontrino rifiuta %s %s: %s", method, path, response.status_code)
        raise ScontrinoError(_("Scontrino ha rifiutato la richiesta."), "error")
    return response.json()


def push_plan(plan: MealPlan, *, new_list: bool = False) -> dict:
    """Manda (o rimanda) il cibo del piano. Va nella lista dove c'e' gia', se
    ancora aperta, altrimenti nell'ultima lista aperta della casa o in una nuova
    (lo decide Scontrino)."""
    body = {
        "ref": plan_ref(plan.id),
        "label": plan_label(plan),
        "items": food_items(plan),
        "days": plan.days,
    }
    if new_list:
        body["new_list"] = True
    data = _call("PUT", "/api/suite/food", user=plan.owner, json=body)
    shopping_list = data.get("list") or {}
    plan.scontrino_sent_at = timezone.now()
    plan.scontrino_list_title = str(shopping_list.get("title", ""))[:120]
    plan.scontrino_list_url = str(shopping_list.get("url", ""))[:300]
    plan.save(update_fields=["scontrino_sent_at", "scontrino_list_title", "scontrino_list_url"])
    return data


def remove_plan(plan_id, user) -> int:
    """Il piano non c'e' piu': via le sue righe da Scontrino (restano quelle
    cambiate a mano)."""
    return _call("DELETE", f"/api/suite/food/{plan_ref(plan_id)}", user=user).get("removed", 0)


def schedule_push(plan_id) -> None:
    """Dopo il commit, se il piano e' gia' stato mandato, lo rimanda tra poco.
    Un invio solo per una raffica di cambi (chiave in cache per il ritardo)."""

    def enqueue():
        if not MealPlan.objects.filter(pk=plan_id, scontrino_sent_at__isnull=False).exists():
            return
        if not cache.add(f"scontrino:push:{plan_id}", 1, PUSH_DELAY + 10):
            return
        from .tasks import push_plan_to_scontrino

        push_plan_to_scontrino.apply_async((str(plan_id),), countdown=PUSH_DELAY)

    transaction.on_commit(enqueue)
