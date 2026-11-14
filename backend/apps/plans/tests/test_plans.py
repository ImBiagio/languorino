"""Piano alimentare: calendario del prep, candidati, generazione (finta), API."""

from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from django.test import override_settings

from apps.ai.client import AIOverloaded
from apps.plans.generation import candidate_recipes
from apps.plans.models import MealPlan, PlannedMeal
from apps.plans.schedule import cook_on, schedule
from apps.plans.tasks import resume_stalled_plans
from apps.profiles.models import FoodPreference, Profile
from apps.recipes.importing import ImportedIngredient, ImportedRecipe
from apps.recipes.models import Recipe, RecipeBook

pytestmark = pytest.mark.django_db
PLANS = "/api/plans"
MONDAY = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)


# --- calendario del prep -------------------------------------------------------------------


def test_cucino_al_momento():
    assert cook_on(MONDAY, "lunch", start=MONDAY, mode="none") == MONDAY


def test_la_sera_prima():
    assert cook_on(MONDAY, "lunch", start=MONDAY, mode="evening_before") == MONDAY - timedelta(1)
    assert cook_on(MONDAY, "dinner", start=MONDAY, mode="evening_before") == MONDAY
    assert cook_on(MONDAY, "breakfast", start=MONDAY, mode="evening_before") == MONDAY


def test_ogni_tre_giorni():
    days = [MONDAY + timedelta(n) for n in range(7)]
    cooked = [cook_on(day, "dinner", start=MONDAY, mode="every_3") for day in days]
    assert cooked == [MONDAY] * 3 + [MONDAY + timedelta(3)] * 3 + [MONDAY + timedelta(6)]


def test_domenica_e_mercoledi():
    days = [MONDAY + timedelta(n) for n in range(7)]
    cooked = [cook_on(day, "lunch", start=MONDAY, mode="weekend") for day in days]
    sunday, wednesday = MONDAY - timedelta(1), MONDAY + timedelta(2)
    assert cooked == [
        sunday,
        sunday,
        wednesday,
        wednesday,
        wednesday,
        wednesday,
        MONDAY + timedelta(6),
    ]


def test_attesa_nel_calendario():
    rows = schedule(MONDAY, [MONDAY + timedelta(1)], ["dinner", "lunch"], "every_2")
    assert [(row["slot"], row["wait"]) for row in rows] == [("lunch", 1), ("dinner", 1)]


# --- dati di prova -----------------------------------------------------------------------


def _recipe(
    user,
    title,
    ingredients=("ceci in scatola",),
    tags=(),
    keeps=3,
    slots=("lunch", "dinner"),
    **extra,
):
    from apps.recipes.serializers import RecipeSerializer

    data = {
        "title": title,
        "servings": 2,
        "meal_slots": list(slots),
        "keeps_days": keeps,
        "tags": list(tags),
        "ingredients": [{"name": name, "quantity": "100", "unit": "g"} for name in ingredients],
    }
    serializer = RecipeSerializer(data=data, context={})
    serializer.is_valid(raise_exception=True)
    return serializer.save(owner=user, **extra)


@pytest.fixture
def cookbook(user):
    return {
        "ceci": _recipe(user, "Zuppa di ceci", tags=["legumi"]),
        "salmone": _recipe(user, "Salmone al forno", ["salmone"], keeps=1),
        "frittata": _recipe(user, "Frittata", ["uova"], tags=["veloce"]),
        "pasta": _recipe(
            user, "Pasta al pomodoro", ["pasta", "passata di pomodoro"], tags=["del cuore"]
        ),
        "porridge": _recipe(user, "Porridge", ["fiocchi d'avena", "latte"], slots=["breakfast"]),
    }


def _settings(**extra):
    base = {
        "start_date": MONDAY.isoformat(),
        "days": 7,
        "slots": ["lunch", "dinner"],
        "servings": 2,
        "prep_mode": "none",
        "minutes": 45,
        "difficulty": "medium",
    }
    return {**base, **extra}


# --- candidati -----------------------------------------------------------------------------


def _plan(user, **extra):
    from apps.plans.serializers import PlanSettingsSerializer

    class Request:
        pass

    request = Request()
    request.user = user
    options = PlanSettingsSerializer(data=_settings(**extra), context={"request": request})
    options.is_valid(raise_exception=True)
    return MealPlan.objects.create(
        owner=user,
        start_date=MONDAY,
        days=options.validated_data["days"],
        settings=options.to_settings(),
    )


def test_candidati_senza_allergie_e_tag_esclusi(user, cookbook):
    profile = Profile.objects.create(user=user)
    FoodPreference.objects.create(profile=profile, kind="allergy", label="eggs", allergen="eggs")
    FoodPreference.objects.create(profile=profile, kind="dislike", label="salmone")
    plan = _plan(user, exclude_tags=["Del cuore"])
    titles = {recipe.title: getattr(recipe, "dislikes", []) for recipe in candidate_recipes(plan)}
    assert set(titles) == {"Zuppa di ceci", "Salmone al forno", "Porridge"}
    assert titles["Salmone al forno"] == ["salmone"]


