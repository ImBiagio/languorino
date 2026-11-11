"""Immagini dei ricettari PDF (ADR 0015): foto ritagliate dal PDF, poi illustrazioni."""

from __future__ import annotations

import io

import pytest
from django.core.files.base import ContentFile
from django.test import override_settings
from PIL import Image, ImageDraw

from apps.ai.client import AIError
from apps.ai.models import AiCall
from apps.recipes import book_images
from apps.recipes.book_images import BookPhoto, BookPhotos, crop
from apps.recipes.models import Recipe, RecipeBook

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _pdf(pages=2) -> bytes:
    """Pagine A5 "scansionate": una testata decorativa e, a pagina 2, una foto rossa."""
    images = []
    for number in range(1, pages + 1):
        page = Image.new("RGB", (600, 850), "white")
        draw = ImageDraw.Draw(page)
        draw.rectangle((0, 0, 600, 60), fill=(200, 200, 160))  # testata di ogni pagina
        if number == 2:
            draw.rectangle((150, 300, 450, 600), fill=(220, 30, 30))  # la foto del piatto
        images.append(page)
    out = io.BytesIO()
    images[0].save(out, "PDF", save_all=True, append_images=images[1:], resolution=72)
    return out.getvalue()


def _book(user, pages=2) -> RecipeBook:
    book = RecipeBook(owner=user, title="Ricettario", page_count=pages, status="ready")
    book.file.save("libro.pdf", ContentFile(_pdf(pages)), save=False)
    book.save()
    for title in ("Pasta e fagioli", "Polpette di piselli"):
        Recipe.objects.create(owner=user, title=title, book=book, in_cookbook=False)
    return book


def test_riquadri_non_plausibili():
    page = Image.new("RGB", (100, 100), "white")
    assert crop(page, [0, 0, 1000, 1000]) is None  # la pagina intera
    assert crop(page, [0, 0, 50, 50]) is None  # un'icona
    assert crop(page, [500, 500, 400, 600]) is None  # rovesciato
    assert crop(page, [1, 2, 3]) is None
    assert crop(page, [300, 300, 700, 700]) is not None


def test_foto_ritagliata_dal_pdf(user, monkeypatch):
    book = _book(user)
    calls = []

    def fake(contents, schema, **kwargs):
        class Types:
            class Part:
                @staticmethod
                def from_bytes(data, mime_type):
                    return mime_type

        calls.append(contents(Types)[-1])
        return BookPhotos(
            photos=[
                # Riquadro della foto rossa a pagina 2 (in millesimi della pagina).
                BookPhoto(title="pasta e  fagioli", page=2, box=[353, 250, 706, 750]),
                # La testata decorativa: troppo sottile e larga, ma l'LLM la segnala lo stesso.
                BookPhoto(title="Polpette di piselli", page=1, box=[0, 0, 1000, 1000]),
                BookPhoto(title="Ricetta che non c'e'", page=1, box=[300, 300, 700, 700]),
            ]
        ), "finto"

    monkeypatch.setattr(book_images, "generate", fake)
    with book.file.open("rb") as handle:
        data = handle.read()
    assert book_images.find_photos(book, data, 0, 2) == 1
    assert "- Pasta e fagioli" in calls[0] and "- Polpette di piselli" in calls[0]
    pasta = Recipe.objects.get(title="Pasta e fagioli")
    assert pasta.image_source == "book"
    with Image.open(pasta.image.path) as saved:
        red, green, _blue = saved.convert("RGB").getpixel((saved.width // 2, saved.height // 2))
    assert red > 180 and green < 80  # e' proprio la foto rossa
    assert not Recipe.objects.get(title="Polpette di piselli").image


def test_flusso_completo_con_illustrazioni(
    user, api, monkeypatch, django_capture_on_commit_callbacks
):
    book = _book(user)
    monkeypatch.setattr(book_images, "generate", lambda *a, **k: (BookPhotos(), "finto"))
    drawn = []

    def fake_image(prompt, **kwargs):
        drawn.append(prompt)
        AiCall.objects.create(user=kwargs["user"], feature=kwargs["feature"], model="finto")
        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), "orange").save(buffer, "PNG")
        return buffer.getvalue(), "image/png", "finto"

    monkeypatch.setattr("apps.recipes.images.generate_image", fake_image)
    url = f"/api/recipe-books/{book.id}/images"
    with override_settings(GEMINI_API_KEY="k"), django_capture_on_commit_callbacks(execute=True):
        response = api(user).post(url)
    assert response.status_code == 202, response.data
    book.refresh_from_db()
    assert (book.images_status, book.images_pages_done) == ("done", 2)
    assert len(drawn) == 2 and drawn[0].startswith("Illustrazione semplice")
    assert set(Recipe.objects.values_list("image_source", flat=True)) == {"ai"}
    listed = api(user).get(f"/api/recipe-books/{book.id}").data
    assert (listed["without_image"], listed["images_status"]) == (0, "done")


