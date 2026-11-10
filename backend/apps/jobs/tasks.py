from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import override

from apps.ai.client import AIError

from .models import Job, JobFile

logger = logging.getLogger(__name__)


def _import_recipes(job: Job) -> None:
    from apps.recipes.importing import read_recipes

    files = []
    for item in job.files.all():
        with item.file.open("rb") as handle:
            files.append((handle.read(), item.content_type))
    language = job.input.get("language", "it")
    result = read_recipes(files, user=job.owner, language=language)
    job.model = result.pop("model", "")
    job.result = result


def _fridge_scan(job: Job) -> None:
    from apps.kitchen.cook_today import read_fridge

    files = []
    for item in job.files.all():
        with item.file.open("rb") as handle:
            files.append((handle.read(), item.content_type))
    result = read_fridge(files, user=job.owner, language=job.input.get("language", "it"))
    job.model = result.pop("model", "")
    job.result = result


def _cook_ideas(job: Job) -> None:
    from apps.kitchen.cook_today import write_ideas
    from apps.recipes.serializers import RecipeListSerializer

    options = job.input
    ideas = write_ideas(
        job.owner,
        options.get("ingredients", []),
        slot=options.get("slot"),
        minutes=options.get("minutes"),
        servings=options.get("servings", 2),
        language=options.get("language", "it"),
    )
    job.result = {"ideas": RecipeListSerializer(ideas, many=True, context={}).data}


RUNNERS = {
    Job.Kind.IMPORT_RECIPES: _import_recipes,
    Job.Kind.FRIDGE_SCAN: _fridge_scan,
    Job.Kind.COOK_IDEAS: _cook_ideas,
}


@shared_task(soft_time_limit=300, time_limit=330, acks_late=True, reject_on_worker_lost=True)
def run_job(job_id: str) -> None:
    """Esegue un job in coda. Gli errori finiscono in ``Job.error``, non in Sentry."""
    job = Job.objects.filter(id=job_id, status=Job.Status.QUEUED).select_related("owner").first()
    if job is None:
        return
    job.status = Job.Status.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])
    # I messaggi d'errore nella lingua di chi ha avviato il lavoro.
    with override(job.input.get("language", "it")):
        try:
            RUNNERS[job.kind](job)
            job.status = Job.Status.READY
            job.error = ""
        except AIError as exc:
            job.status = Job.Status.FAILED
            job.error = str(exc)[:500]
        except SoftTimeLimitExceeded:
            job.status = Job.Status.FAILED
            job.error = _("Ci sta mettendo troppo: riprova con meno pagine alla volta.")
        except Exception:
            logger.exception("Job %s non riuscito", job.id)
            job.status = Job.Status.FAILED
            job.error = _("Qualcosa è andato storto. Riprova tra poco.")
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error", "result", "model", "finished_at", "updated_at"])


@shared_task
def clean_jobs() -> None:
    """File degli import vecchi via dal disco; lavori appesi chiusi come non riusciti."""
    old = timezone.now() - timedelta(days=settings.JOB_FILES_KEEP_DAYS)
    for item in JobFile.objects.filter(created_at__lt=old):
        item.file.delete(save=False)
        item.delete(hard=True)
    stuck = timezone.now() - timedelta(hours=1)
    Job.objects.filter(
        status__in=[Job.Status.QUEUED, Job.Status.RUNNING], updated_at__lt=stuck
    ).update(status=Job.Status.FAILED, error=_("Il lavoro si è interrotto. Riprova."))
