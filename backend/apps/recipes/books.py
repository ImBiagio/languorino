"""Lettura di un ricettario PDF a pezzi (ADR 0006).

Mandare a Gemini un PDF lungo tutto insieme non funziona: il modello si ferma
presto e trascrive una ricetta sola. Qui il PDF si divide in gruppi di
``BOOK_PAGES_PER_CHUNK`` pagine, ognuno con la pagina dopo come contesto, e
si chiede di trascrivere solo le ricette che *iniziano* nel gruppo: una
ricetta a cavallo di due gruppi si legge per intero una volta sola.
"""

from __future__ import annotations

import io

from django.conf import settings
from django.utils.translation import gettext as _
from pypdf import PdfReader, PdfWriter


class BookRejected(ValueError):
    pass


def page_count(data: bytes) -> int:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise BookRejected(_("Il PDF è protetto da password."))
        return len(reader.pages)
    except BookRejected:
        raise
    except Exception as exc:
        raise BookRejected(_("Il PDF non si apre: è danneggiato o non è un PDF.")) from exc


def chunk_bounds(start: int, total: int) -> tuple[int, int, bool]:
    """``(inizio, fine, c'e' la pagina di contesto)`` del pezzo che parte da ``start``."""
    end = min(start + settings.BOOK_PAGES_PER_CHUNK, total)
    return start, end, end < total


def extract_pages(data: bytes, start: int, end: int, with_context: bool) -> bytes:
    """Le pagine ``[start, end)`` (piu' la successiva, se c'e') come PDF a se'."""
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    last = end + 1 if with_context else end
    for index in range(start, last):
        writer.add_page(reader.pages[index])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def chunk_instructions(start: int, end: int, total: int, with_context: bool) -> str:
    """La parte del prompt che spiega quale pezzo del ricettario si sta leggendo."""
    pages = end - start
    text = (
        f"\n\nQuesto PDF contiene le pagine da {start + 1} a {end} di un ricettario di "
        f"{total} pagine"
    )
    if with_context:
        text += (
            f", piu' la pagina {end + 1} SOLO come contesto. Le pagine da trascrivere "
            f"sono le prime {pages} del file; l'ultima serve solo a completare una "
            "ricetta che inizia prima e continua li'."
        )
    else:
        text += "."
    text += (
        "\nTrascrivi TUTTE e SOLO le ricette che INIZIANO nelle pagine da trascrivere, "
        "anche se continuano nella pagina di contesto. Non trascrivere la parte finale "
        "di una ricetta iniziata prima di queste pagine, ne' una ricetta che inizia "
        "nella pagina di contesto. Indici, introduzioni e pagine senza ricette non "
        "producono niente."
    )
    return text
