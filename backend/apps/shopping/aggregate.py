"""Dalla lista dei pasti alla lista della spesa (progettazione 4.7, ADR 0008).

Per ogni pasto del piano nell'intervallo: le quantita' della ricetta scalate
alle porzioni del pasto, sommate per ingrediente dopo averle portate alla
stessa unita' (quella di default dell'ingrediente nel catalogo):

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

from django.db.models import Prefetch

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
        plan.meals.filter(date__gte=date_from, date__lte=date_to, recipe__isnull=False)
        .prefetch_related(Prefetch("recipe", queryset=recipes))
        .order_by("date")
    )


def build_items(meals: list[PlannedMeal]) -> list[dict]:
    """Le voci della spesa per questi pasti, in ordine di reparto e di nome."""
    lines: dict[tuple, Line] = {}
    for meal in meals:
        recipe = meal.recipe
        factor = Decimal(meal.servings) / Decimal(recipe.servings or 1)
        source = {"date": meal.date.isoformat(), "slot": meal.slot, "recipe": recipe.title}
        for row in recipe.ingredients.all():
            if row.optional:
                continue
            ingredient = row.ingredient
            converted = None
            if row.quantity is not None and row.unit != Unit.TO_TASTE:
                converted = convert(row.quantity * factor, row.unit, ingredient)
            unit = (
                converted[1]
                if converted
                else (
                    canonical_unit(ingredient)
                    if row.quantity is None or row.unit == Unit.TO_TASTE
                    else row.unit
                )
            )
            line = lines.setdefault((ingredient.id, unit), Line(ingredient=ingredient, unit=unit))
            if converted:
                line.quantity += converted[0]
                line.has_quantity = True
            elif row.quantity is not None and row.unit != Unit.TO_TASTE:
                # Unita' che non si converte (es. scatola): si somma cosi' com'e'.
                line.quantity += row.quantity * factor
                line.has_quantity = True
            if source not in line.sources:
                line.sources.append(source)

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
