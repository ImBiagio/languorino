"""Generazione di una settimana della preparazione (ADR 0007, ADR 0023).

Il piano alimentare (del nutrizionista o dalle linee guida) dice cosa
mangiare; la preparazione lo mette nei giorni, PER INGREDIENTI, e solo dopo
suggerisce le ricette. Prima ogni pasto era una ricetta e le dosi del piano
ci stavano sopra come testo: si rispettava il piano per ricette, non per
alimenti. Il codice fa quello che deve essere sicuro, l'LLM quello che deve
essere vario:

1. **Candidati (codice)**: le ricette delle fonti scelte (ricettario e
   ricettari PDF), senza quelle che toccano un'allergia, un'intolleranza o un
   alimento da evitare, e senza i tag esclusi. Servono solo da suggerimenti.
2. **Settimana (LLM)**: per ogni pasto gli alimenti a persona con le
   grammature del piano, gli alimenti delle frequenze che contiene, fino a
   due ricette candidate che li cucinano o il nome di un piatto (un'idea, che
   si scrive per intero solo quando l'utente la apre: ``suggestions.py``).
3. **Controlli (codice)**: alimenti delle allergie e da evitare tolti dai
   pasti; pranzi-avanzo copiati dalla cena; frequenze contate sui pasti e,
   se non tornano, una seconda chiamata che cambia solo i pasti che servono;
   quelle ancora oltre restano come nota sul pasto.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Literal

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from pydantic import BaseModel, Field

from apps.ai.client import MAX_OUTPUT_TOKENS, generate
from apps.profiles.allergens import detect_allergen
from apps.profiles.models import FoodPreference, MealSlot, Profile
from apps.recipes.matching import normalize, variants
from apps.recipes.models import Recipe, RecipeIngredient
from apps.recipes.services import PreferenceIndex, match_ingredient, recipe_allergens

from .foods import is_side_food, prepared_weekly, side_only_foods, side_rule
from .models import MealPlan, NutritionistPlan, PlannedMeal
from .schedule import plan_dates, schedule

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 150
MAX_COMPONENTS = 12
MAX_SUGGESTIONS = 2
MAIN_SLOTS = {MealSlot.LUNCH, MealSlot.DINNER}
# Senza "giorni in frigo" una ricetta si da' buona per due giorni.
DEFAULT_KEEPS_DAYS = 2
WEEKDAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
SLOT_NAMES = {
    MealSlot.BREAKFAST: "colazione",
    MealSlot.MORNING_SNACK: "spuntino di metà mattina",
    MealSlot.LUNCH: "pranzo",
    MealSlot.AFTERNOON_SNACK: "merenda",
    MealSlot.DINNER: "cena",
}
GOAL_NAMES = {
    "lose_weight": "perdere peso",
    "gain_muscle": "aumentare la massa muscolare",
    "maintain": "mantenere il peso",
    "more_protein": "mangiare più proteine",
    "eat_better": "mangiare più sano",
    "more_variety": "mangiare più vario",
    "save_time": "perdere meno tempo in cucina",
    "save_money": "spendere meno",
}


# --- 1. candidati -----------------------------------------------------------------


def nutritionist_of(plan: MealPlan) -> NutritionistPlan | None:
    """Il piano del nutrizionista scelto per questo piano, se confermato."""
    if not (chosen := plan.settings.get("nutritionist_plan")):
        return None
    return NutritionistPlan.objects.filter(
        owner=plan.owner, id=chosen, status=NutritionistPlan.Status.CONFIRMED
    ).first()


def candidate_recipes(plan: MealPlan) -> list[Recipe]:
    """Le ricette che il piano puo' usare, gia' ripulite dai vincoli di sicurezza."""
    options = plan.settings
    sources = options.get("sources", {})
    recipes = Recipe.objects.filter(owner=plan.owner)
    allowed = Q(pk__in=[])
    if sources.get("cookbook", True):
        allowed |= Q(in_cookbook=True)
    if books := sources.get("books"):
        allowed |= Q(book_id__in=books)
    recipes = (
        recipes.filter(allowed)
        .prefetch_related(
            "tags",
            Prefetch(
                "ingredients",
                queryset=RecipeIngredient.objects.select_related("ingredient").order_by("position"),
            ),
        )
        .distinct()
    )
    exclude = {tag.lower() for tag in options.get("exclude_tags", [])}
    include = {tag.lower() for tag in options.get("include_tags", [])}
    index = PreferenceIndex(plan.owner)
    from .nutritionist import avoided

    nutritionist = nutritionist_of(plan)
    avoid = nutritionist.rules.get("avoid_foods", []) if nutritionist else []
    out = []
    for recipe in recipes:
        tags = {tag.name.lower() for tag in recipe.tags.all()}
        if tags & exclude or (include and not tags & include):
            continue
        if avoid and avoided(recipe, avoid):
            continue  # il nutrizionista dice di evitarlo
        warnings = index.warnings(recipe, recipe_allergens(recipe))
        if any(warning["kind"] != FoodPreference.Kind.DISLIKE for warning in warnings):
            continue  # allergia o intolleranza: mai nel piano
        recipe.dislikes = [w["label"] for w in warnings]
        out.append(recipe)
    return out[:MAX_CANDIDATES]


def excluded_titles(plan: MealPlan) -> list[str]:
    """I piatti esclusi per tag: l'LLM non deve riproporli nemmeno come ricetta nuova
    (succedeva col piatto "del cuore", che il profilo dice piacere)."""
    exclude = list(plan.settings.get("exclude_tags", []))
    if not exclude:
        return []
    query = Q()
    for tag in exclude:
        query |= Q(tags__name__iexact=tag)
    return list(
        Recipe.objects.filter(owner=plan.owner)
        .filter(query)
        .values_list("title", flat=True)
        .distinct()[:40]
    )


def describe_candidate(number: int, recipe: Recipe) -> str:
    main = [line.ingredient.name for line in recipe.ingredients.all() if not line.ingredient.staple]
    parts = [f"[{number}] {recipe.title}"]
    if recipe.meal_slots:
        parts.append("pasti: " + ", ".join(SLOT_NAMES[slot] for slot in recipe.meal_slots))
    if recipe.total_minutes:
        parts.append(f"{recipe.total_minutes} min")
    parts.append({"easy": "facile", "medium": "media", "hard": "difficile"}[recipe.difficulty])
    if recipe.keeps_days is not None:
        parts.append(f"in frigo {recipe.keeps_days} gg")
    if recipe.freezable:
        parts.append("congelabile")
    if main:
        parts.append("ingredienti: " + ", ".join(main[:6]))
    if tags := [tag.name for tag in recipe.tags.all()]:
        parts.append("tag: " + ", ".join(tags[:4]))
    if dislikes := getattr(recipe, "dislikes", []):
        parts.append("CONTIENE COSE CHE NON PIACCIONO: " + ", ".join(dislikes))
    return " — ".join(parts)


# --- profilo ridotto (progettazione, principio 4) ---------------------------------------


def profile_summary(plan: MealPlan) -> tuple[str, list[str]]:
    return user_profile_summary(plan.owner)


def user_profile_summary(user) -> tuple[str, list[str]]:
    """Quello che serve all'LLM, senza nome, email o data di nascita.

    Restituisce anche le etichette da non usare mai (allergie, intolleranze),
    che vanno nel prompt delle ricette nuove.
    """
    profile = Profile.objects.filter(user=user).first()
    if profile is None:
        return "Nessun profilo compilato.", []
    lines = []
    facts = []
    if profile.age:
        facts.append(f"{profile.age} anni")
    if profile.sex in ("f", "m"):
        facts.append("donna" if profile.sex == "f" else "uomo")
    if profile.height_cm and profile.weight_kg:
        facts.append(f"{profile.height_cm} cm, {profile.weight_kg} kg")
    if profile.activity_level:
        facts.append(f"attività {profile.get_activity_level_display().lower()}")
    if profile.sport_sessions_per_week:
        facts.append(f"sport {profile.sport_sessions_per_week} volte a settimana")
    if facts:
        lines.append("Persona: " + ", ".join(facts) + ".")
    if profile.goals:
        lines.append(
            "Obiettivi: " + ", ".join(GOAL_NAMES.get(goal, goal) for goal in profile.goals) + "."
        )
    if profile.goals_note:
        lines.append(f"In parole sue: {profile.goals_note}")
    if profile.conditions:
        lines.append("Patologie di cui tenere conto: " + ", ".join(profile.conditions) + ".")
    preferences = list(profile.preferences.all())
    forbidden = [p.label for p in preferences if p.is_restriction]
    likes = [p.label for p in preferences if p.kind == FoodPreference.Kind.LIKE]
    dislikes = [p.label for p in preferences if p.kind == FoodPreference.Kind.DISLIKE]
    if forbidden:
        lines.append("Allergie e intolleranze (MAI): " + ", ".join(forbidden) + ".")
    if likes:
        lines.append("Le piace: " + ", ".join(likes) + ".")
    if dislikes:
        lines.append("Non le piace (evitare quando si può): " + ", ".join(dislikes) + ".")
    return "\n".join(lines), forbidden




# --- 2. settimana per ingredienti ---------------------------------------------------------


class Component(BaseModel):
    name: str = Field(
        description="L'alimento come si compra, nome breve (es. 'pasta integrale', "
        "'ceci lessati', 'zucchine', 'olio extravergine')"
    )
    quantity: float | None = Field(
        default=None, description="Quantita' a persona; vuota solo se a volonta'"
    )
    unit: Literal["g", "ml", "pz", ""] = Field(
        default="g", description="g, ml o pz (uova, frutti interi); vuota se a volonta'"
    )


class MealChoice(BaseModel):
    date: str = Field(description="AAAA-MM-GG, uno dei giorni richiesti")
    slot: Literal["breakfast", "morning_snack", "lunch", "afternoon_snack", "dinner"]
    components: list[Component] = Field(
        default_factory=list,
        description="Gli alimenti del pasto a persona con le grammature del piano, "
        "verdura e condimento compresi",
    )
    weekly: list[str] = Field(
        default_factory=list,
        description="Gli alimenti delle frequenze settimanali che il pasto contiene, coi "
        "nomi esatti della lista",
    )
    recipes: list[int] = Field(
        default_factory=list,
        description="Fino a 2 numeri di ricette candidate che si preparano con questi "
        "ingredienti",
    )
    idea: str = Field(
        default="",
        description="Se le candidate adatte sono meno di 2: il nome di un piatto semplice "
        "con questi ingredienti (es. 'Pasta e fagioli')",
    )
    idea_note: str = Field(default="", description="Per l'idea: una frase su come si fa")


class WeekChoices(BaseModel):
    meals: list[MealChoice]


WEEK_PROMPT = """Sei un nutrizionista che organizza la settimana di una persona che segue
un piano alimentare. Il piano dice COSA mangiare: tu componi ogni pasto PER
INGREDIENTI, con le grammature a persona del piano, e solo dopo suggerisci le
ricette per cucinarli. Rispondi solo col JSON richiesto.

