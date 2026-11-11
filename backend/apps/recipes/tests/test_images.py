"""Immagini delle ricette (ADR 0011): foto vera, disegno di Gemini (finto), limiti."""

from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from apps.ai.models import AiCall
from apps.jobs.models import Job
from apps.recipes.models import Recipe
from apps.recipes.serializers import RecipeSerializer

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _recipe(user, **extra):
    serializer = RecipeSerializer(
        data={
            "title": "Pasta e zucchine",
            "description": "Veloce.",
            "ingredients": [
                {"name": "pasta", "quantity": "160", "unit": "g"},
                {"name": "zucchine", "quantity": "200", "unit": "g"},
                {"name": "sale", "unit": "to_taste"},
            ],
        },
        context={},
    )
    serializer.is_valid(raise_exception=True)
    return serializer.save(owner=user, **extra)


def _jpeg(size=(3000, 2000), name="foto.jpg"):
    buffer = io.BytesIO()
    Image.new("RGB", size, "orange").save(buffer, "JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def _png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (512, 512), "green").save(buffer, "PNG")
    return buffer.getvalue()


def test_foto_vera(user, api, media):
    recipe = _recipe(user)
    url = f"/api/recipes/{recipe.id}/image"
    response = api(user).post(url, {"file": _jpeg()}, format="multipart")
    assert response.status_code == 200, response.data
    assert response.data["image_source"] == "photo"
    assert response.data["image"].startswith(f"/media/recipes/{user.id}/")
    recipe.refresh_from_db()
    with Image.open(recipe.image.path) as saved:
        assert saved.format == "WEBP" and max(saved.size) == 1600
    first = recipe.image.path
    # Una foto nuova sostituisce la vecchia, che sparisce dal disco.
    api(user).post(url, {"file": _jpeg((800, 600))}, format="multipart")
    recipe.refresh_from_db()
    assert recipe.image.path != first
    assert len(list((media / "recipes" / str(user.id)).iterdir())) == 1
    # Anche nelle card del ricettario.
    listed = api(user).get("/api/recipes").data["results"][0]
    assert listed["image"] == recipe.image.url
    removed = api(user).delete(url)
    assert (removed.data["image"], removed.data["image_source"]) == (None, "")
    assert not list((media / "recipes" / str(user.id)).iterdir())


def test_file_rifiutati(user, other_user, api):
    recipe = _recipe(user)
    url = f"/api/recipes/{recipe.id}/image"
    pdf = SimpleUploadedFile("a.pdf", b"%PDF-1.4 ciao", content_type="application/pdf")
    assert api(user).post(url, {"file": pdf}, format="multipart").status_code == 400
    assert api(user).post(url, {}, format="multipart").status_code == 400
    assert api(other_user).post(url, {"file": _jpeg()}, format="multipart").status_code == 404


def test_cancellata_davvero_via_anche_il_file(user, api, media):
    recipe = _recipe(user)
    api(user).post(f"/api/recipes/{recipe.id}/image", {"file": _jpeg()}, format="multipart")
    recipe.refresh_from_db()
    recipe.delete()  # soft: il file resta
    assert list((media / "recipes" / str(user.id)).iterdir())
    Recipe.all_objects.get(id=recipe.id).delete(hard=True)
    assert not list((media / "recipes" / str(user.id)).iterdir())


@pytest.fixture
def drawer(monkeypatch):
    state = {"prompts": []}

    def fake(prompt, **kwargs):
        state["prompts"].append(prompt)
        AiCall.objects.create(user=kwargs.get("user"), feature=kwargs["feature"], model="finto")
        return _png_bytes(), "image/png", "finto"

    monkeypatch.setattr("apps.recipes.images.generate_image", fake)
    return state


def _draw(api, user, recipe, capture):
    with override_settings(GEMINI_API_KEY="k"), capture(execute=True):
        return api(user).post(f"/api/recipes/{recipe.id}/image/draw")


def test_disegnata_da_gemini(user, api, drawer, django_capture_on_commit_callbacks):
    recipe = _recipe(user)
    response = _draw(api, user, recipe, django_capture_on_commit_callbacks)
    assert response.status_code == 202, response.data
    job = Job.objects.get(id=response.data["id"])
    assert job.status == Job.Status.READY, job.error
    recipe.refresh_from_db()
    assert recipe.image_source == "ai"
    assert job.result == {"recipe": str(recipe.id), "image": recipe.image.url}
    prompt = drawer["prompts"][0]
    # Titolo e ingredienti principali, non i basilari; niente dati dell'utente.
    assert "Pasta e zucchine" in prompt and "zucchin" in prompt and "sale" not in prompt
    assert user.email not in prompt


def test_la_foto_vera_vince(user, api, drawer, django_capture_on_commit_callbacks):
    recipe = _recipe(user)
    api(user).post(f"/api/recipes/{recipe.id}/image", {"file": _jpeg()}, format="multipart")
    assert _draw(api, user, recipe, django_capture_on_commit_callbacks).status_code == 400
    assert not drawer["prompts"]


@override_settings(AI_IMAGES_PER_DAY=1)
def test_tetto_giornaliero(user, api, drawer, django_capture_on_commit_callbacks):
    recipe = _recipe(user)
    assert _draw(api, user, recipe, django_capture_on_commit_callbacks).status_code == 202
    assert _draw(api, user, recipe, django_capture_on_commit_callbacks).status_code == 400


def test_senza_chiave(user, api):
    recipe = _recipe(user)
    assert api(user).post(f"/api/recipes/{recipe.id}/image/draw").status_code == 503


def test_nel_tetto_contano_solo_le_immagini_riuscite(user):
    from apps.recipes.images import FEATURE, images_today

    AiCall.objects.create(user=user, feature=FEATURE, model="m", ok=True)
    AiCall.objects.create(user=user, feature=FEATURE, model="m", ok=False, error="nessuna immagine")
    assert images_today(user) == 1
