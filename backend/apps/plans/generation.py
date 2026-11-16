"""Generazione di una settimana del piano (progettazione 4.3, ADR 0007).

Il codice fa quello che deve essere sicuro, l'LLM quello che deve essere vario:

1. **Candidati (codice)**: le ricette delle fonti scelte (ricettario e
   ricettari PDF), senza quelle che toccano un'allergia o un'intolleranza e
   senza i tag esclusi.
2. **Settimana (LLM)**: per ogni pasto una ricetta candidata, o il titolo di
   una ricetta nuova quando non c'e' niente di adatto, tenendo conto di
   quanti giorni il pasto aspetta in frigo (meal prep).
3. **Ricette nuove (LLM)**: scritte per intero, una chiamata ciascuna, e
   salvate fuori dal ricettario.
4. **Controlli (codice)**: allergeni ricontrollati sugli ingredienti veri,
   giorni in frigo rispettati (altrimenti si cucina al momento).

Con il piano del nutrizionista (ADR 0010) le sue regole prendono il posto di
"cosa vuoi ottenere" e i suoi alimenti da evitare sono controllati come le
allergie.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Literal

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from pydantic import BaseModel, Field

from apps.ai.client import MAX_OUTPUT_TOKENS, generate
from apps.profiles.models import FoodPreference, MealSlot, Profile
from apps.recipes.generated import save_generated
from apps.recipes.importing import ImportedRecipe
from apps.recipes.matching import normalize
from apps.recipes.models import Recipe, RecipeIngredient
from apps.recipes.services import PreferenceIndex, recipe_allergens

from .models import MealPlan, NutritionistPlan, PlannedMeal
from .schedule import plan_dates, schedule

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 150
NEW_RECIPES_PER_WEEK = 6
MAX_NEW_RECIPES_PER_WEEK = 12
# Varieta' minima: quante volte a settimana puo' tornare la stessa ricetta.
# Pranzi e cene: due (cucinata una volta, mangiata due); colazioni e spuntini: tre.
MAX_USES = {"main": 2, "other": 3}
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


# --- 2. settimana -----------------------------------------------------------------------


class MealChoice(BaseModel):
    date: str = Field(description="AAAA-MM-GG, uno dei giorni richiesti")
    slot: Literal["breakfast", "morning_snack", "lunch", "afternoon_snack", "dinner"]
    recipe: int | None = Field(default=None, description="Numero di una ricetta candidata")
    new_recipe: str | None = Field(
        default=None, description="Titolo di una ricetta nuova, solo se nessuna candidata va bene"
    )
    idea: str = Field(default="", description="Per una ricetta nuova: una frase su cosa contiene")
    portion: str = Field(
        default="",
        description="Solo con il nutrizionista: le dosi a persona di questo pasto secondo il "
        "suo piano, alimenti e grammi (es. '45 g riso, 85 g ceci lessati, 200 g verdura')",
    )
    weekly: list[str] = Field(
        default_factory=list,
        description="Solo con il nutrizionista: gli alimenti delle frequenze settimanali che "
        "questo pasto contiene, coi nomi esatti della lista",
    )


class WeekChoices(BaseModel):
    meals: list[MealChoice]


WEEK_PROMPT = """Sei un nutrizionista che compone il piano alimentare di una settimana
per una persona, in stile mediterraneo e coerente con le linee guida per una sana
alimentazione. Rispondi solo col JSON richiesto.

{profile}

Cosa vuole ottenere con questo piano: {goal}
Porzioni per pasto: {servings}.

Pasti da riempire (giorno, pasto, giorni di attesa in frigo):
{slots}

"Giorni di attesa" = quanti giorni passano da quando si cucina a quando si
mangia (meal prep). Con attesa N scegli solo ricette che reggono in frigo
almeno N giorni; con attesa 0 va bene tutto. Lo stesso giorno di cottura puoi
usare la stessa ricetta per piu' pasti (si cucina una volta per tutti): e' il
modo giusto di fare meal prep.

