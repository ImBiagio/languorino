"""Creare e ricalcolare una lista dal piano e dai ricorrenti."""

from __future__ import annotations

from django.db import transaction

from apps.recipes.matching import normalize

from .aggregate import build_items, plan_meals
from .models import ShoppingItem, ShoppingList
from .recurring import recurring_lines


def _key(item) -> tuple:
    """Stesso ingrediente e stessa unita'; fuori catalogo, stesso nome."""
    if isinstance(item, dict):
        ingredient = item["ingredient"]
        ingredient_id, unit, label = ingredient and ingredient.id, item["unit"], item["label"]
    else:
        ingredient_id, unit, label = item.ingredient_id, item.unit, item.label
    return (ingredient_id, unit, "" if ingredient_id else normalize(label))


@transaction.atomic
def fill_from_plan(shopping_list: ShoppingList) -> None:
    """(Ri)calcola le voci dal piano e dai ricorrenti (se la lista li vuole).
    Restano com'erano le voci scritte o modificate a mano; quelle ricalcolate
    tengono spunta e "ce l'ho gia'"."""
    meals = []
    if shopping_list.plan is not None:
        meals = list(
            plan_meals(shopping_list.plan, shopping_list.date_from, shopping_list.date_to)
        )
    extras, loose = recurring_lines(shopping_list) if shopping_list.include_recurring else ([], [])
    fresh = build_items(meals, extras) + loose
    kept = shopping_list.items.filter(manual=False, edited=False)
    flags = {_key(item): (item.checked, item.in_pantry) for item in kept}
    kept.delete()
    # Una voce scritta o cambiata a mano vince su quella ricalcolata.
    touched = {_key(item) for item in shopping_list.items.all()}
    start = (
        shopping_list.items.order_by("-position").values_list("position", flat=True).first() or 0
    ) + 1
    rows = []
    for offset, item in enumerate(fresh):
        key = _key(item)
        if key in touched:
            continue  # c'e' gia' una voce cambiata a mano per questo ingrediente
        checked, in_pantry = flags.get(key, (False, item["in_pantry"]))
        rows.append(
            ShoppingItem(
                shopping_list=shopping_list,
                ingredient=item["ingredient"],
                label=item["label"],
                quantity=item["quantity"],
                unit=item["unit"],
                category=item["category"],
                in_pantry=in_pantry,
                checked=checked,
                sources=item["sources"],
                position=start + offset,
            )
        )
    ShoppingItem.objects.bulk_create(rows)
