"""Generazione del piano sulla coda "ai": una settimana per task (ADR 0007).

Come i ricettari PDF: ogni task fa una settimana, la salva e mette in coda la
successiva; con Gemini sovraccarico aspetta e riprova; un piano fermo da
troppo (worker riavviato) lo riprende ``resume_stalled_plans``.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import override

from apps.ai.client import AIError, AIOverloaded

from .generation import generate_week
from .models import MealPlan

logger = logging.getLogger(__name__)

STALLED_AFTER = timedelta(minutes=15)
OVERLOAD_RETRIES = 4
OVERLOAD_PAUSE = 120


def enqueue_plan(plan: MealPlan) -> None:
    transaction.on_commit(lambda: plan_week.delay(str(plan.id)))


@shared_task(
    bind=True, soft_time_limit=420, time_limit=450, acks_late=True, reject_on_worker_lost=True
)
def plan_week(self, plan_id: str) -> None:
    plan = MealPlan.objects.filter(id=plan_id, status=MealPlan.Status.GENERATING).first()
    if plan is None:
        return
    if plan.weeks_done >= plan.weeks_total:
        plan.status = MealPlan.Status.DRAFT
        plan.finished_at = timezone.now()
        plan.save(update_fields=["status", "finished_at", "updated_at"])
        return
    plan.save(update_fields=["updated_at"])  # segno di vita per resume_stalled_plans
    with override(plan.language):
        try:
            generate_week(plan, plan.weeks_done)
            with transaction.atomic():
                plan.weeks_done += 1
                plan.error = ""
                if plan.weeks_done >= plan.weeks_total:
                    plan.status = MealPlan.Status.DRAFT
                    plan.finished_at = timezone.now()
                plan.save()
                if plan.status == MealPlan.Status.GENERATING:
                    enqueue_plan(plan)
            return
        except AIOverloaded as exc:
            attempt = self.request.retries + 1
            plan.error = str(exc)[:500]
            if attempt <= OVERLOAD_RETRIES:
                plan.save(update_fields=["error", "updated_at"])
                raise self.retry(
                    countdown=OVERLOAD_PAUSE * attempt, max_retries=OVERLOAD_RETRIES
                ) from exc
        except AIError as exc:
            plan.error = str(exc)[:500]
        except SoftTimeLimitExceeded:
            plan.error = _("Questa settimana ci sta mettendo troppo. Riprova.")
        except Exception:
            logger.exception("Generazione del piano %s non riuscita", plan.id)
            plan.error = _("Qualcosa è andato storto. Riprova tra poco.")
    plan.status = MealPlan.Status.FAILED
    plan.save(update_fields=["status", "error", "updated_at"])


@shared_task
def resume_stalled_plans() -> int:
    stalled = MealPlan.objects.filter(
        status=MealPlan.Status.GENERATING, updated_at__lt=timezone.now() - STALLED_AFTER
    )
    count = 0
    for plan in stalled:
        plan.save(update_fields=["updated_at"])
        plan_week.delay(str(plan.id))
        count += 1
    return count