Ricette candidate (numero tra parentesi quadre):
{candidates}

Regole:
- Usa le ricette candidate col loro numero; inventa una ricetta nuova solo se
  nessuna candidata va bene per quel pasto, al massimo {max_new} nuove in tutto,
  con un titolo chiaro e in "idea" una frase sugli ingredienti.
- Rispetta il pasto: niente cena a colazione. Una ricetta senza pasti indicati
  va bene per pranzo e cena.
- Varia: ogni ricetta al massimo {max_main} volte nella settimana per pranzi e
  cene (meglio se cucinata una volta sola per due pasti) e al massimo
  {max_other} volte per colazioni e spuntini. Alterna legumi, pesce, carne
  bianca, uova, formaggi; verdura ogni giorno; cereali integrali quando puoi.
{variety}{avoid}
- Evita le ricette segnate "CONTIENE COSE CHE NON PIACCIONO" se ci sono alternative.
- Tempo per cucinare in una sessione: circa {minutes} minuti; difficoltà al massimo {difficulty}.
{previous}
Un elemento in "meals" per OGNI pasto della lista, con la stessa data e lo stesso pasto."""


def _slot_lines(rows: list[dict]) -> str:
    return "\n".join(
        f"- {row['date'].isoformat()} ({WEEKDAYS[row['date'].weekday()]}), "
        f"{SLOT_NAMES[row['slot']]} [{row['slot']}], attesa {row['wait']} giorni"
        for row in rows
    )


# --- 3. ricette nuove -------------------------------------------------------------------


NEW_RECIPE_PROMPT = """Scrivi la ricetta "{title}" per un piano alimentare casalingo.
Idea: {idea}
Per {servings} porzioni, adatta a: {slots}. Tempo totale massimo {minutes} minuti,
difficoltà al massimo {difficulty}. Deve reggere in frigo almeno {wait} giorni.

Persona:
{profile}

