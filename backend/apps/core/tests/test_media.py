"""File caricati: pubbliche solo le immagini, mai PDF dei ricettari e file dei lavori."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.http import Http404
from django.test import RequestFactory

from apps.core.media import is_private_media, serve_public_media


@pytest.fixture
def media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    for name in ["recipes/u/foto.webp", "books/libro.pdf", "jobs/j/piano.pdf"]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"contenuto")
    return tmp_path


def test_le_immagini_delle_ricette_si_servono(media):
    response = serve_public_media(RequestFactory().get("/"), "recipes/u/foto.webp")
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"contenuto"


@pytest.mark.parametrize(
    "path",
    [
        "books/libro.pdf",
        "jobs/j/piano.pdf",
        "jobs",
        "books/",
        "./books/libro.pdf",
        "recipes/../books/libro.pdf",
        "//jobs/j/piano.pdf",
        "BOOKS/libro.pdf",
    ],
)
def test_i_file_privati_rispondono_404(media, path):
    assert is_private_media(path)
    with pytest.raises(Http404):
        serve_public_media(RequestFactory().get("/"), path)


def test_il_caddyfile_chiude_le_stesse_cartelle(settings):
    """In produzione i media li serve Caddy: l'elenco non deve divergere."""
    caddyfile = Path(settings.BASE_DIR).parent / "deploy" / "Caddyfile"
    if not caddyfile.exists():  # nell'immagine c'e' solo backend/
        pytest.skip("deploy/Caddyfile non montato")
    text = caddyfile.read_text()
    for prefix in settings.PRIVATE_MEDIA_PREFIXES:
        assert f"/media/{prefix} /media/{prefix}/*" in text