{profile}

{rules}{goal}
Porzioni per pasto: {servings} (le grammature sono a persona: le moltiplica il codice).

Pasti da comporre (giorno, pasto, giorni di attesa in frigo fra cottura e pasto):
{slots}

Ricette candidate da suggerire (numero tra parentesi quadre):
{candidates}

Regole:
- Ogni pasto e' un'opzione del piano (o una sua variante con le sostituzioni): in
  "components" gli alimenti con quantita' e unita' a persona, verdura e olio
  compresi. Un alimento per elemento, col nome breve della lista della spesa;
  per legumi e cereali scrivi se il peso e' da secco o da lessato ("ceci secchi
  50 g", "ceci lessati 150 g"): cambia la spesa.
- Rispetta le frequenze a settimana, contate sui pasti; alterna le opzioni e non
  ripetere lo stesso pasto due giorni di fila.
- Meal prep: pasti con lo stesso giorno di cottura possono essere lo stesso piatto
  cucinato una volta sola, e allora hanno gli stessi "components". Con attesa N
  scegli alimenti che reggono N giorni in frigo (pesce meglio ad attesa 0 o 1).
{leftovers}- In "recipes" fino a 2 ricette candidate che si preparano con gli ingredienti
  del pasto (possono mancare aromi o condimenti; le quantita' le decide il piano,
  non la ricetta). Se ne trovi meno di 2, in "idea" il nome di un piatto semplice e
  casalingo fatto con quegli ingredienti e in "idea_note" una frase su come si fa.
  Tempo per cucinare: circa {minutes} minuti; difficolta' al massimo {difficulty}.