NON deve contenere in nessun modo: {forbidden}.{nutritionist}
Ingredienti comuni da supermercato italiano, quantità in grammi o ml quando ha senso.
Rispondi solo col JSON della ricetta; "inferred" vuoto; tag in italiano (1-3)."""

DIFFICULTY_NAMES = {"easy": "facile", "medium": "media", "hard": "difficile"}


def write_recipe(
    plan: MealPlan,
    title: str,
    idea: str,
    uses: list[dict],
    profile: str,
    forbidden: list[str],
    nutritionist: NutritionistPlan | None = None,
) -> Recipe | None:
    """Scrive e salva una ricetta nuova per il piano; None se tocca un divieto."""
    from .nutritionist import avoided, combined_meal_text, meal_rules_text

    options = plan.settings
    extra = ""
    avoid = []
    if nutritionist is not None:
        avoid = nutritionist.rules.get("avoid_foods", [])
        if any(row.get("feeds_lunch") for row in uses):
            # Cena che e' anche il pranzo di domani: le due opzioni in un piatto.
            extra += combined_meal_text(nutritionist.rules)
        else:
            extra += meal_rules_text(nutritionist.rules, [row["slot"] for row in uses])
        if avoid:
            extra += "\nIl nutrizionista dice di evitare: " + ", ".join(avoid) + "."
    slots = sorted({SLOT_NAMES[row["slot"]] for row in uses})
    prompt = NEW_RECIPE_PROMPT.format(
        title=title,
        idea=idea or "a tua scelta, coerente col titolo",
        servings=options.get("servings", 1),
        slots=", ".join(slots),
        minutes=options.get("minutes", 45),
        difficulty=DIFFICULTY_NAMES.get(options.get("difficulty", "medium"), "media"),
        wait=max(row["wait"] for row in uses),
        profile=profile,
        forbidden=", ".join(forbidden) or "nessun divieto",
        nutritionist=extra,
    )
    written, _model = generate(
        [prompt],
        ImportedRecipe,
        feature="plan_recipe",
        user=plan.owner,
        timeout_ms=60_000,
        temperature=0.6,
    )
    recipe = save_generated(
        plan.owner, written, source=Recipe.Source.PLAN, servings=options.get("servings")
    )
    if recipe is not None and avoid and avoided(recipe, avoid):
        recipe.delete(hard=True)
        return None
    return recipe


# --- 4. una settimana dall'inizio alla fine -----------------------------------------------


def week_rows(plan: MealPlan, week: int) -> list[dict]:
    days = plan_dates(plan.start_date, plan.days)[week * 7 : week * 7 + 7]
    options = plan.settings
    return schedule(
        plan.start_date, days, options.get("slots", []), options.get("prep_mode", "none")
    )


def _fits(recipe: Recipe, group: str) -> bool:
    """La ricetta va bene per quel gruppo di pasti? Senza pasti indicati: pranzo e cena."""
    if not recipe.meal_slots:
        return group == "main"
    slots = set(recipe.meal_slots)
    return bool(slots & MAIN_SLOTS) if group == "main" else bool(slots - MAIN_SLOTS)


def variety_needs(
    rows: list[dict], candidates: list[Recipe], limits: dict[str, int] | None = None
) -> dict[str, int]:
    """Quante ricette nuove servono perche' la varieta' minima si possa rispettare.

    Calcolato qui e non lasciato all'LLM: con poche candidate il modello
    preferisce ripetere (la stessa torta ogni mattina) invece di inventare.
    """
    needs = {}
    for group, limit in (limits or MAX_USES).items():
        meals = sum(1 for row in rows if (row["slot"] in MAIN_SLOTS) == (group == "main"))
        if not meals:
            continue
        distinct = -(-meals // limit)  # arrotondato per eccesso
        available = sum(1 for recipe in candidates if _fits(recipe, group))
        needs[group] = max(0, distinct - available)
    return needs


def leftover_lunches(plan: MealPlan) -> dict:
    """Con "la sera cucino anche il pranzo dopo": ``{giorno del pranzo: giorno
    della cena}`` per ogni pranzo che e' l'avanzo della cena della sera prima.

    Una sola cottura, doppia porzione: prima si sceglievano pranzo e cena come
    due piatti diversi, e la sera si cucinavano due cose (e lo stesso piatto
    su due sere di fila). Il primo pranzo del piano non ha una cena prima.
    Anche con il nutrizionista alla lettera: chi sceglie questa modalita' vuole
    mangiare a pranzo la cena, e il piatto unisce a occhio le sue opzioni di
    pranzo e cena (``combined_meal_text``). Prima qui si rinunciava agli avanzi
    e la sera si cucinavano due piatti diversi.
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


def _diet_foods(names: list[str], nutritionist: NutritionistPlan) -> list[str]:
    """Gli alimenti delle frequenze nominati dall'LLM, coi nomi delle regole
    (gli altri si scartano: senza un nome noto non si possono contare)."""
    known = {normalize(item["food"]): item["food"] for item in nutritionist.rules.get("weekly", [])}
    return list(dict.fromkeys(known[normalize(n)] for n in names if normalize(n) in known))


def _over_frequencies(
    keys: list[tuple], diet: dict[tuple, tuple[str, list[str]]], nutritionist
) -> dict[tuple, str]:
    """I pasti della settimana oltre le frequenze del nutrizionista, contate
    sui pasti (un pranzo-avanzo conta come la sua cena). Non si cambia niente:
    il pasto porta una nota e l'utente decide se cambiarlo. Prima l'LLM contava
    i piatti, e con gli avanzi le patate uscivano 6 volte invece di 3."""
    if nutritionist is None:
        return {}
    limits = {item["food"]: item["times"] for item in nutritionist.rules.get("weekly", [])}
    counts: dict[str, int] = {}
    over: dict[tuple, str] = {}
    for key in keys:
        exceeded = []
        for food in diet.get(key, ("", []))[1]:
            counts[food] = counts.get(food, 0) + 1
            if food in limits and counts[food] > limits[food]:
                exceeded.append(
                    ngettext("%(food)s %(times)s volta", "%(food)s %(times)s volte", limits[food])
                    % {"food": food, "times": limits[food]}
                )
        if exceeded:
            over[key] = _("Oltre le frequenze del nutrizionista (%(rules)s a settimana).") % {
                "rules": ", ".join(exceeded)
            }
    return over


