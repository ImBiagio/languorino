"""Calorie e macro delle ricette (ADR 0018): dalla ricetta, stimati, a mano."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import override_settings

from apps.jobs.models import Job
from apps.recipes.importing import ImportedIngredient, ImportedNutrition, ImportedRecipe, to_draft
from apps.recipes.models import Recipe
from apps.recipes.nutrition import IngredientNutrition, NutritionEstimate
from apps.recipes.serializers import RecipeSerializer

pytestmark = pytest.mark.django_db

STIMA = NutritionEstimate(
    ingredients=[
        IngredientNutrition(
            name="pasta", grams=320, kcal=1139, protein_g=40.5, carbs_g=230.1, fat_g=4.8
        ),
        IngredientNutrition(name="olio", grams=20, kcal=180, protein_g=0, carbs_g=0, fat_g=20),
    ],
    note="Olio q.b. contato 10 g a porzione.",
)


@pytest.fixture
def recipe(user):
    serializer = RecipeSerializer(
        data={
            "title": "Pasta all'olio",
            "servings": 2,
            "ingredients": [
                {"name": "pasta", "quantity": "320", "unit": "g"},
                {"name": "olio extravergine di oliva", "unit": "to_taste"},
                {"name": "peperoncino", "quantity": "1", "unit": "pz", "optional": True},
            ],
        },
        context={},
    )
    serializer.is_valid(raise_exception=True)
    return serializer.save(owner=user)


@pytest.fixture
def gemini(monkeypatch):
    seen = {}

    def fake_generate(contents, schema, **kwargs):
        seen["prompt"] = contents(None)[0]
        return STIMA, "gemini-finto"

    monkeypatch.setattr("apps.recipes.nutrition.generate", fake_generate)
    return seen


def _estimate(api, user, recipe, capture):
    with override_settings(GEMINI_API_KEY="k"), capture(execute=True):
        response = api(user).post(f"/api/recipes/{recipe.id}/nutrition")
    assert response.status_code == 202, response.data
    return Job.objects.get(pk=response.data["id"])


def test_stima_a_porzione(user, api, recipe, gemini, django_capture_on_commit_callbacks):
    job = _estimate(api, user, recipe, django_capture_on_commit_callbacks)
    assert job.status == Job.Status.READY, job.error
    # Le somme e la divisione per porzioni le fa il codice.
    recipe.refresh_from_db()
    assert recipe.kcal == 660  # (1139 + 180) / 2
    assert recipe.protein_g == Decimal("20.3")
    assert recipe.carbs_g == Decimal("115.1")
    assert recipe.fat_g == Decimal("12.4")
    assert recipe.nutrition_source == "ai"
    assert recipe.nutrition_detail["note"].startswith("Olio")
    assert job.result["recipe"]["kcal"] == 660
    # Il facoltativo non va all'LLM, il q.b. si'.
    assert "peperoncino" not in gemini["prompt"]
    assert "q.b." in gemini["prompt"]


def test_senza_chiave_e_senza_ingredienti(user, api, recipe):
    assert api(user).post(f"/api/recipes/{recipe.id}/nutrition").status_code == 503
    recipe.ingredients.all().delete()
    with override_settings(GEMINI_API_KEY="k"):
        assert api(user).post(f"/api/recipes/{recipe.id}/nutrition").status_code == 400


def test_stima_degli_altri_no(user, other_user, api, recipe):
    with override_settings(GEMINI_API_KEY="k"):
        assert api(other_user).post(f"/api/recipes/{recipe.id}/nutrition").status_code == 404


def test_ingredienti_cambiati_tolgono_la_stima(
    user, api, recipe, gemini, django_capture_on_commit_callbacks
):
    _estimate(api, user, recipe, django_capture_on_commit_callbacks)
    url = f"/api/recipes/{recipe.id}"
    current = api(user).get(url).data
    # Il form rimanda tutto uguale (anche "ai"): la stima resta.
    same = {
        "title": current["title"],
        "servings": 2,
        "kcal": current["kcal"],
        "protein_g": current["protein_g"],
        "carbs_g": current["carbs_g"],
        "fat_g": current["fat_g"],
        "nutrition_source": "ai",
        "ingredients": [
            {
                "ingredient_id": line["ingredient"]["id"],
                **{k: line[k] for k in ("quantity", "unit", "note", "optional")},
            }
            for line in current["ingredients"]
        ],
    }
    data = api(user).patch(url, same, format="json").data
    assert data["nutrition_source"] == "ai" and data["kcal"] == 660
    # Porzioni cambiate: la stima a porzione non vale piu'.
    data = api(user).patch(url, {**same, "servings": 4}, format="json").data
    assert data["nutrition_source"] == "" and data["kcal"] is None
    assert data["nutrition_detail"] == {}


def test_valori_scritti_a_mano(user, api, recipe):
    url = f"/api/recipes/{recipe.id}"
    data = api(user).patch(url, {"kcal": 500, "protein_g": "18.5"}, format="json").data
    assert data["nutrition_source"] == "manual"
    assert data["kcal"] == 500 and data["protein_g"] == "18.5"
    # "ai" non lo scrive il client.
    response = api(user).patch(url, {"nutrition_source": "ai"}, format="json")
    assert response.status_code == 400
    # Tolti tutti: non calcolati.
    data = api(user).patch(url, {"kcal": None, "protein_g": None}, format="json").data
    assert data["nutrition_source"] == ""


def test_valori_scritti_nella_ricetta_letta(user):
    letta = ImportedRecipe(
        title="Torta",
        servings=8,
        ingredients=[ImportedIngredient(name="farina", quantity="300", unit="g")],
        steps=["Inforna."],
        nutrition=ImportedNutrition(kcal=2400, protein_g=48, carbs_g=320, fat_g=96, per="recipe"),
    )
    draft = to_draft(letta, user)
    assert draft["kcal"] == 300 and draft["protein_g"] == "6.0"
    assert draft["nutrition_source"] == "recipe"
    # Confermata dalla revisione: resta "dalla ricetta".
    serializer = RecipeSerializer(data=draft, context={})
    serializer.is_valid(raise_exception=True)
    saved = serializer.save(owner=user)
    assert saved.nutrition_source == "recipe" and saved.kcal == 300
    # Per 100 g non si convertono.
    letta.nutrition.per = "100g"
    assert "kcal" not in to_draft(letta, user)


def test_la_copia_tiene_i_valori(user, other_user, recipe):
    from apps.recipes.sharing import copy_recipe

    Recipe.objects.filter(pk=recipe.pk).update(
        kcal=400, protein_g=10, nutrition_source="ai", nutrition_detail={"note": "x"}
    )
    recipe.refresh_from_db()
    copy = copy_recipe(recipe, other_user)
    assert copy.kcal == 400 and copy.nutrition_source == "ai"