- In "weekly" gli alimenti delle frequenze che il pasto contiene, coi nomi esatti
  della lista delle frequenze.
- Mai alimenti delle allergie e intolleranze; quelli che non piacciono solo se non
  ci sono alternative.{avoid}
Un elemento in "meals" per OGNI pasto della lista, con la stessa data e lo stesso pasto."""

LEFTOVERS_RULE = """- La sera si cucina la cena in doppia porzione: meta' e' il pranzo del giorno
  dopo, che quindi non e' nella lista. Le cene segnate "fa anche il pranzo di
  domani" sono un piatto unico per tutti e due i pasti: ogni porzione unisce, a
  occhio, meta' di un'opzione del pranzo e meta' di una della cena (per esempio
  cereali e legumi del pranzo con la verdura della cena), e nelle frequenze
  contano DUE volte. Devono restare buone il giorno dopo.
"""

NO_RULES = """Nessun piano alimentare scelto: segui le porzioni standard delle linee guida
CREA (a persona: 80 g pasta o riso, 50 g pane, 150 g legumi lessati, 150 g pesce,
100 g carne, 1 uovo, 200 g verdura, 150 g frutta, 10 ml olio) e le frequenze a
settimana: legumi 3-4, pesce 2-3, carne bianca 2-3, carne rossa 1, uova 2-4,
formaggi 2-3."""

REPAIR_PROMPT = """Hai composto questa settimana per ingredienti (a persona):
{week}

