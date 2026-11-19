"""Invii a Scontrino in background (ADR 0026): i rinvii dopo un cambio di
pasti e la pulizia quando un piano si elimina. Con Scontrino o cornhub giu'
si riprova qualche volta; se l'utente non ha mai aperto Scontrino no."""

from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.plans.models import MealPlan

from . import scontrino

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=4, default_retry_delay=120)
def push_plan_to_scontrino(self, plan_id: str) -> None:
    plan = (
        MealPlan.objects.select_related("owner")
        .filter(pk=plan_id, scontrino_sent_at__isnull=False)
        .first()
    )
    if plan is None:  # eliminato nel frattempo, o mai mandato
        return
    try:
        scontrino.push_plan(plan)
    except scontrino.ScontrinoError as exc:
        if exc.code == "unavailable":
            raise self.retry(exc=exc) from exc
        logger.warning("piano non rimandato a scontrino: %s", exc.code)


@shared_task(bind=True, max_retries=4, default_retry_delay=120)
def remove_plan_from_scontrino(self, plan_id: str, owner_id) -> None:
    owner = get_user_model().objects.filter(pk=owner_id).first()
    if owner is None:
        return
    try:
        scontrino.remove_plan(plan_id, owner)
    except scontrino.ScontrinoError as exc:
        if exc.code == "unavailable":
            raise self.retry(exc=exc) from exc
        logger.warning("piano non tolto da scontrino: %s", exc.code)
