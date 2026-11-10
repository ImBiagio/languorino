"""Import di ricette da foto e PDF: file, job, lettura (finta), revisione, conferma."""

from __future__ import annotations

import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image

from apps.ai.client import AIError
from apps.jobs.models import Job, JobFile
from apps.jobs.tasks import clean_jobs
from apps.recipes.importing import ImportedIngredient, ImportedRecipe, ImportedRecipes
from apps.recipes.models import Recipe

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("media_tmp")]
JOBS = "/api/jobs"


@pytest.fixture
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _image(width=800, height=600, fmt="JPEG", name="ricetta.jpg"):
    buffer = io.BytesIO()
    image = Image.new("RGB", (width, height), "white")
    exif = Image.Exif()
    exif[0x8825] = {2: (45.0, 28.0, 0.0)}  # GPS: deve sparire
    image.save(buffer, fmt, exif=exif.tobytes() if fmt == "JPEG" else b"")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def _pdf(name="ricettario.pdf", size=0):
    body = b"%PDF-1.4\n" + b"0" * size + b"\n%%EOF"
    return SimpleUploadedFile(name, body, content_type="application/pdf")


LETTA = ImportedRecipes(
    recipes=[
        ImportedRecipe(
            title="  Torta di mele della nonna ",
            servings=0,
            prep_minutes=20,
            cook_minutes=5000,
            difficulty="easy",
            meal_slots=["afternoon_snack", "breakfast", "breakfast"],
            keeps_days=4,
            ingredients=[
                ImportedIngredient(name="Mele", quantity="3", unit="pz"),
                ImportedIngredient(name="farina", quantity="200,5", unit="g"),
                ImportedIngredient(name="cannella", quantity="1", unit="to_taste"),
                ImportedIngredient(name="Uvetta sultanina", quantity="-2", unit="g"),
                ImportedIngredient(name=" ", quantity="1", unit="g"),
            ],
            steps=["Sbuccia le mele.", " ", "Inforna."],
            tags=["Dolci", "dolci", "forno"],
            inferred=["servings", "keeps_days"],
        )
    ]
)


@pytest.fixture
def gemini(monkeypatch):
    """Lettura finta: ``state["result"]`` o ``state["error"]``."""
    state = {"result": LETTA, "error": None, "files": None}

    def fake_generate(contents, schema, **kwargs):
        if state["error"]:
            raise state["error"]

        class Types:
            class Part:
                @staticmethod
                def from_bytes(data, mime_type):
                    return (mime_type, len(data))

        state["files"] = contents(Types)
        return state["result"], "gemini-finto"

    monkeypatch.setattr("apps.recipes.importing.generate", fake_generate)
    return state


def _start(api, user, files, capture):
    with override_settings(GEMINI_API_KEY="k"), capture(execute=True):
        response = api(user).post(
            JOBS, {"kind": "import_recipes", "files": files}, format="multipart"
        )
    return response


def test_serve_il_login(api):
    assert api().get(JOBS).status_code == 401


@override_settings(GEMINI_API_KEY="")
def test_senza_chiave_503(user, api):
    response = api(user).post(
        JOBS, {"kind": "import_recipes", "files": [_pdf()]}, format="multipart"
    )
    assert response.status_code == 503


def test_import_da_foto(user, api, gemini, django_capture_on_commit_callbacks):
    response = _start(api, user, [_image(), _pdf()], django_capture_on_commit_callbacks)
    assert response.status_code == 202, response.data
    job = Job.objects.get(id=response.data["id"])
    assert job.status == Job.Status.READY
    assert job.model == "gemini-finto"
    # A Gemini vanno i file nell'ordine, la foto ridotta a JPEG, piu' il prompt.
    assert [part[0] for part in gemini["files"][:2]] == ["image/jpeg", "application/pdf"]
    assert isinstance(gemini["files"][2], str)

    [draft] = api(user).get(f"{JOBS}/{job.id}").data["result"]["recipes"]
    assert draft["title"] == "Torta di mele della nonna"
    assert draft["servings"] == 2  # 0 vale "non lo so": il default
    assert draft["cook_minutes"] == 1440
    assert draft["meal_slots"] == ["breakfast", "afternoon_snack"]
    assert draft["steps"] == ["Sbuccia le mele.", "Inforna."]
    assert draft["tags"] == ["dolci", "forno"]
    assert draft["inferred"] == ["keeps_days", "servings"]
    lines = {line["name"]: line for line in draft["ingredients"]}
    assert set(lines) == {"mela", "farina 00", "cannella", "Uvetta sultanina"}
    assert lines["mela"]["ingredient_id"] and lines["mela"]["category"] == "produce"
    assert lines["farina 00"]["quantity"] == "200.5"
    assert lines["cannella"]["quantity"] is None
    assert lines["Uvetta sultanina"]["ingredient_id"] is None
    assert lines["Uvetta sultanina"]["quantity"] is None