@override_settings(AI_IMAGES_PER_DAY=1)
def test_tetto_del_giorno_e_ripresa(user, monkeypatch, django_capture_on_commit_callbacks):
    from apps.recipes.tasks import resume_book_images, start_book_images

    book = _book(user)
    monkeypatch.setattr(book_images, "generate", lambda *a, **k: (BookPhotos(), "finto"))

    def fake_image(prompt, **kwargs):
        AiCall.objects.create(user=kwargs["user"], feature=kwargs["feature"], model="finto")
        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), "orange").save(buffer, "PNG")
        return buffer.getvalue(), "image/png", "finto"

    monkeypatch.setattr("apps.recipes.images.generate_image", fake_image)
    with django_capture_on_commit_callbacks(execute=True):
        start_book_images(book)
    book.refresh_from_db()
    assert book.images_status == "drawing" and "domani" in book.images_error
    assert Recipe.objects.exclude(image="").count() == 1
    # Il giorno dopo (tetto azzerato) la ripresa del mattino finisce il lavoro.
    AiCall.objects.all().delete()
    resume_book_images()
    book.refresh_from_db()
    assert book.images_status == "done"


def test_senza_quota_per_le_immagini(user, monkeypatch, django_capture_on_commit_callbacks):
    from apps.recipes.tasks import start_book_images

    book = _book(user)
    monkeypatch.setattr(book_images, "generate", lambda *a, **k: (BookPhotos(), "finto"))

    def no_quota(*args, **kwargs):
        raise AIError("La chiave Gemini non ha quota per le immagini (piano gratuito).")

    monkeypatch.setattr("apps.recipes.images.generate_image", no_quota)
    with django_capture_on_commit_callbacks(execute=True):
        start_book_images(book)
    book.refresh_from_db()
    assert book.images_status == "failed" and "quota" in book.images_error


def test_titolo_cambiato_durante_la_ricerca(
    user, api, monkeypatch, django_capture_on_commit_callbacks
):
    from apps.recipes.tasks import start_book_images

    book = _book(user)

    def rename_then_nothing(*args, **kwargs):
        RecipeBook.objects.filter(id=book.id).update(title="Le ricette di Anna")
        return BookPhotos(), "finto"

    monkeypatch.setattr(book_images, "generate", rename_then_nothing)
    monkeypatch.setattr(
        "apps.recipes.images.generate_image", lambda *a, **k: (_ for _ in ()).throw(AIError("x"))
    )
    with django_capture_on_commit_callbacks(execute=True):
        start_book_images(book)
    book.refresh_from_db()
    assert book.title == "Le ricette di Anna"


def test_solo_ricettari_letti(user, api):
    book = _book(user)
    RecipeBook.objects.filter(id=book.id).update(status="reading")
    with override_settings(GEMINI_API_KEY="k"):
        assert api(user).post(f"/api/recipe-books/{book.id}/images").status_code == 400


def test_tutti_i_titoli_e_un_riquadro_una_ricetta(user, monkeypatch):
    book = _book(user)
    pasta = Recipe.objects.get(title="Pasta e fagioli")
    pasta.image.save("x.webp", ContentFile(b"gia'"), save=False)
    pasta.image_source = "book"
    pasta.save()
    prompts = []

    def fake(contents, schema, **kwargs):
        class Types:
            class Part:
                @staticmethod
                def from_bytes(data, mime_type):
                    return mime_type

        prompts.append(contents(Types)[-1])
        box = [353, 250, 706, 750]
        return BookPhotos(
            photos=[
                BookPhoto(title="Pasta e fagioli", page=2, box=box),
                BookPhoto(title="Polpette di piselli", page=2, box=box),
            ]
        ), "finto"

    monkeypatch.setattr(book_images, "generate", fake)
    with book.file.open("rb") as handle:
        data = handle.read()
    # La foto e' della pasta (che ha gia' un'immagine): alle polpette non va.
    assert book_images.find_photos(book, data, 0, 2) == 0
    assert "- Pasta e fagioli" in prompts[0]
    assert not Recipe.objects.get(title="Polpette di piselli").image
