"""Controllo e preparazione dei file caricati per un job.

Il tipo si riconosce dai primi byte, non dall'estensione o dal content type
che manda il browser. Le foto grandi si riducono e si salvano senza i dati
EXIF (posizione GPS compresa): a Gemini serve leggere, non sapere dove.
"""

from __future__ import annotations

import io

from django.conf import settings
from django.utils.translation import gettext as _
from PIL import Image, ImageOps

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
PDF = "application/pdf"


class FileRejected(ValueError):
    pass


def sniff(head: bytes) -> str | None:
    """Il tipo vero del file dai primi byte, o None se non e' uno di quelli ammessi."""
    if head.startswith(b"%PDF-"):
        return PDF
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in {b"heic", b"heix", b"hevc", b"heim", b"heis"}:
            return "image/heic"
        if brand in {b"mif1", b"msf1"}:
            return "image/heif"
    return None


def _shrink(data: bytes) -> tuple[bytes, str]:
    """Foto ridotta al lato massimo e ruotata come nel telefono, senza EXIF."""
    with Image.open(io.BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((settings.JOB_IMAGE_MAX_SIDE, settings.JOB_IMAGE_MAX_SIDE))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        out = io.BytesIO()
        image.save(out, "JPEG", quality=85, optimize=True)
        return out.getvalue(), "image/jpeg"


def prepare(uploads) -> list[tuple[bytes, str, str]]:
    """``(contenuto, tipo, nome originale)`` per ogni file, o ``FileRejected``."""
    if not uploads:
        raise FileRejected(_("Carica almeno una foto o un PDF."))
    if len(uploads) > settings.JOB_MAX_FILES:
        raise FileRejected(_("Al massimo %(n)d file alla volta.") % {"n": settings.JOB_MAX_FILES})
    prepared = []
    total = 0
    for upload in uploads:
        data = upload.read()
        kind = sniff(data[:16])
        name = (getattr(upload, "name", "") or "")[:200]
        if kind is None:
            raise FileRejected(
                _("“%(name)s” non è una foto (JPEG, PNG, WebP, HEIC) né un PDF.") % {"name": name}
            )
        limit = settings.JOB_MAX_PDF_BYTES if kind == PDF else settings.JOB_MAX_IMAGE_BYTES
        if len(data) > limit:
            raise FileRejected(
                _("“%(name)s” è troppo grande (massimo %(mb)d MB).")
                % {"name": name, "mb": limit // (1024 * 1024)}
            )
        # HEIC resta com'e' (Pillow non lo apre, Gemini si'); le altre foto si riducono.
        if kind in {"image/jpeg", "image/png", "image/webp"}:
            try:
                data, kind = _shrink(data)
            except Exception as exc:
                raise FileRejected(
                    _("“%(name)s” non si apre come immagine.") % {"name": name}
                ) from exc
        total += len(data)
        prepared.append((data, kind, name))
    if total > settings.JOB_MAX_TOTAL_BYTES:
        raise FileRejected(
            _("I file insieme sono troppo grandi (massimo %(mb)d MB).")
            % {"mb": settings.JOB_MAX_TOTAL_BYTES // (1024 * 1024)}
        )
    return prepared
