"""Dalla lista dei pasti alla lista della spesa (progettazione 4.7, ADR 0008).

Per ogni pasto del piano nell'intervallo, sommate per ingrediente dopo averle
portate alla stessa unita' (quella di default dell'ingrediente nel catalogo):

- per ingredienti (ADR 0023): gli alimenti del piano per le porzioni del
  pasto e, solo se l'utente ha approvato una ricetta, i suoi ingredienti in
  piu' (quelli che non sono gia' fra gli alimenti del pasto);
- nei piani di prima, fatti di ricette: le quantita' della ricetta scalate
  alle porzioni del pasto.

Le unita':

- g, kg -> g; ml, l, cucchiai, cucchiaini, tazze -> ml (e ml ~ g quando
  l'ingrediente si pesa: per olio, latte e simili l'errore e' piccolo);
- pezzi <-> grammi coi grammi per pezzo del catalogo ("2 uova" -> 120 g);
- quello che non si converte ("1 scatola", "un mazzetto") resta su una voce
  a parte, senza sommarlo;
- "q.b." e quantita' mancanti: la voce c'e', senza quantita'.

Le voci facoltative non si comprano. I basilari (sale, olio, pepe) partono
come "ce l'ho gia'".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_CEILING, Decimal

from django.db.models import Prefetch, Q

from apps.plans.models import MealPlan, PlannedMeal
from apps.recipes.models import Category, Ingredient, Recipe, RecipeIngredient, Unit

CATEGORY_ORDER = list(Category.values)

# Unita' che si convertono in una unita' base, con il fattore.
TO_BASE = {
    Unit.GRAM: (Unit.GRAM, Decimal(1)),
    Unit.KILO: (Unit.GRAM, Decimal(1000)),
    Unit.MILLILITRE: (Unit.MILLILITRE, Decimal(1)),
    Unit.LITRE: (Unit.MILLILITRE, Decimal(1000)),
    Unit.TABLESPOON: (Unit.MILLILITRE, Decimal(15)),
    Unit.TEASPOON: (Unit.MILLILITRE, Decimal(5)),
    Unit.CUP: (Unit.MILLILITRE, Decimal(240)),
}
WEIGHTS = {Unit.GRAM, Unit.MILLILITRE}


def canonical_unit(ingredient: Ingredient) -> str:
    """L'unita' in cui si somma un ingrediente: la sua di default, ridotta a g/ml/pz."""
    unit = ingredient.default_unit
    if unit in TO_BASE:
        return TO_BASE[unit][0]
    return unit


def convert(quantity: Decimal, unit: str, ingredient: Ingredient) -> tuple[Decimal, str] | None:
    """La quantita' nell'unita' canonica dell'ingrediente, o None se non si converte."""
    target = canonical_unit(ingredient)
    grams_per_piece = Decimal(ingredient.grams_per_piece) if ingredient.grams_per_piece else None
    if unit == target:
        return quantity, target
    if unit in TO_BASE:
        base, factor = TO_BASE[unit]
        value = quantity * factor
        if base == target or (base in WEIGHTS and target in WEIGHTS):
            return value, target
        if target == Unit.PIECE and grams_per_piece:
            return value / grams_per_piece, target
        return None
    if unit == Unit.PIECE and target in WEIGHTS and grams_per_piece:
        return quantity * grams_per_piece, target
    return None


def round_up(quantity: Decimal, unit: str) -> Decimal:
    """Quantita' da comprare: per eccesso e senza decimali inutili."""
    if unit in WEIGHTS:
        step = Decimal(1) if quantity < 20 else Decimal(5) if quantity < 200 else Decimal(10)
    elif unit == Unit.PIECE or unit == Unit.CLOVE:
        step = Decimal(1)
    else:
        step = Decimal("0.5")
    return (quantity / step).to_integral_value(rounding=ROUND_CEILING) * step


@dataclass
class Line:
    ingredient: Ingredient
    unit: str
    quantity: Decimal = Decimal(0)
    has_quantity: bool = False
    sources: list = field(default_factory=list)


