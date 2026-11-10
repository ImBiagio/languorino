"""Ricette scritte dall'LLM (piano, "cosa cucino oggi"): salvate fuori dal
ricettario come bozza e ricontrollate sugli ingredienti veri.

E' il passo di sicurezza comune (progettazione, principio 2): l'LLM riceve i
divieti nel prompt, ma e' il codice a buttare via una ricetta che tocca
un'allergia o un'intolleranza del profilo.
"""

from __future__ import annotations

import logging

from apps.profiles.models import FoodPreference

from .importing import ImportedRecipe, to_draft
from .models import Recipe
from .services import PreferenceIndex, recipe_allergens

logger = logging.getLogger(__name__)


def save_generated(
    user, written: ImportedRecipe, *, source: str, servings: int | None = None
) -> Recipe | None:
    """Salva la ricetta scritta dall'LLM; None se non e' valida o tocca un divieto."""
    from .serializers import RecipeSerializer

    draft = to_draft(written, user)
    if servings:
        draft["servings"] = servings
    serializer = RecipeSerializer(data=draft, context={})
    if not serializer.is_valid():
        logger.warning("Ricetta scritta dall'LLM scartata: %s", serializer.errors)
        return None
    recipe = serializer.save(
        owner=user, source=source, in_cookbook=False, status=Recipe.Status.DRAFT
    )
    warnings = PreferenceIndex(user).warnings(recipe, recipe_allergens(recipe))
    if any(warning["kind"] != FoodPreference.Kind.DISLIKE for warning in warnings):
        logger.warning("Ricetta %r scartata: tocca %s", recipe.title, warnings)
        recipe.delete(hard=True)
        return None
    return recipe
