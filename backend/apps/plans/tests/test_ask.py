"""Chiedi a Languorino (ADR 0016): contesto dal profilo e dal piano, risposta finta."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.test import override_settings

from apps.jobs.models import Job
from apps.plans.ask import AskReply, ask, nutritionist_text, plan_text
from apps.plans.models import MealPlan, NutritionistPlan, PlannedMeal
from apps.profiles.models import FoodPreference, Profile
from apps.recipes.serializers import RecipeSerializer

pytestmark = pytest.mark.django_db
URL = "/api/ask"
TODAY = date.today()


@pytest.fixture
def gemini(monkeypatch):
    state = {"prompts": []}

    def fake(contents, schema, **kwargs):
        state["prompts"].append(contents(None)[-1])
        state["kwargs"] = kwargs
        return AskReply(reply="  80 g a pranzo + 70 g a cena = 150 g di pasta.  "), "finto"

    monkeypatch.setattr("apps.plans.ask.generate", fake)
    return state


def _recipe(user, title, ingredients, servings=2):
    serializer = RecipeSerializer(
        data={
            "title": title,
            "servings": servings,
            "meal_slots": ["lunch", "dinner"],
            "ingredients": [
                {"name": name, "quantity": quantity, "unit": unit}
                for name, quantity, unit in ingredients
            ],
        },
        context={},
    )
    serializer.is_valid(raise_exception=True)
    return serializer.save(owner=user)


@pytest.fixture
def plan(user):
    plan = MealPlan.objects.create(
        owner=user, start_date=TODAY - timedelta(days=2), days=14, status=MealPlan.Status.ACTIVE
    )
    lunch = _recipe(user, "Pasta e zucchine", [("pasta", "160", "g"), ("zucchine", "1", "pz")])
    dinner = _recipe(user, "Pasta al pesto", [("pasta", "140", "g"), ("olio", "2", "tbsp")])
    far = _recipe(user, "Risotto", [("riso", "160", "g")])
    PlannedMeal.objects.create(
        plan=plan,
        date=TODAY,
        slot="lunch",
        recipe=lunch,
        servings=2,
        cooked_on=TODAY - timedelta(1),
    )
    PlannedMeal.objects.create(plan=plan, date=TODAY, slot="dinner", recipe=dinner, cooked_on=TODAY)
    PlannedMeal.objects.create(
        plan=plan,
        date=TODAY + timedelta(1),
        slot="dinner",
        note="Niente di adatto",
        cooked_on=TODAY + timedelta(1),
    )
    # Fuori dalla finestra della chat: non deve finire nel prompt.
    PlannedMeal.objects.create(
        plan=plan,
        date=TODAY + timedelta(10),
        slot="lunch",
        recipe=far,
        cooked_on=TODAY + timedelta(10),
    )
    return plan


def test_piano_con_grammature_a_persona_e_totale(user, plan):
    text = plan_text(plan, TODAY)
    assert "(oggi):" in text
    # 160 g per 2 porzioni = 80 g a persona; la zucchina anche in grammi, se il
    # catalogo lo sa.
    assert "- pranzo: Pasta e zucchine (per 2 persone, cucinato" in text
    assert "a persona: pasta 80 g; zucchina 0.5 pz (~100 g)" in text
    assert "- cena: Pasta al pesto (per 1 persona)" in text
    assert "a persona: pasta 70 g; olio extravergine d'oliva 1 tbsp (~15 ml)" in text
    # Il totale del giorno lo fa il codice: 80 + 70.
    assert "totale del giorno a persona:" in text
    assert "pasta 150 g; zucchina 100 g" in text
    assert "- cena: nessuna ricetta (Niente di adatto)" in text
    assert "Risotto" not in text
    assert "solo i giorni" in text


def test_senza_piano():
    assert plan_text(None, TODAY) == "Nessun piano attivo."


def test_nutrizionista_del_piano_o_ultimo_confermato(user, plan):
    assert nutritionist_text(plan, user) == "Nessuno."
    NutritionistPlan.objects.create(owner=user, title="Bozza", rules={"meals": []})
    assert nutritionist_text(plan, user) == "Nessuno."
    NutritionistPlan.objects.create(
        owner=user,
        title="Piano di novembre",
        status=NutritionistPlan.Status.CONFIRMED,
        rules={
            "meals": [{"slot": "lunch", "options": ["80 g pasta integrale + verdure"]}],
            "weekly": [{"food": "legumi", "times": 3}],
            "free_foods": ["verdure"],
            "avoid_foods": ["alcol"],
            "notes": "2 litri d'acqua",
        },
    )
    text = nutritionist_text(plan, user)
    assert "Piano di novembre (alla lettera)" in text
    assert "· 80 g pasta integrale + verdure" in text
    assert "legumi 3 volte" in text
    assert "Da evitare: alcol" in text


def test_prompt_con_profilo_senza_nome(user, plan, gemini):
    profile = Profile.objects.create(user=user, first_name="Giulia", goals=["eat_better"])
    FoodPreference.objects.create(profile=profile, kind="allergy", label="noci")
    result = ask(user, [{"role": "user", "text": "Quanta pasta tra pranzo e cena?"}])
    assert result == {
        "reply": "80 g a pranzo + 70 g a cena = 150 g di pasta.",
        "model": "finto",
    }
    prompt = gemini["prompts"][0]
    assert "Giulia" not in prompt
    assert "noci" in prompt
    assert "Pasta al pesto" in prompt
    assert "Persona: Quanta pasta tra pranzo e cena?" in prompt
    assert gemini["kwargs"]["fast"] is True


def test_api_crea_il_job(user, api, plan, gemini, django_capture_on_commit_callbacks):
    messages = [
        {"role": "assistant", "text": "Chiedimi pure."},
        {"role": "user", "text": "Cosa ceno stasera?"},
    ]
    with override_settings(GEMINI_API_KEY="k"), django_capture_on_commit_callbacks(execute=True):
        response = api(user).post(URL, {"messages": messages}, format="json")
    assert response.status_code == 202, response.data
    job = Job.objects.get(id=response.data["id"])
    assert (job.kind, job.status) == ("ask", "ready"), job.error
    assert job.result == {"reply": "80 g a pranzo + 70 g a cena = 150 g di pasta."}
    assert job.model == "finto"


def test_api_vuole_una_domanda(user, api):
    with override_settings(GEMINI_API_KEY="k"):
        response = api(user).post(
            URL, {"messages": [{"role": "assistant", "text": "Ciao"}]}, format="json"
        )
    assert response.status_code == 400


def test_api_senza_chiave(user, api):
    with override_settings(GEMINI_API_KEY=""):
        response = api(user).post(
            URL, {"messages": [{"role": "user", "text": "Ciao"}]}, format="json"
        )
    assert response.status_code == 503


def test_api_solo_utenti_loggati(api):
    assert api().post(URL, {"messages": []}, format="json").status_code == 401
