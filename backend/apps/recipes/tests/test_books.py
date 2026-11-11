"""Ricettari PDF letti a pezzi (ADR 0006): caricamento, lettura, ripresa, salvataggio."""

from __future__ import annotations

import io
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from pypdf import PdfReader, PdfWriter

from apps.ai.client import AIError, AIOverloaded
from apps.recipes.books import chunk_bounds, extract_pages
from apps.recipes.models import Recipe, RecipeBook

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("media_tmp")]
BOOKS = "/api/recipe-books"


@pytest.fixture
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _pdf_bytes(pages=9):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _upload(pages=9, name="Ricettario_della_nutrizionista.pdf"):
    return SimpleUploadedFile(name, _pdf_bytes(pages), content_type="application/pdf")


def _draft(title, ingredient="ceci in scatola"):
    return {
        "title": title,
        "description": "",
        "servings": 1,
        "prep_minutes": 10,
        "cook_minutes": 20,
        "difficulty": "easy",
        "meal_slots": ["lunch"],
        "keeps_days": 3,
        "freezable": False,
        "steps": ["Cuoci tutto."],
        "tags": ["nutrizionista"],
        "ingredients": [
            {
                "ingredient_id": None,
                "name": ingredient,
                "category": None,
                "quantity": "100",
                "unit": "g",
                "note": "",
                "optional": False,
            }
        ],
        "inferred": [],
    }


@pytest.fixture
def gemini(monkeypatch):
    """Ogni pezzo "legge" le ricette che il test mette in ``by_start[pagina iniziale]``."""
    state = {"calls": [], "by_start": {}, "fail_at": None}

    def fake_read(files, *, user, language, extra_instructions=""):
        start = int(re.search(r"pagine da (\d+) a (\d+)", extra_instructions).group(1))
        pages = len(PdfReader(io.BytesIO(files[0][0])).pages)
        state["calls"].append((start, pages))
        if state["fail_at"] == start:
            raise AIError("Gemini è sovraccarico.")
        return {"recipes": state["by_start"].get(start, []), "problem": "", "model": "finto"}

    monkeypatch.setattr("apps.recipes.tasks.read_recipes", fake_read)
    return state


def _start(api, user, capture, pages=9):
    with override_settings(GEMINI_API_KEY="k", BOOK_PAGES_PER_CHUNK=4), capture(execute=True):
        return api(user).post(BOOKS, {"file": _upload(pages)}, format="multipart")


def test_pezzi_con_pagina_di_contesto():
    with override_settings(BOOK_PAGES_PER_CHUNK=4):
        assert chunk_bounds(0, 9) == (0, 4, True)
        assert chunk_bounds(4, 9) == (4, 8, True)
        assert chunk_bounds(8, 9) == (8, 9, False)
    data = _pdf_bytes(9)
    assert len(PdfReader(io.BytesIO(extract_pages(data, 4, 8, True))).pages) == 5
    assert len(PdfReader(io.BytesIO(extract_pages(data, 8, 9, False))).pages) == 1


@override_settings(GEMINI_API_KEY="")
def test_senza_chiave_503(user, api):
    assert api(user).post(BOOKS, {"file": _upload()}, format="multipart").status_code == 503


@pytest.mark.parametrize(
    "upload",
    [
        SimpleUploadedFile("ricette.jpg", b"\xff\xd8\xff\xe0 foto", content_type="image/jpeg"),
        SimpleUploadedFile(
            "rotto.pdf", b"%PDF-1.4 niente di valido", content_type="application/pdf"
        ),
    ],
)
def test_file_rifiutati(user, api, upload):
    with override_settings(GEMINI_API_KEY="k"):
        response = api(user).post(BOOKS, {"file": upload}, format="multipart")
    assert response.status_code == 400
    assert not RecipeBook.objects.exists()


def test_troppe_pagine(user, api):
    with override_settings(GEMINI_API_KEY="k", BOOK_MAX_PAGES=5):
        response = api(user).post(BOOKS, {"file": _upload(9)}, format="multipart")
    assert response.status_code == 400


