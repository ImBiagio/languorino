"""File di ``MEDIA_ROOT`` serviti in sviluppo (in produzione lo fa Caddy)."""

from __future__ import annotations

import posixpath

from django.conf import settings
from django.http import Http404
from django.views.static import serve


def is_private_media(path: str) -> bool:
    """Vero se il percorso cade in una cartella privata (``PRIVATE_MEDIA_PREFIXES``).

    Il percorso si normalizza prima del confronto: ``./books/x`` o
    ``recipes/../books/x`` non devono aggirare il blocco.
    """
    clean = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
    first = clean.split("/", 1)[0].lower()
    return first in settings.PRIVATE_MEDIA_PREFIXES


def serve_public_media(request, path: str):
    """Come ``django.views.static.serve``, ma i file privati rispondono 404.

    PDF dei ricettari e file dei lavori non hanno un proprietario nell'URL:
    servirli vorrebbe dire proteggerli solo con un UUID difficile da indovinare.
    """
    if is_private_media(path):
        raise Http404
    return serve(request, path, document_root=settings.MEDIA_ROOT)