Le frequenze a settimana del piano, contate sui pasti, non tornano:
{problems}

Cambia SOLO i pasti che servono perche' tornino, senza toccare quelli segnati
"avanzo" (si cambia la cena da cui vengono, che conta due volte). Rispondi col
JSON con solo i pasti cambiati, nello stesso formato di prima (components,
weekly, recipes, idea, idea_note), con la loro data e il loro pasto.

{rules}

Ricette candidate da suggerire:
{candidates}

Mai alimenti delle allergie e intolleranze: {forbidden}."""


def _slot_lines(rows: list[dict]) -> str:
    return "\n".join(
        f"- {row['date'].isoformat()} ({WEEKDAYS[row['date'].weekday()]}), "
        f"{SLOT_NAMES[row['slot']]} [{row['slot']}], attesa {row['wait']} giorni"
        + (", fa anche il pranzo di domani" if row.get("feeds_lunch") else "")
        for row in rows
    )


DIFFICULTY_NAMES = {"easy": "facile", "medium": "media", "hard": "difficile"}


# --- 3. controlli del codice ------------------------------------------------------------


def clean_components(raw: list[Component]) -> list[dict]:
    """Gli alimenti del pasto: nomi puliti, niente doppioni, quantita' sensate."""
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        name = " ".join(item.name.split())[:80]
        if not name or normalize(name) in seen:
            continue
        seen.add(normalize(name))
        quantity = item.quantity if item.quantity and 0 < item.quantity <= 3000 else None
        unit = (item.unit or "g") if quantity is not None else ""
        if quantity is not None:
            quantity = round(quantity, 1)
            quantity = int(quantity) if quantity == int(quantity) else quantity
        out.append({"name": name, "quantity": quantity, "unit": unit})
    return out[:MAX_COMPONENTS]