def test_lettura_completa_a_pezzi(user, api, gemini, django_capture_on_commit_callbacks):
    gemini["by_start"] = {
        1: [_draft("Zuppa di ceci"), _draft("Insalata di farro", "farro")],
        # La pagina di contesto ha fatto rileggere la zuppa: non si duplica.
        5: [_draft("zuppa di  ceci"), _draft("Vellutata di zucca", "zucca")],
        9: [_draft("Porridge", "fiocchi d'avena")],
    }
    response = _start(api, user, django_capture_on_commit_callbacks)
    assert response.status_code == 202, response.data
    assert response.data["title"] == "Ricettario della nutrizionista"
    assert response.data["page_count"] == 9

    # Tre pezzi: 4 pagine + contesto, 4 + contesto, l'ultima da sola.
    assert gemini["calls"] == [(1, 5), (5, 5), (9, 1)]
    book = RecipeBook.objects.get()
    assert (book.status, book.pages_done) == (RecipeBook.Status.READY, 9)
    data = api(user).get(f"{BOOKS}/{book.id}").data
    assert (data["recipe_count"], data["saved_count"]) == (4, 0)

    recipes = Recipe.objects.filter(book=book)
    assert recipes.count() == 4
    assert set(recipes.values_list("in_cookbook", "status", "source").distinct()) == {
        (False, "draft", "pdf")
    }
    # Fuori dal ricettario dell'utente, dentro quello del PDF.
    assert api(user).get("/api/recipes").data["results"] == []
    listed = api(user).get(f"/api/recipes?book={book.id}").data["results"]
    assert sorted(item["title"] for item in listed) == [
        "Insalata di farro",
        "Porridge",
        "Vellutata di zucca",
        "Zuppa di ceci",
    ]
    assert listed[0]["book"] == {"id": str(book.id), "title": "Ricettario della nutrizionista"}
    # Avvisi e allergeni funzionano anche qui.
    porridge = next(item for item in listed if item["title"] == "Porridge")
    assert porridge["allergens"] == ["gluten"]


def test_salvare_nel_proprio_ricettario(user, api, gemini, django_capture_on_commit_callbacks):
    gemini["by_start"] = {1: [_draft("Zuppa di ceci")]}
    _start(api, user, django_capture_on_commit_callbacks, pages=3)
    recipe = Recipe.objects.get()
    response = api(user).post(f"/api/recipes/{recipe.id}/save")
    assert response.status_code == 200
    assert (response.data["in_cookbook"], response.data["status"]) == (True, "confirmed")
    assert [item["title"] for item in api(user).get("/api/recipes").data["results"]] == [
        "Zuppa di ceci"
    ]
    book = RecipeBook.objects.get()
    assert api(user).get(f"{BOOKS}/{book.id}").data["saved_count"] == 1


def test_errore_a_meta_e_ripresa(user, api, gemini, django_capture_on_commit_callbacks):
    gemini["by_start"] = {1: [_draft("Zuppa di ceci")], 5: [_draft("Vellutata", "zucca")]}
    gemini["fail_at"] = 5
    _start(api, user, django_capture_on_commit_callbacks)
    book = RecipeBook.objects.get()
    assert (book.status, book.pages_done) == (RecipeBook.Status.FAILED, 4)
    assert "sovraccarico" in book.error
    # Quello letto prima dell'errore resta.
    assert Recipe.objects.filter(book=book).count() == 1

    gemini["fail_at"] = None
    gemini["calls"].clear()
    with (
        override_settings(GEMINI_API_KEY="k", BOOK_PAGES_PER_CHUNK=4),
        django_capture_on_commit_callbacks(execute=True),
    ):
        assert api(user).post(f"{BOOKS}/{book.id}/retry").status_code == 202
    # Si riparte dalla pagina 5, non da capo.
    assert [start for start, _pages in gemini["calls"]] == [5, 9]
    book.refresh_from_db()
    assert book.status == RecipeBook.Status.READY
    assert Recipe.objects.filter(book=book).count() == 2
    assert api(user).post(f"{BOOKS}/{book.id}/retry").status_code == 400


def test_gemini_sovraccarico_riprova_da_solo(
    user, api, gemini, monkeypatch, django_capture_on_commit_callbacks
):
    """In modalita' eager il retry di Celery rilancia subito: si conta quante volte."""
    gemini["by_start"] = {1: [_draft("Zuppa di ceci")], 5: [_draft("Vellutata", "zucca")]}
    failures = {"left": 2}

    import apps.recipes.tasks as tasks

    original = tasks.read_recipes

    def flaky(files, **kwargs):
        if "pagine da 5" in kwargs.get("extra_instructions", "") and failures["left"]:
            failures["left"] -= 1
            raise AIOverloaded("Gemini è sovraccarico.")
        return original(files, **kwargs)

    monkeypatch.setattr(tasks, "read_recipes", flaky)
    monkeypatch.setattr(tasks, "OVERLOAD_PAUSE", 0)
    _start(api, user, django_capture_on_commit_callbacks)
    book = RecipeBook.objects.get()
    # Due pause sul secondo pezzo, poi si e' ripreso senza fermarsi.
    assert failures["left"] == 0
    assert (book.status, book.pages_done) == (RecipeBook.Status.READY, 9)
    assert Recipe.objects.filter(book=book).count() == 2