def plan_meals(plan: MealPlan, date_from: date, date_to: date):
    lines = RecipeIngredient.objects.select_related("ingredient").order_by("position")
    recipes = Recipe.all_objects.prefetch_related(Prefetch("ingredients", queryset=lines))
    return (
        plan.meals.filter(date__gte=date_from, date__lte=date_to)
        .filter(Q(recipe__isnull=False) | ~Q(components=[]))
        .select_related("plan__owner")
        .prefetch_related(Prefetch("recipe", queryset=recipes))
        .order_by("date")
    )


def _label(meal: PlannedMeal, titles: dict[str, str]) -> str:
    """Per quale piatto serve: la ricetta approvata, la prima suggerita o il pasto."""
    from apps.profiles.models import MealSlot

    if meal.recipe is not None:
        return meal.recipe.title
    for item in meal.suggestions or []:
        if title := item.get("title") or titles.get(item.get("recipe", "")):
            return title
    return str(MealSlot(meal.slot).label)


def build_items(meals: list[PlannedMeal], extras: list[tuple] = ()) -> list[dict]:
    """Le voci della spesa per questi pasti, in ordine di reparto e di nome.

    ``extras`` sono righe gia' pronte ``(ingrediente, quantita', unita', fonte)``
    che si sommano a quelle dei pasti: i ricorrenti (ADR 0024), cosi' lo yogurt
    della colazione e quello del piano fanno una voce sola."""
    from apps.recipes.services import resolve_ingredient

    lines: dict[tuple, Line] = {}

    def add(ingredient: Ingredient, quantity, unit: str, source: dict) -> None:
        converted = None
        if quantity is not None and unit != Unit.TO_TASTE:
            converted = convert(quantity, unit, ingredient)
        key_unit = (
            converted[1]
            if converted
            else (
                canonical_unit(ingredient)
                if quantity is None or unit == Unit.TO_TASTE
                else unit
            )
        )
        line = lines.setdefault(
            (ingredient.id, key_unit), Line(ingredient=ingredient, unit=key_unit)
        )
        if converted:
            line.quantity += converted[0]
            line.has_quantity = True
        elif quantity is not None and unit != Unit.TO_TASTE:
            # Unita' che non si converte (es. scatola): si somma cosi' com'e'.
            line.quantity += quantity
            line.has_quantity = True
        if source not in line.sources:
            line.sources.append(source)

    from apps.plans.suggestions import suggested_recipe_ids

    titles = {
        str(pk): title
        for pk, title in Recipe.all_objects.filter(id__in=suggested_recipe_ids(meals)).values_list(
            "id", "title"
        )
    }
    resolved: dict[str, Ingredient] = {}
    for meal in meals:
        source = {"date": meal.date.isoformat(), "slot": meal.slot, "recipe": _label(meal, titles)}
        covered: set = set()
        for item in meal.components or []:
            name = item["name"]
            if name not in resolved:
                resolved[name] = resolve_ingredient(name, meal.plan.owner)
            ingredient = resolved[name]
            covered.add(ingredient.id)
            quantity = item.get("quantity")
            add(
                ingredient,
                None if quantity is None else Decimal(str(quantity)) * meal.servings,
                item.get("unit") or Unit.GRAM,
                source,
            )
        recipe = meal.recipe
        if recipe is None:
            continue
        factor = Decimal(meal.servings) / Decimal(recipe.servings or 1)
        for row in recipe.ingredients.all():
            # Per ingredienti: della ricetta approvata solo cio' che il piano
            # non dice gia' (la pasta la decide il piano, la cipolla la ricetta).
            if row.optional or row.ingredient_id in covered:
                continue
            quantity = None if row.quantity is None else row.quantity * factor
            add(row.ingredient, quantity, row.unit, source)
    for ingredient, quantity, unit, source in extras:
        add(ingredient, quantity, unit, source)

    items = []
    for line in lines.values():
        ingredient = line.ingredient
        items.append(
            {
                "ingredient": ingredient,
                "label": ingredient.display_name,
                "quantity": round_up(line.quantity, line.unit) if line.has_quantity else None,
                "unit": line.unit if line.has_quantity else "",
                "category": ingredient.category,
                "in_pantry": ingredient.staple,
                "sources": line.sources,
            }
        )
    items.sort(key=lambda item: (CATEGORY_ORDER.index(item["category"]), item["label"].lower()))
    return items