def components_text(components: list[dict]) -> str:
    """"pasta integrale 80 g, verdura a volonta'" per prompt e chat."""

    def one(item: dict) -> str:
        if item.get("quantity") is None:
            return f"{item['name']} a volontà"
        return f"{item['name']} {item['quantity']} {item['unit']}".strip()

    return ", ".join(one(item) for item in components)


class Guard:
    """Allergie, intolleranze e alimenti da evitare, controllati sui nomi degli
    alimenti del pasto (come ``avoided`` fa sugli ingredienti delle ricette):
    il modello sbaglia di rado, ma qui non puo' sbagliare."""

    def __init__(self, user, avoid: list[str]):
        self.user = user
        self.restrictions = [
            (preference.label, ids, allergen)
            for preference, ids, allergen in PreferenceIndex(user).items
            if preference.is_restriction
        ]
        self.avoid = {name: variants(name) for name in avoid}
        self.cache: dict[str, str | None] = {}

    def problem(self, name: str) -> str | None:
        """Perche' l'alimento non puo' stare nel pasto, o None."""
        key = normalize(name)
        if key not in self.cache:
            self.cache[key] = self._check(name)
        return self.cache[key]

    def _check(self, name: str) -> str | None:
        ingredient = match_ingredient(name, self.user)
        keys = set(variants(name)) | set(ingredient.keys if ingredient else [])
        allergens = set(ingredient.allergens if ingredient else [])
        if found := detect_allergen(name):
            allergens.add(found)
        for label, ids, allergen in self.restrictions:
            if (ingredient is not None and ingredient.id in ids) or (
                allergen and allergen in allergens
            ):
                return label
        for avoid_name, wanted in self.avoid.items():
            if any(word == k or word in k.split(" ") for word in wanted for k in keys):
                return avoid_name
        return None

    def clean(self, components: list[dict]) -> tuple[list[dict], list[str]]:
        kept, removed = [], []
        for item in components:
            if self.problem(item["name"]):
                removed.append(item["name"])
            else:
                kept.append(item)
        return kept, removed


def _keeps(recipe: Recipe) -> int:
    return DEFAULT_KEEPS_DAYS if recipe.keeps_days is None else recipe.keeps_days


def _suggestions(choice: MealChoice, numbered: dict[int, Recipe], wait: int) -> list[dict]:
    """Fino a due suggerimenti: le candidate scelte che reggono l'attesa, poi l'idea."""
    out: list[dict] = []
    for number in choice.recipes:
        recipe = numbered.get(number)
        entry = {"recipe": str(recipe.id)} if recipe is not None else None
        if entry and entry not in out and wait <= _keeps(recipe):
            out.append(entry)
    title = " ".join(choice.idea.split())[:120]
    if len(out) < MAX_SUGGESTIONS and title:
        out.append({"title": title, "idea": " ".join(choice.idea_note.split())[:300]})
    return out[:MAX_SUGGESTIONS]


def leftover_lunches(plan: MealPlan) -> dict:
    """Con "la sera cucino anche il pranzo dopo": ``{giorno del pranzo: giorno
    della cena}`` per ogni pranzo che e' l'avanzo della cena della sera prima.

    Una sola cottura, doppia porzione: il pranzo copia gli alimenti della cena,
    che unisce a occhio meta' pranzo e meta' cena del piano (anche alla
    lettera: chi sceglie questa modalita' vuole mangiare a pranzo la cena). Il
    primo pranzo del piano non ha una cena prima.
    """
    options = plan.settings
    slots = set(options.get("slots", []))
    if (
        options.get("prep_mode") != "evening_before"
        or not {MealSlot.LUNCH, MealSlot.DINNER} <= slots
    ):
        return {}
    days = plan_dates(plan.start_date, plan.days)
    return {day: day - timedelta(days=1) for day in days[1:]}