def _keeps(recipe: Recipe) -> int:
    return DEFAULT_KEEPS_DAYS if recipe.keeps_days is None else recipe.keeps_days


def generate_week(plan: MealPlan, week: int) -> None:
    """Sceglie e salva i pasti della settimana ``week`` (0 = la prima)."""
    from .nutritionist import rules_prompt

    options = plan.settings
    all_rows = week_rows(plan, week)
    candidates = candidate_recipes(plan)
    nutritionist = nutritionist_of(plan)
    leftovers = leftover_lunches(plan)
    # I pranzi-avanzo non si scelgono: li copia il codice dalla cena prima, che
    # quindi deve reggere almeno un giorno in frigo.
    feeding = set(leftovers.values())
    rows = [
        {**row, "wait": max(row["wait"], 1), "feeds_lunch": True}
        if row["slot"] == MealSlot.DINNER and row["date"] in feeding
        else row
        for row in all_rows
        if not (row["slot"] == MealSlot.LUNCH and row["date"] in leftovers)
    ]
    numbered = dict(enumerate(candidates, start=1))
    profile, forbidden = profile_summary(plan)
    # Ogni cena vale gia' due pasti: una volta sola a settimana.
    limits = {**MAX_USES, "main": 1} if leftovers else None
    needs = variety_needs(rows, candidates, limits)
    new_needed = sum(needs.values())
    share = options.get("new_share")
    if share is None:
        # Piani creati prima della percentuale: come allora.
        max_new = min(MAX_NEW_RECIPES_PER_WEEK, max(NEW_RECIPES_PER_WEEK, new_needed))
    else:
        # Una ricetta copre in media un pasto e mezzo (cucinata per due); con i
        # pranzi-avanzo le cene sono gia' una per ricetta.
        target = round(len(rows) * share / 100 / (1 if leftovers else 1.5))
        max_new = min(MAX_NEW_RECIPES_PER_WEEK, max(new_needed, target))
    if nutritionist is not None and nutritionist.strict:
        # Alla lettera le candidate corrispondono di rado: servono piu' ricette nuove.
        max_new = MAX_NEW_RECIPES_PER_WEEK
    goal = options.get("goal_note") or "un piano equilibrato secondo il profilo"
    if nutritionist is not None:
        goal = "seguire il piano del nutrizionista.\n" + rules_prompt(
            nutritionist.rules, nutritionist.strict
        )
        if note := options.get("goal_note"):
            goal += f"\nIn piu', in parole sue: {note}"
    variety = []
    if needs.get("main"):
        variety.append(
            f"- Le candidate per pranzi e cene non bastano per variare: inventa ALMENO "
            f"{needs['main']} ricette nuove per pranzi e cene."
        )
    if share == 0:
        variety.append(
            "- Usa le ricette candidate: inventa solo se servono per la varieta' minima o "
            "se per un pasto nessuna candidata va bene."
        )
    elif share == 100:
        variety.append("- Non usare le candidate: inventa tu tutte le ricette.")
    elif share is not None:
        variety.append(
            f"- Circa il {share}% dei pasti con ricette nuove inventate da te, il resto "
            "con le candidate."
        )
    if leftovers:
        variety.append(
            "- La sera si cucina la cena in doppia porzione: meta' e' il pranzo del giorno "
            "dopo (da portare o scaldare). Scegli cene che restano buone il giorno dopo; i "
            "pranzi non li devi scegliere, tranne quelli nella lista."
        )
        if nutritionist is not None:
            variety.append(
                "- Le frequenze settimanali del nutrizionista si contano sui pasti, non sui "
                "piatti: una cena che fa anche da pranzo conta DUE volte (patate a cena e "
                "il giorno dopo a pranzo sono 2 volte). Tienine conto prima di rispondere."
            )
            variety.append(
                "- Con il nutrizionista, ogni cena che fa anche da pranzo e' un piatto unico "
                "che vale per tutti e due i pasti: ogni porzione unisce, a occhio, meta' di "
                "un'opzione del pranzo e meta' di una della cena (per esempio cereali e "
                "legumi del pranzo con il pesce della cena), cosi' cena e pranzo insieme "
                "portano tutti e due i pasti. Per queste cene vale questo, anche al posto "
                'della regola alla lettera; in "idea" scrivi le due opzioni unite con le '
                "grammature per porzione."
            )
    if nutritionist is not None:
        variety.append(
            '- Per OGNI pasto scrivi in "portion" le dosi a persona secondo il nutrizionista '
            "(alimenti e grammi, verdura compresa), anche per le ricette candidate: si mangia "
            'quella quantita\', non quella della ricetta. In "weekly" gli alimenti delle '
            "frequenze settimanali che il pasto contiene, coi nomi della lista."
        )
    if needs.get("other"):
        variety.append(
            f"- Le candidate per colazioni e spuntini non bastano: inventa ALMENO "
            f"{needs['other']} ricette nuove per colazioni e spuntini."
        )
    previous = list(
        plan.meals.filter(recipe__isnull=False).values_list("recipe__title", flat=True).distinct()
    )
    prompt = WEEK_PROMPT.format(
        profile=profile,
        goal=goal,
        servings=options.get("servings", 1),
        slots=_slot_lines(rows),
        candidates="\n".join(describe_candidate(n, r) for n, r in numbered.items())
        or "(nessuna: inventale tutte)",
        max_new=max_new if candidates else len(rows),
        max_main=1 if leftovers else MAX_USES["main"],
        max_other=MAX_USES["other"],
        variety="\n".join(variety),
        avoid=(
            "\n- Non proporre questi piatti, nemmeno come ricetta nuova: "
            + "; ".join(excluded_titles(plan))
            + "."
            if excluded_titles(plan)
            else ""
        ),
        minutes=options.get("minutes", 45),
        difficulty=DIFFICULTY_NAMES.get(options.get("difficulty", "medium"), "media"),
        previous=(
            "Nelle settimane prima ha gia' mangiato: " + ", ".join(previous[:40]) + ".\n"
            if previous
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

    wanted = {(row["date"].isoformat(), row["slot"]): row for row in rows}
    picked: dict[tuple, MealChoice] = {}
    for choice in choices.meals:
        key = (choice.date, choice.slot)
        if key in wanted and key not in picked:
            picked[key] = choice

    # Le ricette nuove: una chiamata per titolo, riusata per tutti i suoi pasti.
    new_uses: dict[str, list[dict]] = {}
    new_ideas: dict[str, tuple[str, str]] = {}
    for key, choice in picked.items():
        if choice.recipe in numbered or not choice.new_recipe:
            continue
        title = " ".join(choice.new_recipe.split())[:120]
        new_uses.setdefault(normalize(title), []).append(wanted[key])
        new_ideas.setdefault(normalize(title), (title, choice.idea))
    limit = max_new if candidates else len(rows)
    written: dict[str, Recipe | None] = {}
    for key in list(new_uses)[:limit]:
        title, idea = new_ideas[key]
        written[key] = write_recipe(
            plan, title, idea, new_uses[key], profile, forbidden, nutritionist
        )

    # Pasti rimasti vuoti (l'LLM li ha saltati o la sua ricetta e' stata scartata):
    # li riempie il codice con ricette gia' sicure, le meno usate, che reggono l'attesa.
    pool = [*candidates, *(recipe for recipe in written.values() if recipe is not None)]
    usage: dict = {}
    chosen: dict[tuple, Recipe] = {}
    # Dosi della dieta e alimenti delle frequenze, per i pasti scelti dall'LLM.
    diet: dict[tuple, tuple[str, list[str]]] = {}
    for key in wanted:
        choice = picked.get(key)
        recipe = None
        if choice and choice.recipe in numbered:
            recipe = numbered[choice.recipe]
        elif choice and choice.new_recipe:
            recipe = written.get(normalize(" ".join(choice.new_recipe.split())[:120]))
        if recipe is not None:
            chosen[key] = recipe
            usage[recipe.id] = usage.get(recipe.id, 0) + 1
            if nutritionist is not None:
                diet[key] = (choice.portion, _diet_foods(choice.weekly, nutritionist))
    if nutritionist is not None and nutritionist.strict:
        # Alla lettera: i buchi si riempiono solo con le ricette che l'LLM ha
        # scelto questa settimana seguendo le opzioni, mai con altre del ricettario.
        pool = list({recipe.id: recipe for recipe in chosen.values()}.values())
    for key, row in wanted.items():
        if key in chosen:
            continue
        group = "main" if row["slot"] in MAIN_SLOTS else "other"
        options_ = [r for r in pool if _fits(r, group) and row["wait"] <= _keeps(r)]
        if options_:
            best = min(options_, key=lambda r: usage.get(r.id, 0))
            chosen[key] = best
            usage[best.id] = usage.get(best.id, 0) + 1

    # Pranzi-avanzo: la cena della sera prima, anche se e' della settimana prima.
    for row in all_rows:
        if row["slot"] != MealSlot.LUNCH or row["date"] not in leftovers:
            continue
        evening = leftovers[row["date"]]
        evening_key = (evening.isoformat(), MealSlot.DINNER)
        dinner = chosen.get(evening_key)
        dinner_diet = diet.get(evening_key)
        if dinner is None:
            earlier = (
                plan.meals.filter(date=evening, slot=MealSlot.DINNER)
                .select_related("recipe")
                .first()
            )
            dinner = earlier.recipe if earlier else None
            dinner_diet = (earlier.diet_portion, earlier.diet_foods) if earlier else None
        key = (row["date"].isoformat(), row["slot"])
        wanted[key] = row
        if dinner is not None:
            chosen[key] = dinner
            if dinner_diet:
                # Stesso piatto, stessa porzione: meta' pranzo e meta' cena.
                diet[key] = dinner_diet
    over = _over_frequencies(sorted(wanted), diet, nutritionist)

    servings = options.get("servings", 1)
    meals = []
    for key, row in sorted(wanted.items()):
        recipe = chosen.get(key)
        note = "" if recipe is not None else _("Nessuna ricetta adatta: scegline una tu.")
        cooked = row["cooked_on"]
        if recipe is not None and row["wait"] > _keeps(recipe):
            # Non regge l'attesa: si cucina il giorno stesso.
            cooked = row["date"]
            note = _("Non regge in frigo: meglio cucinarla il giorno stesso.")
        portion, foods = diet.get(key, ("", [])) if recipe is not None else ("", [])
        if recipe is not None and key in over:
            note = " ".join(filter(None, [note, over[key]]))[:200]
        meals.append(
            PlannedMeal(
                plan=plan,
                date=row["date"],
                slot=row["slot"],
                recipe=recipe,
                servings=servings,
                cooked_on=cooked,
                note=note,
                diet_portion=" ".join(portion.split())[:300],
                diet_foods=foods,
            )
        )
    with transaction.atomic():
        plan.meals.filter(date__in=[row["date"] for row in all_rows]).delete()
        PlannedMeal.objects.bulk_create(meals)
