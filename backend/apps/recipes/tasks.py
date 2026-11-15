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

from apps.ai.client import AIError, AINoImage, AIOverloaded

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
# Piu' lungo della pausa massima di un pezzo che aspetta l'AI (8 minuti).
STALLED_AFTER = timedelta(minutes=15)
# AI sovraccarica (cornhub ``overloaded``): il pezzo riprova da solo, con
# pause crescenti. Chiave mancante o limite di spesa invece fermano il
# ricettario col messaggio di cornhub (ADR 0021): aspettare non basta.
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
                feature="book_read",
            )
            with transaction.atomic():
                _save_recipes(book, result["recipes"])
                book.pages_done = end
                book.error = ""
                if end >= book.page_count:
                    book.status = RecipeBook.Status.READY
                    book.finished_at = timezone.now()
                # Solo i campi della lettura: il libro e' stato caricato prima
                # della chiamata all'AI (decine di secondi) e un save() intero
                # riscriverebbe il titolo cambiato nel frattempo dall'utente.
                book.save(
                    update_fields=["pages_done", "error", "status", "finished_at", "updated_at"]
                )
                if book.status == RecipeBook.Status.READING:
                    enqueue_book(book)
                else:
                    # Letto tutto: si cercano le foto delle ricette (ADR 0015).
                    start_book_images(book)
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


# --- immagini delle ricette dei ricettari (ADR 0015) ---------------------------------------

IMAGES_RETRY_PAUSE = 300
NO_IMAGE_RETRIES = 2
NO_IMAGE_PAUSE = 30


def _book_update(book_id: str, **fields) -> None:
    """Aggiorna solo questi campi: il titolo puo' cambiare mentre si lavora."""
    RecipeBook.objects.filter(id=book_id).update(updated_at=timezone.now(), **fields)


def start_book_images(book: RecipeBook) -> None:
    """Riparte da capo: foto dal PDF, poi illustrazioni per le altre."""
    _book_update(
        str(book.id),
        images_status=RecipeBook.ImagesStatus.SEARCHING,
        images_pages_done=0,
        images_found=0,
        images_error="",
        images_skipped=[],
    )
    transaction.on_commit(lambda: find_book_images.delay(str(book.id)))


@shared_task(
    bind=True, soft_time_limit=240, time_limit=270, acks_late=True, reject_on_worker_lost=True
)
def find_book_images(self, book_id: str) -> None:
    """Un gruppo di pagine per task, come la lettura: poi il gruppo dopo."""
    from django.db.models import F

    from .book_images import PAGES_PER_CALL, find_photos

    book = (
        RecipeBook.objects.filter(id=book_id, images_status=RecipeBook.ImagesStatus.SEARCHING)
        .select_related("owner")
        .first()
    )
    if book is None:
        return
    start = book.images_pages_done
    if start >= book.page_count:
        _book_update(book_id, images_status=RecipeBook.ImagesStatus.DRAWING)
        draw_book_image.delay(book_id)
        return
    end = min(start + PAGES_PER_CALL, book.page_count)
    with override(book.language):
        try:
            with book.file.open("rb") as handle:
                data = handle.read()
            found = find_photos(book, data, start, end)
            _book_update(
                book_id,
                images_pages_done=end,
                images_found=F("images_found") + found,
                images_error="",
            )
            find_book_images.delay(book_id)
            return
        except AIOverloaded as exc:
            if self.request.retries < OVERLOAD_RETRIES:
                _book_update(book_id, images_error=str(exc)[:300])
                raise self.retry(
                    countdown=OVERLOAD_PAUSE * (self.request.retries + 1),
                    max_retries=OVERLOAD_RETRIES,
                ) from exc
            error = str(exc)
        except AIError as exc:
            error = str(exc)
        except SoftTimeLimitExceeded:
            error = _("Questa parte del ricettario ci sta mettendo troppo. Riprova.")
        except Exception:
            logger.exception("Foto del ricettario %s non riuscite", book_id)
            error = _("Qualcosa è andato storto. Riprova tra poco.")
    _book_update(book_id, images_status=RecipeBook.ImagesStatus.FAILED, images_error=error[:300])


@shared_task(bind=True, soft_time_limit=200, time_limit=230, acks_late=True)
def draw_book_image(self, book_id: str) -> None:
    """Un'illustrazione per task, poi la ricetta dopo."""
    from .book_images import next_to_draw
    from .images import draw_image

    book = (
        RecipeBook.objects.filter(id=book_id, images_status=RecipeBook.ImagesStatus.DRAWING)
        .select_related("owner")
        .first()
    )
    if book is None:
        return
    recipe = next_to_draw(book)
    if recipe is None:
        _book_update(book_id, images_status=RecipeBook.ImagesStatus.DONE, images_error="")
        return
    with override(book.language):
        try:
            draw_image(recipe, book.owner, style="illustration")
        except AINoImage as exc:
            # Senza immagine per caso: si riprova; poi la ricetta si salta.
            if self.request.retries < NO_IMAGE_RETRIES:
                raise self.retry(countdown=NO_IMAGE_PAUSE, max_retries=NO_IMAGE_RETRIES) from exc
            _skip(book, recipe)
            return
        except AIOverloaded as exc:
            # cornhub segnala cosi' anche "non ha disegnato niente": si
            # riprova piu' tardi, poi la ricetta si salta e si va avanti.
            if self.request.retries < OVERLOAD_RETRIES:
                _book_update(book_id, images_error=str(exc)[:300])
                raise self.retry(
                    countdown=IMAGES_RETRY_PAUSE, max_retries=OVERLOAD_RETRIES
                ) from exc
            _skip(book, recipe)
            return
        except AIError as exc:
            # Serve la chiave dell'utente o il limite di spesa e' raggiunto
            # (ADR 0021): aspettare non basta, ci si ferma con il messaggio.
            _book_update(
                book_id, images_status=RecipeBook.ImagesStatus.FAILED, images_error=str(exc)[:300]
            )
            return
    _book_update(book_id, images_error="")
    draw_book_image.delay(book_id)


def _skip(book: RecipeBook, recipe: Recipe) -> None:
    _book_update(
        str(book.id), images_skipped=[*(book.images_skipped or []), str(recipe.id)]
    )
    draw_book_image.delay(str(book.id))


@shared_task
def resume_book_images() -> int:
    """Riprende foto e illustrazioni rimaste appese (worker riavviato). Non
    c'e' piu' il tetto del giorno da aspettare: i limiti stanno su cornhub."""
    count = 0
    stalled = RecipeBook.objects.filter(updated_at__lt=timezone.now() - STALLED_AFTER)
    for book in stalled.filter(images_status=RecipeBook.ImagesStatus.DRAWING):
        draw_book_image.delay(str(book.id))
        count += 1
    for book in stalled.filter(images_status=RecipeBook.ImagesStatus.SEARCHING):
        find_book_images.delay(str(book.id))
        count += 1
    return count