def _diet_foods(names: list[str], nutritionist: NutritionistPlan | None) -> list[str]:
    """Gli alimenti delle frequenze nominati dall'LLM, coi nomi delle regole
    (gli altri si scartano: senza un nome noto non si possono contare)."""
    if nutritionist is None:
        return []
    known = {normalize(item["food"]): item["food"] for item in nutritionist.rules.get("weekly", [])}
    return list(dict.fromkeys(known[normalize(n)] for n in names if normalize(n) in known))


def frequency_targets(
    nutritionist: NutritionistPlan | None, days: int, slots: list[str] | None = None
) -> dict[str, int]:
    """Quante volte ogni alimento delle frequenze in questi giorni (una
    settimana corta ne ha in proporzione). Solo le frequenze dei pasti che si
    preparano: "yogurt 3 volte" non si conta su pranzi e cene."""
    if nutritionist is None:
        return {}
    return {
        item["food"]: round(item["times"] * days / 7)
        for item in prepared_weekly(nutritionist.rules, slots)
    }


def frequency_problems(meals: dict[tuple, dict], targets: dict[str, int]) -> dict[str, int]:
    """``{alimento: volte contate}`` per gli alimenti che non tornano.

    Contati sui pasti, pranzi-avanzo compresi: prima l'LLM contava i piatti, e
    con gli avanzi le patate uscivano 6 volte invece di 3.
    """
    counts = dict.fromkeys(targets, 0)
    for meal in meals.values():
        for food in meal["weekly"]:
            if food in counts:
                counts[food] += 1
    return {food: count for food, count in counts.items() if count != targets[food]}


def _over_notes(keys: list[tuple], meals: dict[tuple, dict], targets) -> dict[tuple, str]:
    """I pasti oltre le frequenze rimasti dopo la correzione: una nota, il
    pasto non si cambia da solo e l'utente decide."""
    counts: dict[str, int] = {}
    over: dict[tuple, str] = {}
    for key in keys:
        exceeded = []
        for food in meals[key]["weekly"]:
            counts[food] = counts.get(food, 0) + 1
            if food in targets and counts[food] > targets[food]:
                exceeded.append(
                    ngettext("%(food)s %(times)s volta", "%(food)s %(times)s volte", targets[food])
                    % {"food": food, "times": targets[food]}
                )
        if exceeded:
            over[key] = _("Oltre le frequenze del piano (%(rules)s a settimana).") % {
                "rules": ", ".join(exceeded)
            }
    return over


# --- 4. una settimana dall'inizio alla fine -----------------------------------------------


def week_rows(plan: MealPlan, week: int) -> list[dict]:
    days = plan_dates(plan.start_date, plan.days)[week * 7 : week * 7 + 7]
    options = plan.settings
    return schedule(
        plan.start_date, days, options.get("slots", []), options.get("prep_mode", "none")
    )


def _rules_block(nutritionist: NutritionistPlan | None, slots: list[str] | None = None) -> str:
    from .nutritionist import rules_prompt

    if nutritionist is None:
        if slots and set(slots) & MAIN_SLOTS:
            return NO_RULES + "\n" + side_rule({})
        return NO_RULES
    title = (
        "Piano alimentare dalle linee guida"
        if nutritionist.source == NutritionistPlan.Source.GUIDELINES
        else "Piano del nutrizionista"
    )
    return rules_prompt(nutritionist.rules, nutritionist.strict, title, slots)


