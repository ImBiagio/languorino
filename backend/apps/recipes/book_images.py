"""Immagini delle ricette dei ricettari PDF (ADR 0015).

1. **Foto dal PDF.** Dopo la lettura (o a richiesta, per i ricettari gia'
   letti) si rimandano a Gemini le pagine, a gruppi, con l'elenco dei titoli:
   per ogni ricetta che ha nelle pagine una foto o un'illustrazione del piatto
   pronto risponde pagina e riquadro. Il codice disegna la pagina (pypdfium2:
   PDF scansionati o digitali allo stesso modo), ritaglia il riquadro e lo
   salva come immagine della ricetta (``image_source=book``). Decorazioni,
   intestazioni ripetute e disegni di ingredienti sparsi non contano: il primo
   PDF vero aveva in ogni pagina la stessa testata di legumi disegnati.
2. **Illustrazione AI.** Le ricette rimaste senza immagine si fanno disegnare
   (stile semplice, un po' illustrativo), una alla volta e nel tetto
   giornaliero; il giorno dopo si riprende. Senza quota per le immagini (piano
   gratuito) ci si ferma con un messaggio chiaro.
"""

from __future__ import annotations

import io

from django.conf import settings
from pydantic import BaseModel, Field

from apps.ai.client import generate

from .images import set_image
from .matching import normalize
from .models import Recipe, RecipeBook

# Pagine per chiamata: poche, perche' il riquadro deve essere preciso.
PAGES_PER_CALL = 4
# Riquadro minimo e massimo rispetto alla pagina: sotto e' un'icona, sopra e'
# la pagina intera (sfondo, scansione) e non una foto del piatto.
MIN_AREA, MAX_AREA = 0.02, 0.8
RENDER_SCALE = 2  # ~144 dpi: abbastanza per una foto da card
MAX_TITLES = 300


class BookPhoto(BaseModel):
    title: str = Field(description="Il titolo della ricetta, come nell'elenco")
    page: int = Field(description="Numero della pagina NEL FILE allegato, da 1")
    box: list[int] = Field(
        description="Riquadro della foto: [ymin, xmin, ymax, xmax] normalizzati 0-1000"
    )


class BookPhotos(BaseModel):
    photos: list[BookPhoto] = Field(default_factory=list)


PROMPT = """Il file allegato contiene alcune pagine di un ricettario. Queste sono le
ricette del ricettario:
{titles}

Per ogni ricetta dell'elenco che in queste pagine ha una FOTOGRAFIA o
un'ILLUSTRAZIONE DEL PIATTO PRONTO, dimmi la pagina (contando da 1 nel file
allegato) e il riquadro dell'immagine come [ymin, xmin, ymax, xmax] con
coordinate normalizzate da 0 a 1000. Un'immagine appartiene a UNA sola
ricetta: quella il cui titolo e testo le stanno accanto nella stessa pagina.

NON contano: decorazioni, cornici, intestazioni o testate ripetute in ogni
pagina, loghi, icone, disegni di ingredienti sparsi, sfondi, foto di persone.
Se una ricetta non ha una sua immagine del piatto, non metterla. Se nessuna
ce l'ha, lista vuota. Usa i titoli esattamente come nell'elenco."""


def render_page(data: bytes, index: int):
    """La pagina ``index`` (da 0) del PDF come immagine PIL."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(data)
    try:
        return document[index].render(scale=RENDER_SCALE).to_pil()
    finally:
        document.close()


def crop(image, box: list[int]) -> bytes | None:
    """Il riquadro normalizzato 0-1000 ritagliato dalla pagina, in JPEG; None se
    il riquadro non e' plausibile per una foto di un piatto."""
    if len(box) != 4:
        return None
    ymin, xmin, ymax, xmax = (max(0, min(1000, value)) for value in box)
    if ymax <= ymin or xmax <= xmin:
        return None
    area = (ymax - ymin) * (xmax - xmin) / 1_000_000
    if not MIN_AREA <= area <= MAX_AREA:
        return None
    width, height = image.size
    region = image.crop(
        (xmin * width // 1000, ymin * height // 1000, xmax * width // 1000, ymax * height // 1000)
    )
    out = io.BytesIO()
    region.convert("RGB").save(out, "JPEG", quality=90)
    return out.getvalue()


def find_photos(book: RecipeBook, data: bytes, start: int, end: int) -> int:
    """Cerca le foto nelle pagine ``[start, end)``; restituisce quante ne salva."""
    from .books import extract_pages

    recipes = list(book.recipes.order_by("created_at"))
    waiting = {normalize(recipe.title): recipe for recipe in recipes if not recipe.image}
    if not waiting:
        return 0
    # Tutti i titoli, non solo quelli senza immagine: con un elenco parziale
    # Gemini attribuiva la sola foto della pagina all'unico titolo rimasto
    # (provato il 2026-11-11: la pasta e fagioli finita sulla zuppa di farro).
    titles = "\n".join(f"- {recipe.title}" for recipe in recipes[:MAX_TITLES])
    part = extract_pages(data, start, end, with_context=False)
    result, _model = generate(
        lambda types: [
            types.Part.from_bytes(data=part, mime_type="application/pdf"),
            PROMPT.format(titles=titles),
        ],
        BookPhotos,
        feature="book_photos",
        user=book.owner,
        timeout_ms=120_000,
        temperature=0.1,
    )
    pages: dict[int, object] = {}
    used: set[tuple] = set()
    saved = 0
    known = {normalize(recipe.title) for recipe in recipes}
    for photo in result.photos:
        key = normalize(photo.title)
        if key not in known or not 1 <= photo.page <= end - start:
            continue
        # Lo stesso riquadro per due ricette vale solo per la prima, anche se
        # quella ha gia' un'immagine: la foto e' sua, non della seconda.
        spot = (photo.page, tuple(photo.box))
        if spot in used:
            continue
        used.add(spot)
        recipe = waiting.get(key)
        if recipe is None:
            continue
        index = start + photo.page - 1
        if index not in pages:
            pages[index] = render_page(data, index)
        cropped = crop(pages[index], photo.box)
        if cropped is None:
            continue
        set_image(recipe, cropped, Recipe.ImageSource.BOOK)
        waiting.pop(normalize(photo.title))
        saved += 1
    return saved


def next_to_draw(book: RecipeBook) -> Recipe | None:
    return (
        book.recipes.filter(image="")
        .exclude(id__in=book.images_skipped or [])
        .order_by("created_at")
        .first()
    )


def missing_count(book: RecipeBook) -> int:
    return book.recipes.filter(image="").count()


def daily_left(user) -> int:
    from .images import images_today

    return max(0, settings.AI_IMAGES_PER_DAY - images_today(user))
