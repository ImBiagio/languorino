"""Regole del ricettario che non stanno in un solo serializer."""

from __future__ import annotations

from django.db.models import Q

from apps.profiles.allergens import detect_allergen
from apps.profiles.models import FoodPreference

from .matching import normalize, variants
from .models import Category, Ingredient, Recipe, Unit


def visible_ingredients(user):
    """Il catalogo condiviso piu' gli ingredienti aggiunti da questo utente."""
    return Ingredient.objects.filter(Q(created_by__isnull=True) | Q(created_by=user))


def match_ingredient(name: str, user) -> Ingredient | None:
    """L'ingrediente che corrisponde al nome, provando anche singolare e plurale.

    A parita' vince il catalogo: il suo ha reparto e allergeni curati.
    """
    for key in variants(name):
        found = (
            visible_ingredients(user)
            .filter(keys__contains=[key])
            .order_by("created_by_id")  # NULL (catalogo) prima
            .first()
        )
        if found:
            return found
    return None


def resolve_ingredient(name: str, user) -> Ingredient:
    """L'ingrediente per questo nome: trovato, o creato per l'utente."""
    found = match_ingredient(name, user)
    if found:
        return found
    allergen = detect_allergen(name)
    ingredient = Ingredient(
        name=" ".join(name.split()).lower(),
        category=Category.OTHER,
        allergens=[allergen] if allergen else [],
        default_unit=Unit.GRAM,
        created_by=user,
    )
    ingredient.set_keys()
    ingredient.save()
    return ingredient


def recipe_allergens(recipe: Recipe) -> list[str]:
    """Gli allergeni UE della ricetta, dagli ingredienti (opzionali compresi)."""
    found: set[str] = set()
    for line in recipe.ingredients.all():
        found.update(line.ingredient.allergens)
    return sorted(found)


class PreferenceIndex:
    """Le preferenze dell'utente pronte da confrontare con molte ricette.

    Si costruisce una volta per richiesta: per ogni preferenza gli id degli
    ingredienti che la nominano (es. "funghi" -> funghi champignon e porcini)
    e, per allergie e intolleranze, l'allergene.
    """

    def __init__(self, user):
        self.items: list[tuple[FoodPreference, set, str]] = []
        if not user or not user.is_authenticated:
            return
        preferences = FoodPreference.objects.filter(
            profile__user=user,
            kind__in=[
                FoodPreference.Kind.ALLERGY,
                FoodPreference.Kind.INTOLERANCE,
                FoodPreference.Kind.DISLIKE,
            ],
        )
        for preference in preferences:
            key = normalize(preference.label)
            # Un chip degli allergeni ha il codice come etichetta: vale l'allergene.
            ids: set = set()
            if not (preference.allergen and preference.label == preference.allergen):
                ids = set(
                    visible_ingredients(user)
                    .filter(
                        Q(keys__overlap=variants(preference.label)) | Q(search_text__icontains=key)
                    )
                    .values_list("id", flat=True)
                )
            self.items.append((preference, ids, preference.allergen))

    def warnings(self, recipe: Recipe, allergens: list[str]) -> list[dict]:
        ingredient_ids = {line.ingredient_id for line in recipe.ingredients.all()}
        out = []
        for preference, ids, allergen in self.items:
            hit = bool(ids & ingredient_ids) or (
                preference.is_restriction and allergen and allergen in allergens
            )
            if hit:
                out.append(
                    {
                        "id": preference.id,
                        "kind": preference.kind,
                        "label": preference.label,
                        "allergen": preference.allergen,
                    }
                )
        return out