def test_foto_ridotta_e_senza_exif(user, api, gemini, django_capture_on_commit_callbacks):
    response = _start(api, user, [_image(4000, 1000)], django_capture_on_commit_callbacks)
    stored = JobFile.objects.get(job_id=response.data["id"])
    with Image.open(stored.file.path) as image:
        assert max(image.size) == 2400
        assert not image.getexif().get(0x8825)


@pytest.mark.parametrize(
    "files",
    [
        [],
        [SimpleUploadedFile("note.txt", b"ciao", content_type="text/plain")],
        [SimpleUploadedFile("finta.jpg", b"%PDX non e' niente", content_type="image/jpeg")],
        [_pdf(name=f"p{n}.pdf") for n in range(9)],
    ],
)
def test_file_rifiutati(user, api, gemini, files, django_capture_on_commit_callbacks):
    response = _start(api, user, files, django_capture_on_commit_callbacks)
    assert response.status_code == 400
    assert not Job.objects.exists()


@override_settings(JOB_MAX_PDF_BYTES=1000)
def test_pdf_troppo_grande(user, api, gemini, django_capture_on_commit_callbacks):
    response = _start(api, user, [_pdf(size=2000)], django_capture_on_commit_callbacks)
    assert response.status_code == 400
    assert "troppo grande" in str(response.data["files"])


def test_lavoro_sconosciuto(user, api):
    with override_settings(GEMINI_API_KEY="k"):
        response = api(user).post(JOBS, {"kind": "boh", "files": [_pdf()]}, format="multipart")
    assert response.status_code == 400


def test_errore_dell_llm_e_riprova(user, api, gemini, django_capture_on_commit_callbacks):
    gemini["error"] = AIError("Gemini è sovraccarico.")
    job_id = _start(api, user, [_pdf()], django_capture_on_commit_callbacks).data["id"]
    data = api(user).get(f"{JOBS}/{job_id}").data
    assert data["status"] == "failed"
    assert "sovraccarico" in data["error"]

    gemini["error"] = None
    with override_settings(GEMINI_API_KEY="k"), django_capture_on_commit_callbacks(execute=True):
        assert api(user).post(f"{JOBS}/{job_id}/retry").status_code == 202
    assert api(user).get(f"{JOBS}/{job_id}").data["status"] == "ready"
    # Un lavoro riuscito non si "riprova".
    assert api(user).post(f"{JOBS}/{job_id}/retry").status_code == 400


def test_errore_imprevisto_non_rompe(user, api, gemini, django_capture_on_commit_callbacks):
    gemini["error"] = RuntimeError("boom")
    job_id = _start(api, user, [_pdf()], django_capture_on_commit_callbacks).data["id"]
    data = api(user).get(f"{JOBS}/{job_id}").data
    assert data["status"] == "failed"
    assert "boom" not in data["error"]


def test_nessuna_ricetta_trovata(user, api, gemini, django_capture_on_commit_callbacks):
    gemini["result"] = ImportedRecipes(recipes=[], problem="La foto è sfocata.")
    job_id = _start(api, user, [_image()], django_capture_on_commit_callbacks).data["id"]
    result = api(user).get(f"{JOBS}/{job_id}").data["result"]
    assert result == {"recipes": [], "problem": "La foto è sfocata."}


def _ready_job(api, user, capture, files=None):
    return _start(api, user, files or [_image()], capture).data["id"]


def _reviewed(api, user, job_id):
    draft = api(user).get(f"{JOBS}/{job_id}").data["result"]["recipes"][0]
    draft["title"] = "Torta di mele"
    return draft


