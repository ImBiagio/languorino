"""Le ricette suggerite per i pasti della preparazione (ADR 0023).

Ogni pasto e' fatto di alimenti con le grammature del piano; sotto ci sono
fino a due ricette suggerite: dal ricettario (``{"recipe": id}``) o idee
(``{"title", "idea"}``). Un'idea si scrive per intero solo quando l'utente la
apre, con gli alimenti e le quantita' del pasto: cosi' la settimana si genera
in una chiamata sola invece di una per ricetta.

La ricetta diventa quella del pasto solo quando l'utente la approva
(``PlannedMeal.recipe``): da li' i suoi ingredienti in piu' (cipolla, passata)
vanno anche nella spesa. Un piatto cucinato una volta per piu' pasti (meal
prep, avanzi) si approva insieme: ``same_dish``.
"""

from __future__ import annotations

from django.db.models import QuerySet
from django.utils.translation import gettext as _

from apps.ai.client import AIError, generate
from apps.recipes.generated import save_generated
from apps.recipes.importing import LANGUAGES, ImportedRecipe
from apps.recipes.models import Recipe

from .generation import (
    DIFFICULTY_NAMES,
    MAIN_SLOTS,
    components_text,
    nutritionist_of,
    user_profile_summary,
)
from .models import PlannedMeal

PROMPT = """Scrivi in {language} la ricetta "{title}" per {servings} porzioni.
Idea: {idea}

Gli alimenti principali li decide il piano alimentare: usali tutti, con queste
quantita' a persona (moltiplicate per {servings} nella ricetta): {components}.
Puoi aggiungere solo aromi, erbe, spezie, sale, aglio, cipolla, brodo, acqua e
poca passata o verdura per il condimento: niente altre fonti di carboidrati,
proteine o grassi. Tempo totale al massimo {minutes} minuti, difficolta' al
massimo {difficulty}.{wait}

Persona:
{profile}

NON deve contenere in nessun modo: {forbidden}.{avoid}
Rispondi solo col JSON della ricetta; "inferred" vuoto; tag in italiano (1-3)."""


def same_dish(meal: PlannedMeal) -> QuerySet:
    """I pasti dello stesso piatto: stesso giorno di cottura e stessi alimenti
    (la cena e il pranzo-avanzo, i pasti di una sessione di meal prep)."""
    meals = PlannedMeal.objects.filter(plan_id=meal.plan_id, cooked_on=meal.cooked_on)
    if not meal.components:
        return meals.filter(pk=meal.pk)
    if meal.slot in MAIN_SLOTS:
        meals = meals.filter(slot__in=MAIN_SLOTS)
    else:
        meals = meals.filter(slot=meal.slot)
    return meals.filter(components=meal.components)


def write_suggestion(meal: PlannedMeal, index: int, language: str = "it") -> Recipe:
    """Scrive per intero l'idea ``index`` del pasto e la mette al suo posto."""
    from .nutritionist import avoided

    try:
        suggestion = meal.suggestions[index]
    except (IndexError, TypeError) as exc:
        raise AIError(_("Questo suggerimento non c'è più.")) from exc
    if suggestion.get("recipe"):
        found = Recipe.all_objects.filter(id=suggestion["recipe"], owner=meal.plan.owner).first()
        if found is not None:
            return found
    plan = meal.plan
    options = plan.settings
    profile, forbidden = user_profile_summary(plan.owner)
    nutritionist = nutritionist_of(plan)
    avoid = nutritionist.rules.get("avoid_foods", []) if nutritionist else []
    wait = (meal.date - meal.cooked_on).days
    prompt = PROMPT.format(
        language=LANGUAGES.get(language[:2], "italiano"),
        title=suggestion.get("title") or _("Piatto del piano"),
        servings=meal.servings,
        idea=suggestion.get("idea") or "a tua scelta, coerente col titolo",
        components=components_text(meal.components) or "a tua scelta",
        minutes=options.get("minutes", 45),
        difficulty=DIFFICULTY_NAMES.get(options.get("difficulty", "medium"), "media"),
        wait=(
            f"\nSi cucina {wait} giorni prima di mangiarla: deve reggere in frigo." if wait else ""
        ),
        profile=profile,
        forbidden=", ".join(forbidden) or "nessun divieto",
        avoid=("\nDa evitare secondo il piano: " + ", ".join(avoid) + ".") if avoid else "",
    )
    written, _model = generate(
        [prompt],
        ImportedRecipe,
        feature="meal_recipe",
        user=plan.owner,
        timeout_ms=60_000,
        temperature=0.5,
        fast=True,
    )
    recipe = save_generated(plan.owner, written, source=Recipe.Source.PLAN, servings=meal.servings)
    if recipe is not None and avoid and avoided(recipe, avoid):
        recipe.delete(hard=True)
        recipe = None
    if recipe is None:
        raise AIError(_("La ricetta scritta non andava bene per te. Riprova."))
    if meal.slot not in recipe.meal_slots:
        recipe.meal_slots = [*recipe.meal_slots, meal.slot]
        recipe.save(update_fields=["meal_slots", "updated_at"])
    # L'idea diventa la ricetta scritta in tutti i pasti dello stesso piatto.
    for other in same_dish(meal):
        other.suggestions = [
            {"recipe": str(recipe.id)} if item == suggestion else item
            for item in other.suggestions
        ]
        other.save(update_fields=["suggestions"])
    return recipe


def suggested_recipe_ids(meals) -> set[str]:
    """Gli id delle ricette suggerite in questi pasti."""
    return {
        item["recipe"]
        for meal in meals
        for item in (meal.suggestions or [])
        if isinstance(item, dict) and item.get("recipe")
    }
