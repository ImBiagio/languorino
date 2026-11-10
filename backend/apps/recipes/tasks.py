"""Lettura dei ricettari PDF sulla coda "ai": un pezzo per task (ADR 0006).

Ogni task legge un gruppo di pagine, salva le ricette trovate e mette in coda
il pezzo dopo. Cosi' un ricettario lungo non sfora il tempo di un task, le
ricette compaiono man mano e un errore si riprende dalla pagina a cui si era.
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

from .books import chunk_bounds, chunk_instructions, extract_pages
from .importing import read_recipes
from .matching import normalize
from .models import Recipe, RecipeBook

logger = logging.getLogger(__name__)


def enqueue_book(book: RecipeBook) -> None:
    transaction.on_commit(lambda: read_book_chunk.delay(str(book.id)))


def _save_recipes(book: RecipeBook, drafts: list[dict]) -> int:
    """Le ricette lette diventano ricette del ricettario PDF (non dell'utente)."""
    from .serializers import RecipeSerializer

    seen = {normalize(title) for title in book.recipes.values_list("title", flat=True)}
    saved = 0
    for draft in drafts:
        key = normalize(draft["title"])
        if not key or key in seen:
            continue  # la stessa ricetta letta due volte (pagina di contesto)
        serializer = RecipeSerializer(data=draft, context={})
        if not serializer.is_valid():
            logger.warning("Ricetta del ricettario %s scartata: %s", book.id, serializer.errors)
            continue
        serializer.save(
            owner=book.owner,
            book=book,
            in_cookbook=False,
            status=Recipe.Status.DRAFT,
            source=Recipe.Source.PDF,
        )
        seen.add(key)
        saved += 1
    return saved


# Un pezzo che non avanza da cosi' tanto e' stato perso (worker riavviato da un
# deploy o dall'autoreload): lo riprende resume_stalled_books.
# Piu' lungo della pausa massima di un pezzo che aspetta Gemini (8 minuti).
STALLED_AFTER = timedelta(minutes=15)
# Gemini sovraccarico: il pezzo riprova da solo, con pause crescenti.
OVERLOAD_RETRIES = 4
OVERLOAD_PAUSE = 120  # secondi, moltiplicati per il numero del tentativo


# acks_late: il messaggio si conferma a fine lavoro, cosi' un worker che muore
# a meta' non se lo porta via (Redis lo riconsegna).
@shared_task(
    bind=True, soft_time_limit=240, time_limit=270, acks_late=True, reject_on_worker_lost=True
)
def read_book_chunk(self, book_id: str) -> None:
    book = (
        RecipeBook.objects.filter(
            id=book_id, status__in=[RecipeBook.Status.QUEUED, RecipeBook.Status.READING]
        )
        .select_related("owner")
        .first()
    )
    if book is None:
        return
    if book.pages_done >= book.page_count:
        book.status = RecipeBook.Status.READY
        book.finished_at = timezone.now()
        book.save(update_fields=["status", "finished_at", "updated_at"])
        return

    book.status = RecipeBook.Status.READING
    book.save(update_fields=["status", "updated_at"])
    start, end, with_context = chunk_bounds(book.pages_done, book.page_count)
    with override(book.language):
        try:
            with book.file.open("rb") as handle:
                data = handle.read()
            part = extract_pages(data, start, end, with_context)
            result = read_recipes(
                [(part, "application/pdf")],
                user=book.owner,
                language=book.language,
                extra_instructions=chunk_instructions(start, end, book.page_count, with_context),
            )
            with transaction.atomic():
                _save_recipes(book, result["recipes"])
                book.pages_done = end
                book.error = ""
                if end >= book.page_count:
                    book.status = RecipeBook.Status.READY
                    book.finished_at = timezone.now()
                book.save()
                if book.status == RecipeBook.Status.READING:
                    enqueue_book(book)
            return
        except AIOverloaded as exc:
            attempt = self.request.retries + 1
            if attempt <= OVERLOAD_RETRIES:
                # Resta "in lettura": l'errore dice all'utente che e' in pausa.
                book.error = str(exc)[:500]
                book.save(update_fields=["error", "updated_at"])
                raise self.retry(
                    countdown=OVERLOAD_PAUSE * attempt, max_retries=OVERLOAD_RETRIES
                ) from exc
            book.error = str(exc)[:500]
        except AIError as exc:
            book.error = str(exc)[:500]
        except SoftTimeLimitExceeded:
            book.error = _("Questa parte del ricettario ci sta mettendo troppo. Riprova.")
        except Exception:
            logger.exception("Lettura del ricettario %s non riuscita", book.id)
            book.error = _("Qualcosa è andato storto. Riprova tra poco.")
    book.status = RecipeBook.Status.FAILED
    book.save(update_fields=["status", "error", "updated_at"])


@shared_task
def resume_stalled_books() -> int:
    """Rimette in coda le letture ferme da troppo tempo, dalla pagina a cui erano."""
    stalled = RecipeBook.objects.filter(
        status__in=[RecipeBook.Status.QUEUED, RecipeBook.Status.READING],
        updated_at__lt=timezone.now() - STALLED_AFTER,
    )
    count = 0
    for book in stalled:
        book.status = RecipeBook.Status.QUEUED
        book.save(update_fields=["status", "updated_at"])
        read_book_chunk.delay(str(book.id))
        count += 1
    if count:
        logger.info("Riprese %s letture di ricettari ferme", count)
    return count
