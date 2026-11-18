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
# Il piano alimentare scelto dal fixture ``diet``: senza, la preparazione non si fa.
DIET: dict = {}
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


DIET_RULES = {
    "meals": [
        {"slot": "breakfast", "options": ["200 ml latte + 30 g fiocchi d'avena"]},
        {"slot": "lunch", "options": ["80 g pasta integrale + 150 g ceci lessati + 200 g verdura"]},
        {"slot": "dinner", "options": ["150 g pesce + 200 g verdura + 50 g pane"]},
    ],
    "substitutions": [
        {"group": "Cereali", "equivalents": ["80 g pasta", "80 g riso", "100 g pane"], "note": ""}
    ],
    "weekly": [{"food": "legumi", "times": 3}],
    "free_foods": ["verdura"],
    "avoid_foods": [],
    "notes": "",
}


@pytest.fixture
def diet(user):
    from apps.plans.models import NutritionistPlan

    plan = NutritionistPlan.objects.create(
        owner=user,
        title="Piano dalle linee guida",
        source=NutritionistPlan.Source.GUIDELINES,
        status=NutritionistPlan.Status.CONFIRMED,
        rules=DIET_RULES,
    )
    DIET["id"] = str(plan.id)
    yield plan
    DIET.clear()


@pytest.fixture
def cookbook(user, diet):
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
    if DIET:
        base["nutritionist_plan"] = DIET["id"]
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


# --- generazione per ingredienti con Gemini finto (ADR 0023) ------------------------------


SLOT_LINE = re.compile(r"- (\d{4}-\d\d-\d\d) \([^)]*\), [^[]+\[(\w+)\], attesa (\d+)")
CANDIDATE = re.compile(r"\[(\d+)\] ([^—\n]+?) —")
LUNCH = [
    {"name": "pasta integrale", "quantity": 80, "unit": "g"},
    {"name": "ceci lessati", "quantity": 150, "unit": "g"},
    {"name": "zucchine", "quantity": 200, "unit": "g"},
]


@pytest.fixture
def gemini(monkeypatch):
    """``state["pick"](candidati, slot, giorno, attesa)``: un numero (ricetta
    suggerita), un titolo (idea), un dict (campi di MealChoice) o None (saltato).
    ``state["repair"](prompt)`` risponde alla correzione delle frequenze."""
    from apps.plans import generation, suggestions
    from apps.plans.generation import MealChoice, WeekChoices

    state = {
        "prompts": [],
        "kwargs": [],
        "new": [],
        "overloaded": 0,
        "pick": None,
        "repair": None,
    }

    def fake_generate(contents, schema, **kwargs):
        prompt = contents[0]
        state["prompts"].append(prompt)
        state["kwargs"].append(kwargs)
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
        if "non tornano" in prompt:
            return (state["repair"](prompt) if state["repair"] else WeekChoices(meals=[])), "finto"
        candidates = {title.strip(): int(n) for n, title in CANDIDATE.findall(prompt)}
        meals = []
        for day, slot, wait in SLOT_LINE.findall(prompt):
            choice = state["pick"](candidates, slot, date.fromisoformat(day), int(wait))
            if choice is None:
                continue
            fields = {"components": LUNCH}
            if isinstance(choice, int):
                fields["recipes"] = [choice]
            elif isinstance(choice, str):
                fields.update(idea=choice, idea_note="leggera")
            else:
                fields.update(choice)
            meals.append(MealChoice(date=day, slot=slot, **fields))
        return WeekChoices(meals=meals), "finto"

    monkeypatch.setattr(generation, "generate", fake_generate)
    monkeypatch.setattr(suggestions, "generate", fake_generate)
    monkeypatch.setattr("apps.plans.tasks.OVERLOAD_PAUSE", 0)
    return state


def _create(api, user, capture, **extra):
    with capture(execute=True):
        return api(user).post(PLANS, _settings(**extra), format="json")


def _week_prompts(gemini):
    return [p for p in gemini["prompts"] if "Pasti da comporre" in p]