def test_candidati_solo_con_i_tag_inclusi(user, cookbook):
    plan = _plan(user, include_tags=["veloce", "legumi"])
    assert {r.title for r in candidate_recipes(plan)} == {"Zuppa di ceci", "Frittata"}


def test_candidati_dai_ricettari_pdf(user, cookbook):
    book = RecipeBook.objects.create(owner=user, title="PDF", page_count=1)
    _recipe(user, "Vellutata dal PDF", ["zucca"], book=book, in_cookbook=False, status="draft")
    _recipe(
        user,
        "Altro PDF",
        ["zucca"],
        book=RecipeBook.objects.create(owner=user, title="B"),
        in_cookbook=False,
    )
    only_book = _plan(user, use_cookbook=False, books=[str(book.id)])
    assert {r.title for r in candidate_recipes(only_book)} == {"Vellutata dal PDF"}
    both = _plan(user, books=[str(book.id)])
    assert "Vellutata dal PDF" in {r.title for r in candidate_recipes(both)}
    assert "Altro PDF" not in {r.title for r in candidate_recipes(both)}


# --- generazione con Gemini finto ---------------------------------------------------------------


SLOT_LINE = re.compile(r"- (\d{4}-\d\d-\d\d) \([^)]*\), [^[]+\[(\w+)\], attesa (\d+)")
CANDIDATE = re.compile(r"\[(\d+)\] ([^—\n]+?) —")


@pytest.fixture
def gemini(monkeypatch):
    """``state["pick"](titolo_candidati, slot, giorno)`` -> numero o titolo nuovo."""
    from apps.plans import generation
    from apps.plans.generation import MealChoice, WeekChoices

    state = {"prompts": [], "new": [], "overloaded": 0, "pick": None}

    def fake_generate(contents, schema, **kwargs):
        prompt = contents(None)[0]
        state["prompts"].append(prompt)
        if schema is ImportedRecipe:
            title = re.search(r'ricetta "([^"]+)"', prompt).group(1)
            state["new"].append(title)
            ingredient = "uova" if "uova" in title.lower() else "zucchina"
            return ImportedRecipe(
                title=title,
                servings=2,
                prep_minutes=10,
                cook_minutes=10,
                keeps_days=2,
                ingredients=[ImportedIngredient(name=ingredient, quantity="200", unit="g")],
                steps=["Cuoci."],
                tags=["nuova"],
            ), "finto"
        if state["overloaded"]:
            state["overloaded"] -= 1
            raise AIOverloaded("Gemini è sovraccarico.")
        candidates = {title.strip(): int(n) for n, title in CANDIDATE.findall(prompt)}
        meals = []
        for day, slot, wait in SLOT_LINE.findall(prompt):
            choice = state["pick"](candidates, slot, date.fromisoformat(day), int(wait))
            if isinstance(choice, int):
                meals.append(MealChoice(date=day, slot=slot, recipe=choice))
            elif choice:
                meals.append(MealChoice(date=day, slot=slot, new_recipe=choice, idea="leggera"))
        return WeekChoices(meals=meals), "finto"

    monkeypatch.setattr(generation, "generate", fake_generate)
    monkeypatch.setattr("apps.plans.tasks.OVERLOAD_PAUSE", 0)
    return state


def _create(api, user, capture, **extra):
    with override_settings(GEMINI_API_KEY="k"), capture(execute=True):
        return api(user).post(PLANS, _settings(**extra), format="json")


def test_settimana_generata(user, api, cookbook, gemini, django_capture_on_commit_callbacks):
    def pick(candidates, slot, day, wait):
        if slot == "lunch":
            return candidates["Zuppa di ceci"]
        return "Zucchine ripiene" if day.weekday() < 3 else candidates["Frittata"]

    gemini["pick"] = pick
    response = _create(api, user, django_capture_on_commit_callbacks)
    assert response.status_code == 202, response.data
    plan = MealPlan.objects.get()
    assert (plan.status, plan.weeks_done) == (MealPlan.Status.DRAFT, 1)
    meals = list(plan.meals.select_related("recipe"))
    assert len(meals) == 14
    assert {meal.servings for meal in meals} == {2}
    # Una ricetta nuova scritta una volta sola per tre cene, fuori dal ricettario.
    assert gemini["new"] == ["Zucchine ripiene"]
    new = Recipe.objects.get(title="Zucchine ripiene")
    assert (new.source, new.in_cookbook, new.status) == ("plan", False, "draft")
    assert sum(1 for meal in meals if meal.recipe_id == new.id) == 3
    # Nel prompt c'e' il profilo ridotto, mai email o nome.
    assert user.email not in gemini["prompts"][0]
    detail = api(user).get(f"{PLANS}/{plan.id}").data
    assert len(detail["meals"]) == 14
    assert detail["meals"][0]["recipe"]["title"]


