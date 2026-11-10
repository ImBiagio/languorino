"""Cosa cucino oggi: frigo letto (finto), ricette che si possono fare, idee nuove."""

from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from apps.jobs.models import Job
from apps.kitchen.cook_today import FridgeContents, match_recipes
from apps.profiles.models import FoodPreference, Profile
from apps.recipes.importing import ImportedIngredient, ImportedRecipe, ImportedRecipes
from apps.recipes.models import Recipe, RecipeBook
from apps.recipes.serializers import RecipeSerializer

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("media_tmp")]
SCAN = "/api/cook-today/scan"
SUGGEST = "/api/cook-today/suggest"


@pytest.fixture
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _recipe(user, title, ingredients, slots=("lunch", "dinner"), minutes=20, **extra):
    data = {
        "title": title,
        "servings": 2,
        "prep_minutes": minutes,
        "meal_slots": list(slots),
        "ingredients": [{"name": name, "quantity": "100", "unit": "g"} for name in ingredients],
    }
    serializer = RecipeSerializer(data=data, context={})
    serializer.is_valid(raise_exception=True)
    return serializer.save(owner=user, **extra)


@pytest.fixture
def cookbook(user):
    _recipe(user, "Frittata di zucchine", ["uova", "zucchine", "olio evo", "sale"])
    _recipe(user, "Pasta zucchine e pancetta", ["pasta", "zucchine", "pancetta"])
    _recipe(user, "Risotto ai funghi", ["riso", "funghi champignon", "brodo vegetale"], minutes=40)
    _recipe(user, "Yogurt e frutta", ["yogurt bianco", "fragole"], slots=["breakfast"])
    book = RecipeBook.objects.create(owner=user, title="PDF", page_count=1)
    _recipe(user, "Uova strapazzate", ["uova", "burro"], book=book, in_cookbook=False)


def _titles(matches):
    return [item["recipe"].title for item in matches]


def test_le_piu_complete_prima(user, cookbook):
    matches = match_recipes(user, ["uova", "zucchine"])
    # La frittata ha tutto (olio e sale sono basilari e non contano).
    assert _titles(matches)[0] == "Frittata di zucchine"
    assert matches[0]["missing"] == []
    pasta = next(item for item in matches if item["recipe"].title == "Pasta zucchine e pancetta")
    assert sorted(pasta["missing"]) == ["pancetta", "pasta"]
    # Senza niente in comune non compare.
    assert "Risotto ai funghi" not in _titles(matches)


def test_nomi_scritti_come_vengono(user, cookbook):
    # Plurale, maiuscole e "pancetta a cubetti" riconosciuti lo stesso.
    matches = match_recipes(user, ["Zucchina", "pancetta a cubetti", "spaghetti"])
    assert _titles(matches)[0] == "Pasta zucchine e pancetta"
    assert matches[0]["missing"] == []


def test_filtri_pasto_e_tempo(user, cookbook):
    assert _titles(match_recipes(user, ["yogurt"], slot="breakfast")) == ["Yogurt e frutta"]
    assert match_recipes(user, ["yogurt"], slot="dinner") == []
    assert match_recipes(user, ["riso"], minutes=30) == []


def test_ricettari_pdf_inclusi_o_no(user, cookbook):
    assert "Uova strapazzate" in _titles(match_recipes(user, ["uova"]))
    assert "Uova strapazzate" not in _titles(match_recipes(user, ["uova"], include_books=False))


def test_mai_ricette_vietate(user, cookbook):
    profile = Profile.objects.create(user=user)
    FoodPreference.objects.create(profile=profile, kind="allergy", label="eggs", allergen="eggs")
    titles = _titles(match_recipes(user, ["uova", "zucchine"]))
    assert "Frittata di zucchine" not in titles
    assert "Uova strapazzate" not in titles


def test_ricette_degli_altri_ignorate(user, other_user, cookbook):
    assert match_recipes(other_user, ["uova", "zucchine"]) == []


# --- API con Gemini finto ---------------------------------------------------------------


@pytest.fixture
def gemini(monkeypatch):
    state = {"prompts": [], "ideas": None}

    def fake_generate(contents, schema, **kwargs):
        class Types:
            class Part:
                @staticmethod
                def from_bytes(data, mime_type):
                    return mime_type

        parts = contents(Types)
        state["prompts"].append(parts[-1])
        if schema is FridgeContents:
            return FridgeContents(
                ingredients=["Zucchine ", "uova", "zucchine", "Mozzarella"]
            ), "finto"
        return state["ideas"] or ImportedRecipes(
            recipes=[
                ImportedRecipe(
                    title="Zucchine ripiene",
                    servings=2,
                    ingredients=[ImportedIngredient(name="zucchine", quantity="400", unit="g")],
                    steps=["Svuota e riempi."],
                ),
                ImportedRecipe(
                    title="Torta salata",
                    servings=2,
                    ingredients=[ImportedIngredient(name="uova", quantity="3", unit="pz")],
                    steps=["Inforna."],
                ),
            ]
        ), "finto"

    monkeypatch.setattr("apps.kitchen.cook_today.generate", fake_generate)
    return state


def _photo():
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buffer, "JPEG")
    return SimpleUploadedFile("frigo.jpg", buffer.getvalue(), content_type="image/jpeg")