class Week:
    """Lo stato di una settimana mentre si compone: i pasti scelti per chiave
    ``(data, pasto)`` come ``{"components", "weekly", "suggestions", "note"}``."""

    def __init__(self, plan: MealPlan, week: int):
        self.plan = plan
        self.all_rows = week_rows(plan, week)
        self.nutritionist = nutritionist_of(plan)
        self.leftovers = leftover_lunches(plan)
        feeding = set(self.leftovers.values())
        # I pranzi-avanzo non si compongono: li copia il codice dalla cena
        # prima, che quindi deve reggere almeno un giorno in frigo.
        self.rows = [
            {**row, "wait": max(row["wait"], 1), "feeds_lunch": True}
            if row["slot"] == MealSlot.DINNER and row["date"] in feeding
            else row
            for row in self.all_rows
            if not (row["slot"] == MealSlot.LUNCH and row["date"] in self.leftovers)
        ]
        self.wanted = {(row["date"].isoformat(), row["slot"]): row for row in self.rows}
        self.candidates = candidate_recipes(plan)
        self.numbered = dict(enumerate(self.candidates, start=1))
        self.profile, self.forbidden = profile_summary(plan)
        avoid = self.nutritionist.rules.get("avoid_foods", []) if self.nutritionist else []
        self.guard = Guard(plan.owner, avoid)
        self.slots = list(plan.settings.get("slots", []))
        # Yogurt e frutta secca restano a colazione e merenda (foods.py).
        self.side_foods = side_only_foods(self.nutritionist.rules if self.nutritionist else {})
        self.meals: dict[tuple, dict] = {}

    def candidates_text(self) -> str:
        return (
            "\n".join(describe_candidate(n, r) for n, r in self.numbered.items())
            or "(nessuna: suggerisci solo idee)"
        )

    def take(self, choices: WeekChoices) -> None:
        """Le scelte dell'LLM per i pasti richiesti, ripulite dal codice."""
        for choice in choices.meals:
            key = (choice.date, choice.slot)
            row = self.wanted.get(key)
            if row is None:
                continue
            components = clean_components(choice.components)
            if choice.slot in MAIN_SLOTS:
                components = [
                    item
                    for item in components
                    if not is_side_food(item["name"], self.side_foods)
                ]
            components, removed = self.guard.clean(components)
            if not components:
                continue  # niente di mangiabile: lo riempie ``fill``
            note = ""
            if removed:
                note = _("Tolto perché non puoi mangiarlo: %(foods)s.") % {
                    "foods": ", ".join(removed)
                }
            self.meals[key] = {
                "components": components,
                "weekly": _diet_foods(choice.weekly, self.nutritionist),
                "suggestions": _suggestions(choice, self.numbered, row["wait"]),
                "note": note,
            }

    def fill(self) -> None:
        """I pasti saltati dall'LLM: un pasto dello stesso tipo gia' composto
        questa settimana, il meno ripetuto."""
        used: dict[str, int] = {}
        for meal in self.meals.values():
            signature = repr(meal["components"])
            used[signature] = used.get(signature, 0) + 1
        for key, row in self.wanted.items():
            if key in self.meals:
                continue
            main = row["slot"] in MAIN_SLOTS
            pool = [
                meal
                for (_day, slot), meal in self.meals.items()
                if (slot in MAIN_SLOTS) == main and not meal.get("filled")
            ]
            if not pool:
                continue
            best = min(pool, key=lambda meal: used.get(repr(meal["components"]), 0))
            used[repr(best["components"])] = used.get(repr(best["components"]), 0) + 1
            self.meals[key] = {
                **best,
                "filled": True,
                "note": _("Ripreso da un altro giorno della settimana: cambialo se vuoi."),
            }

    def with_leftovers(self) -> dict[tuple, dict]:
        """Tutti i pasti della settimana, coi pranzi-avanzo copiati dalla cena
        della sera prima (anche se e' della settimana prima)."""
        out = dict(self.meals)
        for row in self.all_rows:
            if row["slot"] != MealSlot.LUNCH or row["date"] not in self.leftovers:
                continue
            evening = self.leftovers[row["date"]]
            dinner = self.meals.get((evening.isoformat(), MealSlot.DINNER))
            if dinner is None:
                earlier = self.plan.meals.filter(date=evening, slot=MealSlot.DINNER).first()
                if earlier is not None and earlier.components:
                    dinner = {
                        "components": earlier.components,
                        "weekly": earlier.diet_foods,
                        "suggestions": earlier.suggestions,
                        "note": "",
                    }
            if dinner is not None:
                out[(row["date"].isoformat(), row["slot"])] = {
                    **dinner,
                    "note": _("Avanzo della cena di ieri."),
                    "leftover": True,
                }
        return out

    def repair(self, problems: dict[str, int], targets: dict[str, int]) -> None:
        """Una seconda chiamata che cambia solo i pasti che servono perche' le
        frequenze tornino. Quello che resta fuori diventa una nota."""
        meals = self.with_leftovers()
        lines = []
        for key in sorted(meals):
            meal = meals[key]
            day = date_of(key[0])
            line = (
                f"- {key[0]} ({WEEKDAYS[day.weekday()]}), {SLOT_NAMES[key[1]]} [{key[1]}]: "
                f"{components_text(meal['components'])}"
            )
            if meal["weekly"]:
                line += f" (frequenze: {', '.join(meal['weekly'])})"
            if meal.get("leftover"):
                line += " — avanzo, non cambiarlo"
            lines.append(line)
        prompt = REPAIR_PROMPT.format(
            week="\n".join(lines),
            problems="\n".join(
                f"- {food}: {count} volte, il piano dice {targets[food]}"
                for food, count in problems.items()
            ),
            rules=_rules_block(self.nutritionist, self.slots),
            candidates=self.candidates_text(),
            forbidden=", ".join(self.forbidden) or "nessuna",
        )
        choices, _model = generate(
            [prompt],
            WeekChoices,
            feature="plan_week",
            user=self.plan.owner,
            timeout_ms=120_000,
            temperature=0.3,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        self.take(choices)


def date_of(text: str) -> date:
    return date.fromisoformat(text)


def generate_week(plan: MealPlan, week: int) -> None:
    """Compone e salva i pasti della settimana ``week`` (0 = la prima)."""
    options = plan.settings
    state = Week(plan, week)
    goal = ""
    if note := options.get("goal_note"):
        goal = f"\nIn piu', in parole sue: {note}"
    excluded = excluded_titles(plan)
    prompt = WEEK_PROMPT.format(
        profile=state.profile,
        rules=_rules_block(state.nutritionist, state.slots),
        goal=goal,
        servings=options.get("servings", 1),
        slots=_slot_lines(state.rows),
        candidates=state.candidates_text(),
        leftovers=LEFTOVERS_RULE if state.leftovers else "",
        minutes=options.get("minutes", 45),
        difficulty=DIFFICULTY_NAMES.get(options.get("difficulty", "medium"), "media"),
        avoid=(
            "\n- Non suggerire questi piatti, nemmeno come idea: " + "; ".join(excluded) + "."
            if excluded
            else ""
        ),
    )
    choices, _model = generate(
        [prompt],
        WeekChoices,
        feature="plan_week",
        user=plan.owner,
        timeout_ms=120_000,
        temperature=0.5,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    state.take(choices)
    state.fill()

    targets = frequency_targets(
        state.nutritionist, len({row["date"] for row in state.all_rows}), state.slots
    )
    if problems := frequency_problems(state.with_leftovers(), targets):
        try:
            state.repair(problems, targets)
        except Exception:
            # La correzione e' un di piu': senza, restano le note sui pasti.
            logger.warning("Correzione delle frequenze del piano %s non riuscita", plan.id)
    meals = state.with_leftovers()
    over = _over_notes(sorted(meals), meals, targets)

    servings = options.get("servings", 1)
    rows = {(row["date"].isoformat(), row["slot"]): row for row in state.all_rows}
    created = []
    for key, row in sorted(rows.items()):
        meal = meals.get(key)
        note = meal["note"] if meal else _("Nessuna proposta per questo pasto: componilo tu.")
        if meal and key in over:
            note = " ".join(filter(None, [note, over[key]]))
        created.append(
            PlannedMeal(
                plan=plan,
                date=row["date"],
                slot=row["slot"],
                servings=servings,
                cooked_on=row["cooked_on"],
                note=note[:200],
                components=meal["components"] if meal else [],
                suggestions=meal["suggestions"] if meal else [],
                diet_foods=meal["weekly"] if meal else [],
            )
        )
    with transaction.atomic():
        plan.meals.filter(date__in=[row["date"] for row in state.all_rows]).delete()
        PlannedMeal.objects.bulk_create(created)