def test_ricetta_nuova_con_allergene_scartata(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    profile = Profile.objects.create(user=user)
    FoodPreference.objects.create(profile=profile, kind="allergy", label="eggs", allergen="eggs")
    gemini["pick"] = lambda c, slot, day, wait: (
        "Torta di uova" if slot == "dinner" else c["Zuppa di ceci"]
    )
    _create(api, user, django_capture_on_commit_callbacks)
    plan = MealPlan.objects.get()
    # L'LLM l'ha scritta con le uova: il codice la toglie e riempie le cene con
    # ricette gia' sicure (mai la frittata, che ha le uova).
    assert not Recipe.all_objects.filter(title="Torta di uova").exists()
    dinners = plan.meals.filter(slot="dinner").select_related("recipe")
    assert all(meal.recipe_id for meal in dinners)
    assert "Frittata" not in {meal.recipe.title for meal in dinners}
    # Nel prompt della ricetta nuova c'era il divieto.
    assert any("NON deve contenere" in p and "eggs" in p for p in gemini["prompts"])


def test_prep_e_giorni_in_frigo(user, api, cookbook, gemini, django_capture_on_commit_callbacks):
    # Il salmone regge un giorno: con attesa 2 si cucina il giorno stesso.
    gemini["pick"] = lambda c, slot, day, wait: (
        c["Salmone al forno"] if wait == 2 else c["Zuppa di ceci"]
    )
    _create(api, user, django_capture_on_commit_callbacks, prep_mode="every_3")
    plan = MealPlan.objects.get()
    salmon = plan.meals.filter(recipe__title="Salmone al forno")
    assert salmon.exists()
    assert all(meal.cooked_on == meal.date and meal.note for meal in salmon)
    soup = plan.meals.get(date=MONDAY + timedelta(1), slot="lunch")
    assert soup.cooked_on == MONDAY  # ceci: tre giorni in frigo, si prepara lunedi'


def test_un_mese_a_settimane(user, api, cookbook, gemini, django_capture_on_commit_callbacks):
    gemini["pick"] = lambda c, slot, day, wait: c["Zuppa di ceci"]
    _create(api, user, django_capture_on_commit_callbacks, days=28)
    plan = MealPlan.objects.get()
    assert (plan.status, plan.weeks_done, plan.meals.count()) == ("draft", 4, 56)
    week_prompts = [p for p in gemini["prompts"] if "Pasti da riempire" in p]
    assert len(week_prompts) == 4
    # Dalla seconda settimana sa cosa ha gia' messo.
    assert "ha gia' mangiato: Zuppa di ceci" in week_prompts[1]


def test_gemini_sovraccarico_riprova(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["overloaded"] = 2
    gemini["pick"] = lambda c, slot, day, wait: c["Frittata"]
    _create(api, user, django_capture_on_commit_callbacks)
    assert MealPlan.objects.get().status == "draft"


def test_varieta_calcolata_dal_codice(user, cookbook):
    from apps.plans.generation import variety_needs
    from apps.plans.schedule import plan_dates

    days = plan_dates(MONDAY, 7)
    rows = schedule(MONDAY, days, ["breakfast", "lunch", "dinner"], "none")
    candidates = list(Recipe.objects.filter(owner=user))
    # 14 pranzi e cene: almeno 7 ricette diverse, ce ne sono 4 -> 3 nuove;
    # 7 colazioni: almeno 3 diverse, c'e' solo il porridge -> 2 nuove.
    assert variety_needs(rows, candidates) == {"main": 3, "other": 2}


def test_prompt_chiede_le_ricette_che_mancano(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["pick"] = lambda c, slot, day, wait: (
        c["Frittata"] if slot != "breakfast" else c["Porridge"]
    )
    _create(api, user, django_capture_on_commit_callbacks, slots=["breakfast", "lunch", "dinner"])
    week = next(p for p in gemini["prompts"] if "Pasti da riempire" in p)
    assert "inventa ALMENO 3 ricette nuove per pranzi e cene" in week
    assert "inventa ALMENO 2 ricette nuove per colazioni" in week


def test_pasti_saltati_riempiti_dal_codice(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    # L'LLM riempie solo il lunedi': il resto lo completa il codice, senza
    # mai usare ricette vietate e rispettando il pasto (niente porridge a cena).
    def pick(c, slot, day, wait):
        if day != MONDAY:
            return None
        return c["Porridge"] if slot == "breakfast" else c["Zuppa di ceci"]

    gemini["pick"] = pick
    _create(api, user, django_capture_on_commit_callbacks, slots=["breakfast", "lunch", "dinner"])
    plan = MealPlan.objects.get()
    meals = list(plan.meals.select_related("recipe"))
    assert all(meal.recipe_id for meal in meals)
    breakfasts = {meal.recipe.title for meal in meals if meal.slot == "breakfast"}
    assert breakfasts == {"Porridge"}
    mains = [meal.recipe.title for meal in meals if meal.slot != "breakfast"]
    assert "Porridge" not in mains
    # Le meno usate prima: le quattro ricette di pranzo/cena girano.
    assert len(set(mains)) == 4


def test_piatti_esclusi_nominati_nel_prompt(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["pick"] = lambda c, slot, day, wait: c["Frittata"]
    _create(api, user, django_capture_on_commit_callbacks, exclude_tags=["del cuore"])
    week = next(p for p in gemini["prompts"] if "Pasti da riempire" in p)
    assert "nemmeno come ricetta nuova: Pasta al pomodoro" in week


def test_senza_ricette_le_inventa(user, api, gemini, django_capture_on_commit_callbacks):
    gemini["pick"] = lambda c, slot, day, wait: f"Piatto {slot} {day.weekday()}"
    _create(api, user, django_capture_on_commit_callbacks, days=7, slots=["dinner"])
    plan = MealPlan.objects.get()
    assert plan.meals.filter(recipe__isnull=False).count() == 7
    assert len(gemini["new"]) == 7


# --- API ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"days": 10},
        {"slots": []},
        {"servings": 0},
        {"prep_mode": "boh"},
        {"start_date": (date.today() - timedelta(days=5)).isoformat()},
        {"use_cookbook": False},
        {"books": ["00000000-0000-0000-0000-000000000000"]},
    ],
)
def test_scelte_rifiutate(user, api, extra):
    with override_settings(GEMINI_API_KEY="k"):
        assert api(user).post(PLANS, _settings(**extra), format="json").status_code == 400


@override_settings(GEMINI_API_KEY="")
def test_senza_chiave(user, api):
    assert api(user).post(PLANS, _settings(), format="json").status_code == 503


def test_attivare_archivia_il_precedente(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["pick"] = lambda c, slot, day, wait: c["Frittata"]
    first = _create(api, user, django_capture_on_commit_callbacks).data["id"]
    second = _create(api, user, django_capture_on_commit_callbacks).data["id"]
    assert api(user).post(f"{PLANS}/{first}/activate").data["status"] == "active"
    assert api(user).post(f"{PLANS}/{second}/activate").status_code == 200
    assert MealPlan.objects.get(id=first).status == "archived"
    # Il piano corrente: quello attivo (qui parte lunedi' prossimo).
    assert api(user).get(f"{PLANS}/current").data["id"] == second


def test_nessun_piano_corrente(user, api):
    assert api(user).get(f"{PLANS}/current").status_code == 204


def test_cambiare_un_pasto(
    user, other_user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["pick"] = lambda c, slot, day, wait: c["Frittata"]
    plan_id = _create(api, user, django_capture_on_commit_callbacks).data["id"]
    meal = PlannedMeal.objects.filter(plan_id=plan_id).first()
    url = f"{PLANS}/{plan_id}/meals/{meal.id}"
    response = api(user).patch(
        url, {"recipe_id": str(cookbook["ceci"].id), "servings": 3}, format="json"
    )
    assert response.status_code == 200, response.data
    assert (response.data["recipe"]["title"], response.data["servings"]) == ("Zuppa di ceci", 3)
    assert api(user).patch(url, {"recipe_id": None}, format="json").data["recipe"] is None
    late = (meal.date + timedelta(1)).isoformat()
    assert api(user).patch(url, {"cooked_on": late}, format="json").status_code == 400
    foreign = _recipe(other_user, "Non mia")
    assert api(user).patch(url, {"recipe_id": str(foreign.id)}, format="json").status_code == 404
    assert api(other_user).patch(url, {"servings": 1}, format="json").status_code == 404


def test_rifare_e_eliminare(user, api, cookbook, gemini, django_capture_on_commit_callbacks):
    gemini["pick"] = lambda c, slot, day, wait: "Zucchine ripiene"
    plan_id = _create(api, user, django_capture_on_commit_callbacks).data["id"]
    gemini["pick"] = lambda c, slot, day, wait: c["Frittata"]
    with override_settings(GEMINI_API_KEY="k"), django_capture_on_commit_callbacks(execute=True):
        assert api(user).post(f"{PLANS}/{plan_id}/regenerate").status_code == 202
    plan = MealPlan.objects.get()
    assert set(plan.meals.values_list("recipe__title", flat=True)) == {"Frittata"}
    assert api(user).delete(f"{PLANS}/{plan_id}").status_code == 204
    assert not MealPlan.all_objects.exists()
    # Le ricette scritte per il piano e mai salvate se ne vanno; il ricettario resta.
    assert Recipe.objects.filter(in_cookbook=True).count() == 5


def test_piani_degli_altri(
    user, other_user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["pick"] = lambda c, slot, day, wait: c["Frittata"]
    plan_id = _create(api, user, django_capture_on_commit_callbacks).data["id"]
    assert api(other_user).get(PLANS).data == []
    assert api(other_user).get(f"{PLANS}/{plan_id}").status_code == 404
    assert api(other_user).post(f"{PLANS}/{plan_id}/activate").status_code == 404
    assert api(other_user).delete(f"{PLANS}/{plan_id}").status_code == 404


def test_piani_fermi_ripresi(user, cookbook, gemini, django_capture_on_commit_callbacks):
    from django.utils import timezone

    gemini["pick"] = lambda c, slot, day, wait: c["Frittata"]
    plan = _plan(user)
    MealPlan.objects.filter(id=plan.id).update(updated_at=timezone.now() - timedelta(hours=1))
    with django_capture_on_commit_callbacks(execute=True):
        assert resume_stalled_plans() == 1
    plan.refresh_from_db()
    assert plan.status == "draft"


# --- piano del nutrizionista (ADR 0010) ----------------------------------------------------


NUTRITIONIST = "/api/nutritionist-plans"


def _photo():
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buffer, "JPEG")
    return SimpleUploadedFile("piano.jpg", buffer.getvalue(), content_type="image/jpeg")


@pytest.fixture
def reading(monkeypatch, settings, tmp_path):
    from apps.plans.nutritionist import NutritionistMeal, NutritionistReading, WeeklyFrequency

    settings.MEDIA_ROOT = tmp_path
    state = {"result": None, "prompts": []}

    def fake_generate(contents, schema, **kwargs):
        class Types:
            class Part:
                @staticmethod
                def from_bytes(data, mime_type):
                    return mime_type

        state["prompts"].append(contents(Types)[-1])
        return state["result"] or NutritionistReading(
            title="Piano di novembre",
            valid_from="2026-11-01",
            valid_to="non so",
            meals=[
                NutritionistMeal(slot="dinner", options=["150 g pesce + verdure"]),
                NutritionistMeal(
                    slot="lunch",
                    options=["80 g pasta integrale + verdure", " 80 g  pasta integrale + verdure"],
                ),
                NutritionistMeal(slot="breakfast", options=[]),
            ],
            weekly=[
                WeeklyFrequency(food="legumi", times=3),
                WeeklyFrequency(food="Legumi", times=2),
                WeeklyFrequency(food="dolci", times=0),
            ],
            avoid_foods=["salumi", "salumi", "zucchero"],
        ), "finto"

    monkeypatch.setattr("apps.plans.nutritionist.generate", fake_generate)
    return state


def _upload(api, user, capture):
    with override_settings(GEMINI_API_KEY="k"), capture(execute=True):
        return api(user).post(NUTRITIONIST, {"files": [_photo()]}, format="multipart")


def test_piano_del_nutrizionista_letto(user, api, reading, django_capture_on_commit_callbacks):
    from apps.jobs.models import Job
    from apps.plans.models import NutritionistPlan

    response = _upload(api, user, django_capture_on_commit_callbacks)
    assert response.status_code == 202, response.data
    job = Job.objects.get(id=response.data["id"])
    assert job.status == Job.Status.READY
    plan = NutritionistPlan.objects.get()
    assert job.result == {"nutritionist_plan": str(plan.id), "problem": ""}
    assert (plan.title, plan.status, plan.strict) == ("Piano di novembre", "draft", True)
    assert (plan.valid_from, plan.valid_to) == (date(2026, 11, 1), None)
    # Pasti nell'ordine della giornata, niente doppioni ne' pasti vuoti.
    assert plan.rules["meals"] == [
        {"slot": "lunch", "options": ["80 g pasta integrale + verdure"]},
        {"slot": "dinner", "options": ["150 g pesce + verdure"]},
    ]
    assert plan.rules["weekly"] == [{"food": "legumi", "times": 3}]
    assert plan.rules["avoid_foods"] == ["salumi", "zucchero"]
    detail = api(user).get(f"{NUTRITIONIST}/{plan.id}").data
    assert detail["files"] == [{"original_name": "piano.jpg", "content_type": "image/jpeg"}]


def test_file_senza_piano(user, api, reading, django_capture_on_commit_callbacks):
    from apps.jobs.models import Job
    from apps.plans.models import NutritionistPlan
    from apps.plans.nutritionist import NutritionistReading

    reading["result"] = NutritionistReading(problem="È una ricetta, non un piano.")
    response = _upload(api, user, django_capture_on_commit_callbacks)
    job = Job.objects.get(id=response.data["id"])
    assert job.result == {"problem": "È una ricetta, non un piano."}
    assert not NutritionistPlan.objects.exists()


def test_rivedere_e_confermare(user, other_user, api, reading, django_capture_on_commit_callbacks):
    from apps.jobs.models import Job

    _upload(api, user, django_capture_on_commit_callbacks)
    plan_id = api(user).get(NUTRITIONIST).data[0]["id"]
    url = f"{NUTRITIONIST}/{plan_id}"
    assert api(other_user).get(url).status_code == 404
    bad = api(user).patch(url, {"rules": {"meals": [{"slot": "brunch"}]}}, format="json")
    assert bad.status_code == 400
    empty = api(user).patch(url, {"rules": {"meals": []}}, format="json")
    assert empty.status_code == 200
    assert api(user).post(f"{url}/confirm").status_code == 400
    rules = {
        "meals": [{"slot": "lunch", "options": ["70 g riso + legumi"]}],
        "avoid_foods": ["salmone"],
    }
    changed = api(user).patch(url, {"rules": rules, "strict": False}, format="json")
    assert changed.data["rules"]["avoid_foods"] == ["salmone"]
    assert changed.data["strict"] is False
    confirmed = api(user).post(f"{url}/confirm")
    assert confirmed.data["status"] == "confirmed"
    assert Job.objects.get().status == Job.Status.CONFIRMED


def test_generare_dal_piano_del_nutrizionista(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    from apps.plans.models import NutritionistPlan

    nutritionist = NutritionistPlan.objects.create(
        owner=user,
        title="Piano della dottoressa",
        rules={
            "meals": [{"slot": "lunch", "options": ["80 g pasta + verdure"]}],
            "substitutions": [
                {"group": "Carboidrati", "equivalents": ["80 g pasta", "100 g pane"], "note": ""}
            ],
            "weekly": [{"food": "legumi", "times": 3}],
            "avoid_foods": ["salmone", "uova"],
        },
    )
    # Ancora bozza: non si puo' usare.
    draft = _create(
        api, user, django_capture_on_commit_callbacks, nutritionist_plan=str(nutritionist.id)
    )
    assert draft.status_code == 400
    nutritionist.status = NutritionistPlan.Status.CONFIRMED
    nutritionist.save()

    def pick(candidates, slot, day, wait):
        assert "Salmone al forno" not in candidates and "Frittata" not in candidates
        return "Frittatona di uova" if day.weekday() == 0 else candidates["Zuppa di ceci"]

    gemini["pick"] = pick
    response = _create(
        api, user, django_capture_on_commit_callbacks, nutritionist_plan=str(nutritionist.id)
    )
    assert response.status_code == 202, response.data
    assert response.data["nutritionist"] == {
        "id": str(nutritionist.id),
        "title": "Piano della dottoressa",
    }
    week = gemini["prompts"][0]
    assert "Piano del nutrizionista" in week and "80 g pasta + verdure" in week
    assert "ALLA LETTERA" in week and "legumi 3 volte" in week
    # Le sostituzioni, con la grammatura di ogni equivalente, arrivano alla
    # settimana e alla ricetta nuova (prima stavano solo nelle note).
    assert "Carboidrati: 80 g pasta = 100 g pane" in week
    assert "grammatura scritta per l'equivalente" in week
    # La ricetta nuova con le uova (da evitare) e' scartata: il pasto lo riempie il codice.
    assert not Recipe.objects.filter(title="Frittatona di uova").exists()
    written = gemini["prompts"][1]
    assert "80 g pasta + verdure" in written and "evitare: salmone, uova" in written
    assert "80 g pasta = 100 g pane" in written
    plan = MealPlan.objects.get(id=response.data["id"])
    titles = {meal.recipe.title for meal in plan.meals.select_related("recipe") if meal.recipe}
    assert titles and not titles & {"Salmone al forno", "Frittata", "Frittatona di uova"}


def test_file_del_piano_del_nutrizionista_tenuti(
    user, api, reading, django_capture_on_commit_callbacks
):
    from django.utils import timezone

    from apps.jobs.models import JobFile
    from apps.jobs.tasks import clean_jobs

    _upload(api, user, django_capture_on_commit_callbacks)
    JobFile.objects.update(created_at=timezone.now() - timedelta(days=90))
    clean_jobs()
    assert JobFile.objects.count() == 1
    plan_id = api(user).get(NUTRITIONIST).data[0]["id"]
    assert api(user).delete(f"{NUTRITIONIST}/{plan_id}").status_code == 204
    assert not JobFile.objects.exists()


def test_alla_lettera_i_buchi_solo_con_le_scelte_dell_llm(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    from apps.plans.models import NutritionistPlan

    nutritionist = NutritionistPlan.objects.create(
        owner=user,
        title="Piano",
        status=NutritionistPlan.Status.CONFIRMED,
        rules={"meals": [{"slot": "lunch", "options": ["legumi"]}]},
    )

    def pick(candidates, slot, day, wait):
        # Sceglie solo il lunedi'; gli altri giorni li salta.
        return candidates["Zuppa di ceci"] if day.weekday() == 0 else None

    gemini["pick"] = pick
    response = _create(
        api,
        user,
        django_capture_on_commit_callbacks,
        slots=["lunch"],
        nutritionist_plan=str(nutritionist.id),
    )
    plan = MealPlan.objects.get(id=response.data["id"])
    titles = {meal.recipe.title for meal in plan.meals.select_related("recipe")}
    assert titles == {"Zuppa di ceci"}


def test_grammature_a_persona(user, api, gemini, django_capture_on_commit_callbacks):
    from apps.recipes.serializers import RecipeSerializer

    serializer = RecipeSerializer(
        data={
            "title": "Pasta e zucchine",
            "servings": 4,
            "meal_slots": ["lunch", "dinner"],
            "ingredients": [
                {"name": "pasta", "quantity": "320", "unit": "g"},
                {"name": "zucchine", "quantity": "2", "unit": "pz"},
                {"name": "olio extravergine d'oliva", "quantity": "2", "unit": "tbsp"},
                {"name": "sale", "unit": "to_taste"},
                {"name": "basilico", "quantity": "5", "unit": "g", "optional": True},
            ],
        },
        context={},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save(owner=user)
    gemini["pick"] = lambda candidates, slot, day, wait: candidates["Pasta e zucchine"]
    response = _create(api, user, django_capture_on_commit_callbacks, servings=2)
    meal = api(user).get(f"{PLANS}/{response.data['id']}").data["meals"][0]
    assert meal["servings"] == 2
    # A persona, non per le porzioni del pasto: senza "q.b." e facoltativi.
    assert meal["portion"] == [
        {"name": "pasta", "quantity": "80.00", "unit": "g"},
        {
            "name": "zucchina",
            "quantity": "0.50",
            "unit": "pz",
            "approx": {"quantity": "100", "unit": "g"},
        },
        {
            "name": "olio extravergine d'oliva",
            "quantity": "0.50",
            "unit": "tbsp",
            "approx": {"quantity": "8", "unit": "ml"},
        },
    ]


def test_la_sera_cucino_anche_il_pranzo_dopo(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    """Il pranzo e' l'avanzo della cena prima: una cottura sola, anche fra due settimane."""
    asked = []
    dinners = ["Zuppa di ceci", "Frittata", "Pasta al pomodoro"]

    def pick(candidates, slot, day, wait):
        asked.append((day, slot, wait))
        if slot == "lunch":
            return candidates["Frittata"]
        return candidates[dinners[day.toordinal() % 3]]

    gemini["pick"] = pick
    response = _create(
        api,
        user,
        django_capture_on_commit_callbacks,
        days=14,
        prep_mode="evening_before",
    )
    plan = MealPlan.objects.get(id=response.data["id"])
    assert plan.status == MealPlan.Status.DRAFT
    # A Gemini si chiede solo il primo pranzo; le cene devono reggere un giorno.
    assert [(day, slot) for day, slot, _w in asked if slot == "lunch"] == [(MONDAY, "lunch")]
    last = MONDAY + timedelta(days=13)
    assert all(wait == (0 if day == last else 1) for day, slot, wait in asked if slot == "dinner")
    meals = {(m.date, m.slot): m for m in plan.meals.select_related("recipe")}
    assert len(meals) == 28
    for offset in range(1, 14):
        day = MONDAY + timedelta(days=offset)
        lunch, dinner = meals[(day, "lunch")], meals[(day - timedelta(days=1), "dinner")]
        assert lunch.recipe_id == dinner.recipe_id, day
        assert lunch.cooked_on == dinner.cooked_on == day - timedelta(days=1)
    # Anche il pranzo del primo lunedi' della seconda settimana viene dalla domenica.
    second_monday = MONDAY + timedelta(days=7)
    assert (
        meals[(second_monday, "lunch")].recipe_id
        == meals[(second_monday - timedelta(days=1), "dinner")].recipe_id
    )


def test_alla_lettera_niente_pranzi_avanzo(user, cookbook):
    from apps.plans.generation import leftover_lunches
    from apps.plans.models import NutritionistPlan

    plan = _plan(user, prep_mode="evening_before")
    assert len(leftover_lunches(plan, None)) == 6
    strict = NutritionistPlan(owner=user, title="P", strict=True, rules={})
    assert leftover_lunches(plan, strict) == {}
    assert leftover_lunches(_plan(user, prep_mode="none"), None) == {}


@pytest.mark.parametrize(
    ("share", "phrase"),
    [(0, "Usa le ricette candidate"), (50, "Circa il 50%"), (100, "Non usare le candidate")],
)
def test_percentuale_di_ricette_nuove(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks, share, phrase
):
    gemini["pick"] = lambda candidates, slot, day, wait: candidates["Zuppa di ceci"]
    response = _create(api, user, django_capture_on_commit_callbacks, new_share=share)
    assert response.status_code == 202, response.data
    assert MealPlan.objects.get().settings["new_share"] == share
    assert phrase in gemini["prompts"][0]


def test_percentuale_non_ammessa(user, api):
    with override_settings(GEMINI_API_KEY="k"):
        response = api(user).post(PLANS, _settings(new_share=33), format="json")
    assert response.status_code == 400


def test_idee_per_un_pasto(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks, monkeypatch
):
    from apps.jobs.models import Job
    from apps.plans.models import NutritionistPlan
    from apps.recipes.importing import ImportedRecipes

    gemini["pick"] = lambda candidates, slot, day, wait: candidates["Zuppa di ceci"]
    nutritionist = NutritionistPlan.objects.create(
        owner=user,
        title="N",
        status=NutritionistPlan.Status.CONFIRMED,
        strict=False,
        rules={
            "meals": [{"slot": "dinner", "options": ["150 g pesce + verdure"]}],
            "avoid_foods": ["uova"],
        },
    )
    plan_id = _create(
        api, user, django_capture_on_commit_callbacks, nutritionist_plan=str(nutritionist.id)
    ).data["id"]
    meal = PlannedMeal.objects.filter(plan_id=plan_id, slot="dinner").first()
    prompts = []

    def fake(contents, schema, **kwargs):
        prompts.append((contents(None)[0], kwargs))
        return ImportedRecipes(
            recipes=[
                ImportedRecipe(
                    title="Orata al cartoccio",
                    servings=2,
                    ingredients=[ImportedIngredient(name="orata", quantity="300", unit="g")],
                    steps=["Inforna."],
                ),
                ImportedRecipe(
                    title="Frittata di zucchine",  # uova: il nutrizionista dice di evitarle
                    servings=2,
                    ingredients=[ImportedIngredient(name="uova", quantity="4", unit="pz")],
                    steps=["Sbatti."],
                ),
            ]
        ), "finto"

    monkeypatch.setattr("apps.plans.swap.generate", fake)
    url = f"{PLANS}/{plan_id}/meals/{meal.id}/ideas"
    with override_settings(GEMINI_API_KEY="k"), django_capture_on_commit_callbacks(execute=True):
        response = api(user).post(url, {"hint": "  qualcosa  col pesce "}, format="json")
    assert response.status_code == 202, response.data
    job = Job.objects.get(id=response.data["id"])
    assert job.status == Job.Status.READY, job.error
    assert [idea["title"] for idea in job.result["ideas"]] == ["Orata al cartoccio"]
    prompt, kwargs = prompts[0]
    assert kwargs["fast"] is True and kwargs["feature"] == "meal_ideas"
    assert '"qualcosa col pesce"' in prompt and "150 g pesce + verdure" in prompt
    assert "Zuppa di ceci" in prompt  # gia' nel piano: da non ripetere
    idea = Recipe.objects.get(title="Orata al cartoccio")
    assert (idea.source, idea.in_cookbook, "dinner" in idea.meal_slots) == ("plan", False, True)
    # Scelta: entra nel pasto come qualsiasi altra ricetta.
    api(user).patch(
        f"{PLANS}/{plan_id}/meals/{meal.id}", {"recipe_id": str(idea.id)}, format="json"
    )
    meal.refresh_from_db()
    assert meal.recipe_id == idea.id


def test_idee_per_un_pasto_degli_altri(
    user, other_user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["pick"] = lambda candidates, slot, day, wait: candidates["Zuppa di ceci"]
    plan_id = _create(api, user, django_capture_on_commit_callbacks).data["id"]
    meal = PlannedMeal.objects.filter(plan_id=plan_id).first()
    with override_settings(GEMINI_API_KEY="k"):
        response = api(other_user).post(
            f"{PLANS}/{plan_id}/meals/{meal.id}/ideas", {}, format="json"
        )
    assert response.status_code == 404


def test_sostituzioni_lette(user, api, reading, django_capture_on_commit_callbacks):
    from apps.plans.models import NutritionistPlan
    from apps.plans.nutritionist import NutritionistMeal, NutritionistReading, SubstitutionGroup

    reading["result"] = NutritionistReading(
        meals=[NutritionistMeal(slot="lunch", options=["80 g pasta + verdure"])],
        substitutions=[
            SubstitutionGroup(
                group=" Carboidrati ",
                equivalents=["80 g pasta", "80 g riso", "100 g  pane", "80 g riso"],
                note="a pranzo",
            ),
            # Un alimento solo non sostituisce niente.
            SubstitutionGroup(group="Frutta", equivalents=["1 mela"]),
        ],
    )
    _upload(api, user, django_capture_on_commit_callbacks)
    rules = NutritionistPlan.objects.get().rules
    assert rules["substitutions"] == [
        {
            "group": "Carboidrati",
            "equivalents": ["80 g pasta", "80 g riso", "100 g pane"],
            "note": "a pranzo",
        }
    ]
    # La lettura le chiede a parte, non nelle note.
    assert '"substitutions"' in reading["prompts"][0]
    # Si correggono dalla revisione come il resto.
    plan = NutritionistPlan.objects.get()
    rules["substitutions"][0]["equivalents"].append("300 g patate")
    response = api(user).patch(f"{NUTRITIONIST}/{plan.id}", {"rules": rules}, format="json")
    assert response.data["rules"]["substitutions"][0]["equivalents"][-1] == "300 g patate"


def test_rileggere_dai_file(user, api, reading, django_capture_on_commit_callbacks):
    from apps.plans.models import NutritionistPlan
    from apps.plans.nutritionist import NutritionistMeal, NutritionistReading, SubstitutionGroup

    _upload(api, user, django_capture_on_commit_callbacks)
    plan = NutritionistPlan.objects.get()
    plan.title = "Il mio piano"
    plan.strict = False
    plan.status = NutritionistPlan.Status.CONFIRMED
    plan.save()
    reading["result"] = NutritionistReading(
        title="Altro titolo",
        meals=[NutritionistMeal(slot="lunch", options=["80 g pasta + verdure"])],
        substitutions=[SubstitutionGroup(group="Proteine", equivalents=["150 g pollo", "2 uova"])],
    )
    url = f"{NUTRITIONIST}/{plan.id}/reread"
    with override_settings(GEMINI_API_KEY="k"), django_capture_on_commit_callbacks(execute=True):
        response = api(user).post(url)
    assert response.status_code == 202, response.data
    plan.refresh_from_db()
    # Regole nuove da rivedere; nome e "alla lettera" restano quelli scelti.
    assert plan.status == "draft" and plan.title == "Il mio piano" and plan.strict is False
    assert plan.rules["substitutions"][0]["equivalents"] == ["150 g pollo", "2 uova"]
    assert NutritionistPlan.objects.count() == 1
    # Gli altri no.
    from apps.conftest import UserFactory

    with override_settings(GEMINI_API_KEY="k"):
        assert api(UserFactory()).post(url).status_code == 404