def test_conferma_crea_le_ricette(user, api, gemini, django_capture_on_commit_callbacks):
    job_id = _ready_job(api, user, django_capture_on_commit_callbacks)
    draft = _reviewed(api, user, job_id)
    response = api(user).post(f"{JOBS}/{job_id}/confirm", {"recipes": [draft]}, format="json")
    assert response.status_code == 201, response.data
    recipe = Recipe.objects.get(owner=user)
    assert recipe.title == "Torta di mele"
    assert recipe.source == Recipe.Source.PHOTO
    assert recipe.status == Recipe.Status.CONFIRMED
    assert recipe.ingredients.count() == 4
    assert sorted(tag.name for tag in recipe.tags.all()) == ["dolci", "forno"]
    assert response.data["status"] == "confirmed"
    assert response.data["result"]["created"] == [str(recipe.id)]
    # Una seconda conferma non duplica.
    again = api(user).post(f"{JOBS}/{job_id}/confirm", {"recipes": [draft]}, format="json")
    assert again.status_code == 400
    assert Recipe.objects.count() == 1


def test_da_pdf_la_fonte_e_pdf(user, api, gemini, django_capture_on_commit_callbacks):
    job_id = _ready_job(api, user, django_capture_on_commit_callbacks, files=[_pdf()])
    draft = _reviewed(api, user, job_id)
    api(user).post(f"{JOBS}/{job_id}/confirm", {"recipes": [draft]}, format="json")
    assert Recipe.objects.get().source == Recipe.Source.PDF


def test_conferma_non_valida_non_crea_niente(user, api, gemini, django_capture_on_commit_callbacks):
    job_id = _ready_job(api, user, django_capture_on_commit_callbacks)
    draft = _reviewed(api, user, job_id)
    broken = {**draft, "title": " "}
    response = api(user).post(
        f"{JOBS}/{job_id}/confirm", {"recipes": [draft, broken]}, format="json"
    )
    assert response.status_code == 400
    assert not Recipe.objects.exists()
    assert Job.objects.get(id=job_id).status == Job.Status.READY
    assert (
        api(user).post(f"{JOBS}/{job_id}/confirm", {"recipes": []}, format="json").status_code
        == 400
    )


def test_lavori_degli_altri_invisibili(
    user, other_user, api, gemini, django_capture_on_commit_callbacks
):
    job_id = _ready_job(api, user, django_capture_on_commit_callbacks)
    draft = _reviewed(api, user, job_id)
    assert api(other_user).get(f"{JOBS}/{job_id}").status_code == 404
    assert api(other_user).get(JOBS).data == []
    response = api(other_user).post(f"{JOBS}/{job_id}/confirm", {"recipes": [draft]}, format="json")
    assert response.status_code == 404
    assert api(other_user).delete(f"{JOBS}/{job_id}").status_code == 404


def test_elenco_per_stato(user, api, gemini, django_capture_on_commit_callbacks):
    job_id = _ready_job(api, user, django_capture_on_commit_callbacks)
    assert [job["id"] for job in api(user).get(f"{JOBS}?status=ready").data] == [job_id]
    assert api(user).get(f"{JOBS}?status=failed").data == []


def test_scartare_cancella_i_file(user, api, gemini, django_capture_on_commit_callbacks):
    job_id = _ready_job(api, user, django_capture_on_commit_callbacks)
    path = JobFile.objects.get(job_id=job_id).file.path
    assert api(user).delete(f"{JOBS}/{job_id}").status_code == 204
    assert not Job.all_objects.filter(id=job_id).exists()
    import os

    assert not os.path.exists(path)


def test_pulizia_notturna(user, api, gemini, django_capture_on_commit_callbacks):
    job_id = _ready_job(api, user, django_capture_on_commit_callbacks)
    JobFile.objects.update(created_at=timezone.now() - timedelta(days=60))
    stuck = Job.objects.create(owner=user, kind="import_recipes", status="running")
    Job.objects.filter(id=stuck.id).update(updated_at=timezone.now() - timedelta(hours=3))
    clean_jobs()
    assert not JobFile.all_objects.filter(job_id=job_id).exists()
    assert Job.objects.get(id=job_id).status == Job.Status.READY
    stuck.refresh_from_db()
    assert stuck.status == Job.Status.FAILED