def test_settimana_per_ingredienti(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    def pick(candidates, slot, day, wait):
        return {"recipes": [candidates["Zuppa di ceci"]], "idea": "Pasta e ceci", "weekly": []}

    gemini["pick"] = pick
    response = _create(api, user, django_capture_on_commit_callbacks)
    assert response.status_code == 202, response.data
    plan = MealPlan.objects.get()
    assert (plan.status, plan.weeks_done) == (MealPlan.Status.DRAFT, 1)
    meals = list(plan.meals.all())
    assert len(meals) == 14
    # Il pasto e' fatto di alimenti a persona; la ricetta non e' scelta: e' suggerita.
    assert all(meal.components == LUNCH and meal.recipe_id is None for meal in meals)
    assert meals[0].suggestions == [
        {"recipe": str(cookbook["ceci"].id)},
        {"title": "Pasta e ceci", "idea": ""},
    ]
    # Nessuna ricetta scritta durante la generazione: le idee si scrivono quando si aprono.
    assert gemini["new"] == []
    week = _week_prompts(gemini)[0]
    assert "Piano alimentare dalle linee guida" in week
    assert "80 g pasta integrale + 150 g ceci lessati" in week and "legumi 3 volte" in week
    assert "Cereali: 80 g pasta = 80 g riso = 100 g pane" in week
    assert user.email not in week
    # La settimana chiede il massimo di token: con cinque pasti al giorno serve.
    assert gemini["kwargs"][0]["max_output_tokens"] == 32_000
    detail = api(user).get(f"{PLANS}/{plan.id}").data
    first = detail["meals"][0]
    assert first["recipe"] is None
    assert first["portion"][0] == {"name": "pasta integrale", "quantity": "80", "unit": "g"}
    assert first["suggestions"][0]["recipe"]["title"] == "Zuppa di ceci"
    assert first["suggestions"][1] == {"title": "Pasta e ceci", "idea": ""}
    assert detail["nutritionist"]["weekly"] == [{"food": "legumi", "times": 3}]
    assert detail["nutritionist"]["source"] == "guidelines"


def test_serve_un_piano_alimentare(user, api, cookbook):
    from apps.plans.models import NutritionistPlan

    with override_settings(CORNHUB_APP_TOKEN="token-test"):
        missing = api(user).post(PLANS, _settings(nutritionist_plan=None), format="json")
        assert missing.status_code == 400
        NutritionistPlan.objects.update(status=NutritionistPlan.Status.DRAFT)
        draft = api(user).post(PLANS, _settings(), format="json")
        assert draft.status_code == 400


def test_alimenti_vietati_tolti_dai_pasti(
    user, api, cookbook, gemini, diet, django_capture_on_commit_callbacks
):
    profile = Profile.objects.create(user=user)
    FoodPreference.objects.create(profile=profile, kind="allergy", label="gamberi")
    diet.rules = {**DIET_RULES, "avoid_foods": ["salmone"]}
    diet.save()

    def pick(candidates, slot, day, wait):
        if slot == "lunch":
            return {"components": [*LUNCH, {"name": "gamberi", "quantity": 100, "unit": "g"}]}
        if day == MONDAY:
            return {"components": [{"name": "salmone", "quantity": 150, "unit": "g"}]}
        return {"components": [{"name": "merluzzo", "quantity": 150, "unit": "g"}]}

    gemini["pick"] = pick
    _create(api, user, django_capture_on_commit_callbacks)
    plan = MealPlan.objects.get()
    lunch = plan.meals.get(date=MONDAY, slot="lunch")
    assert lunch.components == LUNCH
    assert "gamberi" in lunch.note
    # La cena di lunedi' era solo salmone: niente di mangiabile, la riempie il codice.
    dinner = plan.meals.get(date=MONDAY, slot="dinner")
    assert dinner.components == [{"name": "merluzzo", "quantity": 150, "unit": "g"}]
    assert "Ripreso da un altro giorno" in dinner.note
    names = {item["name"] for meal in plan.meals.all() for item in meal.components}
    assert not names & {"gamberi", "salmone"}
    assert "Allergie e intolleranze (MAI): gamberi" in _week_prompts(gemini)[0]


def test_suggerimenti_che_non_reggono_il_frigo(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["pick"] = lambda c, slot, day, wait: c["Salmone al forno"]
    _create(api, user, django_capture_on_commit_callbacks, prep_mode="every_3")
    plan = MealPlan.objects.get()
    salmon = {"recipe": str(cookbook["salmone"].id)}
    # Il salmone regge un giorno: suggerito solo dove si mangia entro un giorno.
    for meal in plan.meals.all():
        wait = (meal.date - meal.cooked_on).days
        assert (salmon in meal.suggestions) == (wait <= 1)
    assert plan.meals.get(date=MONDAY + timedelta(1), slot="lunch").cooked_on == MONDAY


def test_un_mese_a_settimane(user, api, cookbook, gemini, django_capture_on_commit_callbacks):
    gemini["pick"] = lambda c, slot, day, wait: c["Zuppa di ceci"]
    _create(api, user, django_capture_on_commit_callbacks, days=28)
    plan = MealPlan.objects.get()
    assert (plan.status, plan.weeks_done, plan.meals.count()) == ("draft", 4, 56)
    assert len(_week_prompts(gemini)) == 4


def test_gemini_sovraccarico_riprova(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["overloaded"] = 2
    gemini["pick"] = lambda c, slot, day, wait: c["Frittata"]
    _create(api, user, django_capture_on_commit_callbacks)
    assert MealPlan.objects.get().status == "draft"


def test_pasti_saltati_riempiti_dal_codice(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    breakfast = [{"name": "latte", "quantity": 200, "unit": "ml"}]

    def pick(c, slot, day, wait):
        if day != MONDAY:
            return None
        return {"components": breakfast} if slot == "breakfast" else c["Zuppa di ceci"]

    gemini["pick"] = pick
    _create(api, user, django_capture_on_commit_callbacks, slots=["breakfast", "lunch", "dinner"])
    plan = MealPlan.objects.get()
    meals = list(plan.meals.all())
    # Colazioni con la colazione, pranzi e cene con pranzi e cene.
    assert all(meal.components for meal in meals)
    assert all(m.components == breakfast for m in meals if m.slot == "breakfast")
    assert all(m.components == LUNCH for m in meals if m.slot != "breakfast")
    assert all("Ripreso" in m.note for m in meals if m.date != MONDAY)


def test_piatti_esclusi_nominati_nel_prompt(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["pick"] = lambda c, slot, day, wait: c["Frittata"]
    _create(api, user, django_capture_on_commit_callbacks, exclude_tags=["del cuore"])
    assert "nemmeno come idea: Pasta al pomodoro" in _week_prompts(gemini)[0]


def test_frequenze_corrette_da_una_seconda_chiamata(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    from apps.plans.generation import MealChoice, WeekChoices

    gemini["pick"] = lambda c, slot, day, wait: {"weekly": ["Legumi"]}
    asked = []

    def repair(prompt):
        asked.append(prompt)
        # Toglie i legumi da tutti i pasti tranne tre pranzi.
        return WeekChoices(
            meals=[
                MealChoice(
                    date=(MONDAY + timedelta(n)).isoformat(),
                    slot=slot,
                    components=[{"name": "riso", "quantity": 80, "unit": "g"}],
                    weekly=[],
                )
                for n in range(7)
                for slot in ("lunch", "dinner")
                if not (slot == "lunch" and n < 3)
            ]
        )

    gemini["repair"] = repair
    _create(api, user, django_capture_on_commit_callbacks)
    assert "- legumi: 14 volte, il piano dice 3" in asked[0]
    plan = MealPlan.objects.get()
    with_legumes = [meal for meal in plan.meals.all() if meal.diet_foods == ["legumi"]]
    assert len(with_legumes) == 3
    assert not [meal for meal in plan.meals.all() if "Oltre" in meal.note]


def test_frequenze_oltre_restano_come_nota(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["pick"] = lambda c, slot, day, wait: {"weekly": ["legumi"]}
    _create(api, user, django_capture_on_commit_callbacks)
    plan = MealPlan.objects.get()
    noted = [meal for meal in plan.meals.order_by("date", "slot") if "Oltre" in meal.note]
    # I primi tre pasti coi legumi vanno bene, gli altri undici no.
    assert len(noted) == 11
    assert "legumi 3 volte a settimana" in noted[0].note


def test_niente_yogurt_a_pranzo_e_cena(
    user, api, cookbook, diet, gemini, django_capture_on_commit_callbacks
):
    # Il piano ha lo yogurt a merenda e 3 volte a settimana, ma si preparano
    # solo pranzi e cene: non deve finirci per far tornare le frequenze.
    diet.rules = {
        **DIET_RULES,
        "meals": [
            *DIET_RULES["meals"],
            {"slot": "afternoon_snack", "options": ["125 g yogurt + 150 g frutta"]},
        ],
        "weekly": [{"food": "yogurt", "times": 3}],
    }
    diet.save(update_fields=["rules"])
    yogurt = [*LUNCH, {"name": "yogurt greco", "quantity": 125, "unit": "g"}]
    gemini["pick"] = lambda c, slot, day, wait: {"components": yogurt, "weekly": ["yogurt"]}
    _create(api, user, django_capture_on_commit_callbacks)
    week = _week_prompts(gemini)[0]
    assert "yogurt 3 volte" not in week and "125 g yogurt" not in week
    assert "MAI gli alimenti di colazione, spuntini e merende (yogurt" in week
    # Lo yogurt non e' fra i conti da correggere: non conta su pranzi e cene.
    assert not [p for p in gemini["prompts"] if "non tornano" in p and "- yogurt" in p]
    plan = MealPlan.objects.get()
    assert all(meal.components == LUNCH for meal in plan.meals.all())
    response = api(user).get(f"{PLANS}/{plan.id}")
    assert response.data["nutritionist"]["weekly"] == []


def test_niente_merluzzo_tutta_la_settimana(
    user, api, cookbook, diet, gemini, django_capture_on_commit_callbacks
):
    from apps.plans.generation import WeekChoices

    # Il piano dice "pesce bianco: merluzzo, sogliola, ..." e l'LLM sceglieva
    # sempre merluzzo (2026-11-18): al massimo 2 piatti, poi gli altri pesci.
    diet.rules = {
        **DIET_RULES,
        "meals": [
            DIET_RULES["meals"][1],
            {
                "slot": "dinner",
                "options": [
                    "300 g Pesce bianco: merluzzo, sogliola, platessa, orata + 60 g pane"
                ],
            },
        ],
    }
    diet.save(update_fields=["rules"])
    cod = [
        {"name": "merluzzo", "quantity": 300, "unit": "g"},
        {"name": "pane", "quantity": 60, "unit": "g"},
    ]

    def pick(c, slot, day, wait):
        if slot == "dinner":
            return {"components": cod, "idea": "Merluzzo al forno"}
        return {"components": [LUNCH[0], LUNCH[2]]}

    asked = []
    gemini["pick"] = pick
    gemini["repair"] = lambda prompt: asked.append(prompt) or WeekChoices(meals=[])
    _create(api, user, django_capture_on_commit_callbacks)
    # Prima la correzione dell'LLM...
    assert "- merluzzo: in 7 piatti, al massimo 2 a settimana" in asked[0]
    # ...poi, se non basta, il codice: stessa grammatura, altri pesci della voce.
    plan = MealPlan.objects.get()
    dinners = list(plan.meals.filter(slot="dinner").order_by("date"))
    fish = [meal.components[0]["name"] for meal in dinners]
    assert fish[:2] == ["merluzzo", "merluzzo"]
    assert max(fish.count(name) for name in set(fish)) == 2
    assert set(fish) == {"merluzzo", "sogliola", "platessa", "orata"}
    assert all(meal.components[0]["quantity"] == 300 for meal in dinners)
    sole = next(meal for meal in dinners if meal.components[0]["name"] == "sogliola")
    assert sole.suggestions == [{"title": "Sogliola al forno", "idea": ""}]


def test_la_sera_cucino_anche_il_pranzo_dopo(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    dinner = [{"name": "riso", "quantity": 80, "unit": "g"}]

    def pick(c, slot, day, wait):
        if slot == "dinner":
            return {"components": dinner, "recipes": [c["Zuppa di ceci"]], "weekly": ["legumi"]}
        return {}

    gemini["pick"] = pick
    _create(api, user, django_capture_on_commit_callbacks, prep_mode="evening_before")
    week = _week_prompts(gemini)[0]
    # Solo il primo pranzo si compone; le cene sanno che fanno anche il pranzo.
    assert len(re.findall(r"\[lunch\]", week)) == 1
    assert "fa anche il pranzo di domani" in week and "contano DUE volte" in week
    plan = MealPlan.objects.get()
    tuesday = plan.meals.get(date=MONDAY + timedelta(1), slot="lunch")
    assert tuesday.components == dinner and tuesday.cooked_on == MONDAY
    assert tuesday.note.startswith("Avanzo della cena di ieri")
    assert tuesday.suggestions == [{"recipe": str(cookbook["ceci"].id)}]
    # Le frequenze si contano sui pasti: 6 cene-avanzo valgono 12, piu' l'ultima cena.
    assert sum(1 for meal in plan.meals.all() if meal.diet_foods == ["legumi"]) == 13
    # Approvare la ricetta della cena la approva anche per il pranzo di domani.
    monday_dinner = plan.meals.get(date=MONDAY, slot="dinner")
    url = f"{PLANS}/{plan.id}/meals/{monday_dinner.id}"
    response = api(user).patch(url, {"recipe_id": str(cookbook["ceci"].id)}, format="json")
    assert response.status_code == 200, response.data
    tuesday.refresh_from_db()
    assert tuesday.recipe_id == cookbook["ceci"].id and tuesday.components == dinner
    assert plan.meals.get(date=MONDAY + timedelta(1), slot="dinner").recipe_id is None


def test_cambio_un_alimento_del_pasto(
    user, api, cookbook, diet, gemini, django_capture_on_commit_callbacks
):
    diet.rules = {**DIET_RULES, "avoid_foods": ["salmone"]}
    diet.save(update_fields=["rules"])
    gemini["pick"] = lambda c, slot, day, wait: {
        "components": LUNCH,
        "weekly": ["legumi"],
        "recipes": [c["Zuppa di ceci"]],
    }
    _create(api, user, django_capture_on_commit_callbacks, prep_mode="evening_before")
    plan = MealPlan.objects.get()
    monday = plan.meals.get(date=MONDAY, slot="dinner")
    url = f"{PLANS}/{plan.id}/meals/{monday.id}"

    # Solo le grammature: i suggerimenti restano.
    more = [{**LUNCH[0], "quantity": 90}, *LUNCH[1:]]
    response = api(user).patch(url, {"components": more}, format="json")
    assert response.data["components"] == more and len(response.data["suggestions"]) == 1
    response = api(user).patch(url, {"components": LUNCH}, format="json")
    api(user).patch(url, {"recipe_id": str(cookbook["ceci"].id)}, format="json")

    # Gli equivalenti dalle sostituzioni, con la grammatura gia' fatta.
    swaps = api(user).get(f"{url}/swaps").data["swaps"]
    assert len(swaps) == 3 and swaps[1] == swaps[2] == []
    assert swaps[0] == [
        {"name": "riso", "quantity": 80, "unit": "g", "group": "Cereali"},
        {"name": "pane", "quantity": 100, "unit": "g", "group": "Cereali"},
    ]

    chicken = [LUNCH[0], {"name": "pollo", "quantity": 100, "unit": "g"}, LUNCH[2]]
    response = api(user).patch(url, {"components": chicken}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["components"] == chicken and response.data["diet_foods"] == []
    # La zuppa di ceci era per i ceci: col pollo non si suggerisce ne' resta scelta.
    assert response.data["suggestions"] == [] and response.data["recipe"] is None
    # Vale anche per il pranzo-avanzo di martedi', non per la cena di martedi'.
    tuesday = plan.meals.get(date=MONDAY + timedelta(1), slot="lunch")
    assert tuesday.components == chicken and tuesday.diet_foods == []
    assert tuesday.recipe_id is None
    assert plan.meals.get(date=MONDAY + timedelta(1), slot="dinner").components == LUNCH

    lentils = [*chicken[:1], {"name": "lenticchie lessate", "quantity": 150, "unit": "g"}]
    response = api(user).patch(url, {"components": lentils}, format="json")
    assert response.data["diet_foods"] == ["legumi"]

    # A volonta': quantita' vuota, unita' vuota.
    free = [{"name": "insalata", "quantity": None, "unit": "g"}]
    response = api(user).patch(url, {"components": free}, format="json")
    assert response.data["components"] == [{"name": "insalata", "quantity": None, "unit": ""}]

    salmon = [{"name": "salmone", "quantity": 150, "unit": "g"}]
    response = api(user).patch(url, {"components": salmon}, format="json")
    assert response.status_code == 400
    assert "Non puoi mangiarlo: salmone" in str(response.data)
    response = api(user).patch(url, {"components": []}, format="json")
    assert response.status_code == 400


def test_pranzi_avanzo_solo_la_sera_prima(user, cookbook):
    from apps.plans.generation import leftover_lunches

    assert len(leftover_lunches(_plan(user, prep_mode="evening_before"))) == 6
    assert leftover_lunches(_plan(user, prep_mode="none")) == {}


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
    with override_settings(CORNHUB_APP_TOKEN="token-test"):
        assert api(user).post(PLANS, _settings(**extra), format="json").status_code == 400


@override_settings(CORNHUB_APP_TOKEN="")
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


def test_approvare_una_ricetta_suggerita(
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
    # Gli alimenti restano quelli del piano: la ricetta dice solo come cucinarli.
    assert response.data["components"] == LUNCH
    assert response.data["suggestions"][0]["recipe"]["title"] == "Frittata"
    assert api(user).patch(url, {"recipe_id": None}, format="json").data["recipe"] is None
    late = (meal.date + timedelta(1)).isoformat()
    assert api(user).patch(url, {"cooked_on": late}, format="json").status_code == 400
    foreign = _recipe(other_user, "Non mia")
    assert api(user).patch(url, {"recipe_id": str(foreign.id)}, format="json").status_code == 404
    assert api(other_user).patch(url, {"servings": 1}, format="json").status_code == 404


def test_scrivere_un_idea_suggerita(
    user, other_user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    from apps.jobs.models import Job

    gemini["pick"] = lambda c, slot, day, wait: "Pasta e ceci"
    plan_id = _create(api, user, django_capture_on_commit_callbacks, prep_mode="every_2").data[
        "id"
    ]
    meal = PlannedMeal.objects.get(plan_id=plan_id, date=MONDAY, slot="lunch")
    url = f"{PLANS}/{plan_id}/meals/{meal.id}/suggestions"
    with django_capture_on_commit_callbacks(execute=True):
        response = api(user).post(f"{url}/0/write")
    assert response.status_code == 202, response.data
    job = Job.objects.get(id=response.data["id"])
    assert job.status == Job.Status.READY, job.error
    recipe = Recipe.objects.get(title="Pasta e ceci")
    assert job.result["recipe"]["id"] == str(recipe.id)
    assert (recipe.source, recipe.in_cookbook, recipe.servings) == ("plan", False, 2)
    prompt = gemini["prompts"][-1]
    assert "pasta integrale 80 g, ceci lessati 150 g, zucchine 200 g" in prompt
    assert "Idea: leggera" in prompt
    assert gemini["kwargs"][-1]["feature"] == "meal_recipe"
    assert gemini["kwargs"][-1]["fast"] is True
    # L'idea diventa la ricetta in tutti i pasti dello stesso piatto (cucinati lunedi').
    for same in PlannedMeal.objects.filter(plan_id=plan_id, cooked_on=MONDAY):
        assert same.suggestions == [{"recipe": str(recipe.id)}]
    assert PlannedMeal.objects.get(
        plan_id=plan_id, date=MONDAY + timedelta(2), slot="lunch"
    ).suggestions == [{"title": "Pasta e ceci", "idea": "leggera"}]
    # Non e' approvata: il pasto non ha ancora una ricetta.
    meal.refresh_from_db()
    assert meal.recipe_id is None
    with override_settings(CORNHUB_APP_TOKEN="token-test"):
        assert api(user).post(f"{url}/5/write").status_code == 404
        assert api(other_user).post(f"{url}/0/write").status_code == 404


def test_rifare_e_eliminare(user, api, cookbook, gemini, django_capture_on_commit_callbacks):
    gemini["pick"] = lambda c, slot, day, wait: "Zucchine ripiene"
    plan_id = _create(api, user, django_capture_on_commit_callbacks).data["id"]
    meal = PlannedMeal.objects.filter(plan_id=plan_id).first()
    with django_capture_on_commit_callbacks(execute=True):
        api(user).post(f"{PLANS}/{plan_id}/meals/{meal.id}/suggestions/0/write")
    assert Recipe.objects.filter(title="Zucchine ripiene").exists()
    gemini["pick"] = lambda c, slot, day, wait: c["Frittata"]
    with django_capture_on_commit_callbacks(execute=True):
        assert api(user).post(f"{PLANS}/{plan_id}/regenerate").status_code == 202
    plan = MealPlan.objects.get()
    frittata = {"recipe": str(cookbook["frittata"].id)}
    assert all(meal.suggestions == [frittata] for meal in plan.meals.all())
    with django_capture_on_commit_callbacks(execute=True):
        api(user).post(f"{PLANS}/{plan_id}/meals/{plan.meals.first().id}/suggestions/0/write")
    assert api(user).delete(f"{PLANS}/{plan_id}").status_code == 204
    assert not MealPlan.all_objects.exists()
    # Il ricettario resta.
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
        state["prompts"].append(contents[-1])
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
    with capture(execute=True):
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
        status=NutritionistPlan.Status.CONFIRMED,
        rules={
            "meals": [{"slot": "lunch", "options": ["80 g pasta + verdure"]}],
            "weekly": [{"food": "legumi", "times": 3}],
            "avoid_foods": ["salmone", "uova"],
        },
    )

    def pick(candidates, slot, day, wait):
        assert "Salmone al forno" not in candidates and "Frittata" not in candidates
        return candidates["Zuppa di ceci"]

    gemini["pick"] = pick
    response = _create(
        api, user, django_capture_on_commit_callbacks, nutritionist_plan=str(nutritionist.id)
    )
    assert response.status_code == 202, response.data
    assert response.data["nutritionist"]["title"] == "Piano della dottoressa"
    assert response.data["nutritionist"]["source"] == "nutritionist"
    week = _week_prompts(gemini)[0]
    assert "Piano del nutrizionista" in week and "80 g pasta + verdure" in week
    assert "ALLA LETTERA" in week and "Da evitare: salmone, uova" in week


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


def test_idee_per_un_pasto(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks, monkeypatch
):
    from apps.jobs.models import Job
    from apps.plans.models import NutritionistPlan
    from apps.recipes.importing import ImportedRecipes

    gemini["pick"] = lambda candidates, slot, day, wait: candidates["Zuppa di ceci"]
    NutritionistPlan.objects.filter(id=DIET["id"]).update(
        rules={**DIET_RULES, "avoid_foods": ["uova"]}
    )
    plan_id = _create(api, user, django_capture_on_commit_callbacks).data["id"]
    meal = PlannedMeal.objects.filter(plan_id=plan_id, slot="dinner").first()
    prompts = []

    def fake(contents, schema, **kwargs):
        prompts.append((contents[0], kwargs))
        return ImportedRecipes(
            recipes=[
                ImportedRecipe(
                    title="Pasta e ceci al rosmarino",
                    servings=2,
                    ingredients=[ImportedIngredient(name="ceci", quantity="300", unit="g")],
                    steps=["Cuoci."],
                ),
                ImportedRecipe(
                    title="Frittata di zucchine",  # uova: il piano dice di evitarle
                    servings=2,
                    ingredients=[ImportedIngredient(name="uova", quantity="4", unit="pz")],
                    steps=["Sbatti."],
                ),
            ]
        ), "finto"

    monkeypatch.setattr("apps.plans.swap.generate", fake)
    url = f"{PLANS}/{plan_id}/meals/{meal.id}/ideas"
    with django_capture_on_commit_callbacks(execute=True):
        response = api(user).post(url, {"hint": "  qualcosa  di caldo "}, format="json")
    assert response.status_code == 202, response.data
    job = Job.objects.get(id=response.data["id"])
    assert job.status == Job.Status.READY, job.error
    assert [idea["title"] for idea in job.result["ideas"]] == ["Pasta e ceci al rosmarino"]
    prompt, kwargs = prompts[0]
    assert kwargs["fast"] is True and kwargs["feature"] == "meal_ideas"
    # Le idee cucinano gli alimenti del pasto.
    assert '"qualcosa di caldo"' in prompt and "pasta integrale 80 g" in prompt


def test_idee_per_un_pasto_degli_altri(
    user, other_user, api, cookbook, gemini, django_capture_on_commit_callbacks
):
    gemini["pick"] = lambda candidates, slot, day, wait: candidates["Zuppa di ceci"]
    plan_id = _create(api, user, django_capture_on_commit_callbacks).data["id"]
    meal = PlannedMeal.objects.filter(plan_id=plan_id).first()
    with override_settings(CORNHUB_APP_TOKEN="token-test"):
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
    with django_capture_on_commit_callbacks(execute=True):
        response = api(user).post(url)
    assert response.status_code == 202, response.data
    plan.refresh_from_db()
    # Regole nuove da rivedere; nome e "alla lettera" restano quelli scelti.
    assert plan.status == "draft" and plan.title == "Il mio piano" and plan.strict is False
    assert plan.rules["substitutions"][0]["equivalents"] == ["150 g pollo", "2 uova"]
    assert NutritionistPlan.objects.count() == 1
    # Gli altri no.
    from apps.conftest import UserFactory

    with override_settings(CORNHUB_APP_TOKEN="token-test"):
        assert api(UserFactory()).post(url).status_code == 404


# --- piano dalle linee guida (ADR 0023) ---------------------------------------------------


def test_piano_dalle_linee_guida(
    user, other_user, api, monkeypatch, django_capture_on_commit_callbacks
):
    from apps.jobs.models import Job
    from apps.plans.models import NutritionistPlan
    from apps.plans.nutritionist import NutritionistMeal, NutritionistReading, WeeklyFrequency

    profile = Profile.objects.create(user=user, meal_slots=["lunch", "dinner"], sex="f")
    FoodPreference.objects.create(profile=profile, kind="allergy", label="gamberi")
    calls = []

    def fake(contents, schema, **kwargs):
        calls.append((contents[0], kwargs))
        return NutritionistReading(
            title="Piano dalle linee guida",
            meals=[
                NutritionistMeal(slot="breakfast", options=["200 ml latte"]),
                NutritionistMeal(slot="lunch", options=["80 g pasta + 150 g legumi + verdura"]),
                NutritionistMeal(slot="dinner", options=["150 g pesce + verdura + 50 g pane"]),
            ],
            weekly=[WeeklyFrequency(food="legumi", times=4)],
            notes="Indicativo: per esigenze di salute decide il medico.",
        ), "finto"

    monkeypatch.setattr("apps.plans.guidelines.generate", fake)
    with override_settings(CORNHUB_APP_TOKEN="token-test"):
        with django_capture_on_commit_callbacks(execute=True):
            response = api(user).post(f"{NUTRITIONIST}/guidelines")
    assert response.status_code == 202, response.data
    job = Job.objects.get(id=response.data["id"])
    assert job.status == Job.Status.READY, job.error
    plan = NutritionistPlan.objects.get(owner=user)
    assert job.result == {"nutritionist_plan": str(plan.id), "problem": ""}
    assert (plan.source, plan.status) == ("guidelines", "draft")
    # Solo i pasti della sua giornata.
    assert [meal["slot"] for meal in plan.rules["meals"]] == ["lunch", "dinner"]
    assert plan.rules["weekly"] == [{"food": "legumi", "times": 4}]
    prompt, kwargs = calls[0]
    assert kwargs["feature"] == "diet_guidelines"
    assert "CREA" in prompt and "pranzo [lunch], cena [dinner]" in prompt
    assert "Allergie e intolleranze (MAI): gamberi" in prompt
    assert user.email not in prompt
    detail = api(user).get(f"{NUTRITIONIST}/{plan.id}").data
    assert detail["source"] == "guidelines" and detail["files"] == []
    assert api(other_user).get(f"{NUTRITIONIST}/{plan.id}").status_code == 404


@pytest.mark.parametrize("fails", [False, True])
def test_piano_cancellato_durante_la_generazione(
    user, api, cookbook, gemini, django_capture_on_commit_callbacks, caplog, monkeypatch, fails
):
    """Il piano cancellato (o rifatto da capo) mentre una settimana si genera:
    il task si ferma in silenzio, senza errori su GlitchTip, sia che la
    generazione finisca sia che fallisca sulla chiave esterna."""
    from django.db import IntegrityError

    from apps.plans import tasks

    def generate_week(plan, week):
        MealPlan.all_objects.filter(pk=plan.pk).hard_delete()
        if fails:
            raise IntegrityError("plans_plannedmeal violates foreign key constraint")

    monkeypatch.setattr(tasks, "generate_week", generate_week)
    with caplog.at_level("INFO", logger="apps.plans.tasks"):
        response = _create(api, user, django_capture_on_commit_callbacks)
    assert response.status_code == 202
    assert not MealPlan.all_objects.exists()
    assert "cancellato durante la generazione" in caplog.text
    assert not [r for r in caplog.records if r.levelname == "ERROR"]