def test_letture_ferme_riprese(user, api, gemini, django_capture_on_commit_callbacks):
    from datetime import timedelta

    from django.utils import timezone

    from apps.recipes.tasks import resume_stalled_books

    gemini["by_start"] = {5: [_draft("Vellutata", "zucca")]}
    with override_settings(GEMINI_API_KEY="k", BOOK_PAGES_PER_CHUNK=4):
        # Senza on_commit eseguiti: il libro resta in coda.
        api(user).post(BOOKS, {"file": _upload(9)}, format="multipart")
    book = RecipeBook.objects.get()
    # Un worker morto a meta': "in lettura" da mezz'ora, arrivato a pagina 4.
    RecipeBook.objects.filter(id=book.id).update(
        status="reading", pages_done=4, updated_at=timezone.now() - timedelta(minutes=30)
    )
    with (
        override_settings(BOOK_PAGES_PER_CHUNK=4),
        django_capture_on_commit_callbacks(execute=True),
    ):
        assert resume_stalled_books() == 1
    book.refresh_from_db()
    assert book.status == RecipeBook.Status.READY
    assert [start for start, _pages in gemini["calls"]] == [5, 9]
    # Una lettura che sta andando non si tocca.
    assert resume_stalled_books() == 0


def test_eliminare_tiene_le_ricette_salvate(user, api, gemini, django_capture_on_commit_callbacks):
    gemini["by_start"] = {1: [_draft("Zuppa di ceci"), _draft("Farro", "farro")]}
    _start(api, user, django_capture_on_commit_callbacks, pages=3)
    book = RecipeBook.objects.get()
    kept = Recipe.objects.get(title="Zuppa di ceci")
    api(user).post(f"/api/recipes/{kept.id}/save")
    assert api(user).delete(f"{BOOKS}/{book.id}").status_code == 204
    assert not RecipeBook.all_objects.exists()
    assert list(Recipe.all_objects.values_list("title", flat=True)) == ["Zuppa di ceci"]
    kept.refresh_from_db()
    assert kept.book_id is None and kept.in_cookbook


def test_rinominare(user, api, gemini, django_capture_on_commit_callbacks):
    _start(api, user, django_capture_on_commit_callbacks, pages=1)
    book = RecipeBook.objects.get()
    response = api(user).patch(
        f"{BOOKS}/{book.id}", {"title": "  Ricette di Stefania "}, format="json"
    )
    assert response.data["title"] == "Ricette di Stefania"
    assert api(user).patch(f"{BOOKS}/{book.id}", {"title": " "}, format="json").status_code == 400


def test_ricettari_degli_altri_invisibili(
    user, other_user, api, gemini, django_capture_on_commit_callbacks
):
    gemini["by_start"] = {1: [_draft("Zuppa di ceci")]}
    _start(api, user, django_capture_on_commit_callbacks, pages=1)
    book = RecipeBook.objects.get()
    recipe = Recipe.objects.get()
    assert api(other_user).get(BOOKS).data == []
    assert api(other_user).get(f"{BOOKS}/{book.id}").status_code == 404
    assert api(other_user).delete(f"{BOOKS}/{book.id}").status_code == 404
    assert api(other_user).post(f"/api/recipes/{recipe.id}/save").status_code == 404
    assert api(other_user).get(f"/api/recipes?book={book.id}").data["results"] == []


def test_rinominare_durante_la_lettura(user, api, gemini, django_capture_on_commit_callbacks):
    """Il nome cambiato mentre Gemini legge un pezzo non torna quello di prima."""
    renamed = []

    def by_start(start):
        if start == 5 and not renamed:
            # L'utente rinomina mentre il secondo pezzo e' "da Gemini".
            book = RecipeBook.objects.get()
            api(user).patch(f"{BOOKS}/{book.id}", {"title": "Le ricette di Anna"}, format="json")
            renamed.append(True)
        return []

    gemini["by_start"] = type("Lazy", (dict,), {"get": lambda self, k, d=None: by_start(k)})()
    _start(api, user, django_capture_on_commit_callbacks)
    book = RecipeBook.objects.get()
    assert renamed and book.status == RecipeBook.Status.READY
    assert book.title == "Le ricette di Anna"