def test_foto_del_frigo(user, api, gemini, django_capture_on_commit_callbacks):
    with override_settings(GEMINI_API_KEY="k"), django_capture_on_commit_callbacks(execute=True):
        response = api(user).post(SCAN, {"files": [_photo()]}, format="multipart")
    assert response.status_code == 202, response.data
    job = api(user).get(f"/api/jobs/{response.data['id']}").data
    assert job["status"] == "ready"
    assert job["result"]["ingredients"] == ["zucchine", "uova", "mozzarella"]


def test_foto_rifiutate(user, api):
    with override_settings(GEMINI_API_KEY="k"):
        pdf = SimpleUploadedFile("x.pdf", b"%PDF-1.4 x", content_type="application/pdf")
        assert api(user).post(SCAN, {"files": [pdf]}, format="multipart").status_code == 400
        assert (
            api(user)
            .post(SCAN, {"files": [_photo() for _ in range(4)]}, format="multipart")
            .status_code
            == 400
        )
    with override_settings(GEMINI_API_KEY=""):
        assert api(user).post(SCAN, {"files": [_photo()]}, format="multipart").status_code == 503


def test_suggerimenti_e_idee(user, api, cookbook, gemini, django_capture_on_commit_callbacks):
    with override_settings(GEMINI_API_KEY="k"), django_capture_on_commit_callbacks(execute=True):
        response = api(user).post(
            SUGGEST,
            {"ingredients": ["uova", " zucchine ", ""], "slot": "dinner", "servings": 3},
            format="json",
        )
    assert response.status_code == 200, response.data
    data = response.data
    assert data["ingredients"] == ["uova", "zucchine"]
    assert data["matches"][0]["recipe"]["title"] == "Frittata di zucchine"
    assert data["matches"][0]["missing"] == []
    job = api(user).get(f"/api/jobs/{data['job']['id']}").data
    assert [idea["title"] for idea in job["result"]["ideas"]] == [
        "Zucchine ripiene",
        "Torta salata",
    ]
    new = Recipe.objects.get(title="Zucchine ripiene")
    assert (new.source, new.in_cookbook, new.status, new.servings) == ("fridge", False, "draft", 3)
    assert "uova, zucchine" in gemini["prompts"][-1]
    assert "cena" in gemini["prompts"][-1]


def test_idea_con_allergene_scartata(user, api, gemini, django_capture_on_commit_callbacks):
    profile = Profile.objects.create(user=user)
    FoodPreference.objects.create(profile=profile, kind="allergy", label="eggs", allergen="eggs")
    with override_settings(GEMINI_API_KEY="k"), django_capture_on_commit_callbacks(execute=True):
        data = api(user).post(SUGGEST, {"ingredients": ["zucchine"]}, format="json").data
    ideas = api(user).get(f"/api/jobs/{data['job']['id']}").data["result"]["ideas"]
    assert [idea["title"] for idea in ideas] == ["Zucchine ripiene"]
    assert not Recipe.all_objects.filter(title="Torta salata").exists()
    assert "NON devono contenere" in gemini["prompts"][-1] and "eggs" in gemini["prompts"][-1]


def test_senza_idee_o_senza_chiave(user, api, cookbook):
    with override_settings(GEMINI_API_KEY=""):
        data = api(user).post(SUGGEST, {"ingredients": ["uova"]}, format="json").data
    assert data["job"] is None and data["matches"]
    with override_settings(GEMINI_API_KEY="k"):
        data = (
            api(user).post(SUGGEST, {"ingredients": ["uova"], "ideas": False}, format="json").data
        )
    assert data["job"] is None
    assert not Job.objects.exists()


@pytest.mark.parametrize(
    "payload",
    [{"ingredients": []}, {"ingredients": ["  "]}, {"ingredients": ["x"], "slot": "brunch"}],
)
def test_richieste_rifiutate(user, api, payload):
    assert api(user).post(SUGGEST, payload, format="json").status_code == 400


def test_lavori_generici_solo_import(user, api):
    with override_settings(GEMINI_API_KEY="k"):
        response = api(user).post(
            "/api/jobs", {"kind": "cook_ideas", "files": [_photo()]}, format="multipart"
        )
    assert response.status_code == 400


def test_pulizia_delle_idee_vecchie(user):
    from datetime import date, timedelta

    from django.utils import timezone

    from apps.kitchen.tasks import clean_ideas
    from apps.plans.models import MealPlan, PlannedMeal

    fridge = {"source": Recipe.Source.FRIDGE, "in_cookbook": False}
    old = _recipe(user, "Vecchia", ["uova"], **fridge)
    fresh = _recipe(user, "Di ieri", ["uova"], **fridge)
    saved = _recipe(user, "Salvata", ["uova"], source=Recipe.Source.FRIDGE, in_cookbook=True)
    planned = _recipe(user, "Nel piano", ["uova"], **fridge)
    other = _recipe(user, "Del piano", ["uova"], source=Recipe.Source.PLAN, in_cookbook=False)
    ten_days_ago = timezone.now() - timedelta(days=10)
    Recipe.objects.filter(id__in=[old.id, saved.id, planned.id, other.id]).update(
        created_at=ten_days_ago
    )
    Recipe.objects.filter(id=fresh.id).update(created_at=timezone.now() - timedelta(days=1))
    plan = MealPlan.objects.create(owner=user, start_date=date.today())
    PlannedMeal.objects.create(
        plan=plan, date=date.today(), slot="lunch", recipe=planned, cooked_on=date.today()
    )

    assert clean_ideas() == 1
    left = set(Recipe.all_objects.filter(owner=user).values_list("title", flat=True))
    assert left == {"Di ieri", "Salvata", "Nel piano", "Del piano"}
