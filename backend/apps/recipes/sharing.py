"""Condivisione delle ricette con un link (progettazione 4.8, ADR 0012).

Come le liste di regalino: ``/r/<token>`` e' una pagina pubblica senza login.
Chi ha un account copia la ricetta nel suo ricettario: diventa una ricetta
sua, indipendente, che ricorda da dove viene. "Nuovo link" spegne il vecchio.
"""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.db import transaction

from apps.core.methods import random_token

from .models import Recipe


def share(recipe: Recipe, *, renew: bool = False, visibility: str | None = None) -> Recipe:
    """Link acceso (o nuovo con ``renew``) e visibilita' "con il link" o
    "pubblica". Pubblica la ricetta solo se e' nel ricettario: quelle dei
    ricettari PDF e del piano non sono dell'utente da mostrare."""
    from apps.community.profiles import ensure_handle

    visibility = visibility or (
        recipe.visibility
        if recipe.visibility != Recipe.Visibility.PRIVATE
        else Recipe.Visibility.UNLISTED
    )
    if visibility == Recipe.Visibility.PUBLIC and not recipe.in_cookbook:
        raise ValueError("not in cookbook")
    if renew or not recipe.share_token:
        recipe.share_token = random_token(12)
    recipe.visibility = visibility
    recipe.save(update_fields=["share_token", "visibility", "updated_at"])
    if visibility == Recipe.Visibility.PUBLIC:
        ensure_handle(recipe.owner)
    return recipe


def unshare(recipe: Recipe) -> Recipe:
    recipe.share_token = None
    recipe.visibility = Recipe.Visibility.PRIVATE
    recipe.save(update_fields=["share_token", "visibility", "updated_at"])
    return recipe


@transaction.atomic
def copy_recipe(recipe: Recipe, user) -> Recipe:
    """La copia per ``user``: stessi campi, ingredienti, tag e immagine.

    Gli ingredienti del catalogo restano gli stessi; quelli che l'autore si e'
    creato si riconoscono di nuovo per nome tra quelli di chi copia.
    """
    from .serializers import RecipeSerializer

    data = {
        "title": recipe.title,
        "description": recipe.description,
        "servings": recipe.servings,
        "prep_minutes": recipe.prep_minutes,
        "cook_minutes": recipe.cook_minutes,
        "difficulty": recipe.difficulty,
        "steps": recipe.steps,
        "meal_slots": recipe.meal_slots,
        "keeps_days": recipe.keeps_days,
        "freezable": recipe.freezable,
        "tags": [tag.name for tag in recipe.tags.all()],
        "ingredients": [
            {
                **(
                    {"ingredient_id": str(line.ingredient_id)}
                    if line.ingredient.created_by_id is None
                    else {"name": line.ingredient.name}
                ),
                "quantity": line.quantity,
                "unit": line.unit,
                "note": line.note,
                "optional": line.optional,
            }
            for line in recipe.ingredients.select_related("ingredient").order_by("position")
        ],
    }
    serializer = RecipeSerializer(data=data, context={})
    serializer.is_valid(raise_exception=True)
    copy = serializer.save(owner=user, source=Recipe.Source.COPY, copied_from=recipe)
    if recipe.image:
        with recipe.image.open("rb") as handle:
            copy.image.save("image.webp", ContentFile(handle.read()), save=False)
        copy.image_source = recipe.image_source
        copy.save(update_fields=["image", "image_source", "updated_at"])
    return copy
