"""Creare e ricalcolare una lista dal piano."""

from __future__ import annotations

from django.db import transaction

from .aggregate import build_items, plan_meals
from .models import ShoppingItem, ShoppingList


def _key(item) -> tuple:
    ingredient_id = item["ingredient"].id if isinstance(item, dict) else item.ingredient_id
    unit = item["unit"] if isinstance(item, dict) else item.unit
    return (ingredient_id, unit)


@transaction.atomic
def fill_from_plan(shopping_list: ShoppingList) -> None:
    """(Ri)calcola le voci dal piano. Restano com'erano le voci scritte o
    modificate a mano; quelle ricalcolate tengono spunta e "ce l'ho gia'"."""
    if shopping_list.plan is None:
        return
    meals = plan_meals(shopping_list.plan, shopping_list.date_from, shopping_list.date_to)
    fresh = build_items(list(meals))
    kept = shopping_list.items.filter(manual=False, edited=False)
    flags = {_key(item): (item.checked, item.in_pantry) for item in kept}
    kept.delete()
    touched = {_key(item) for item in shopping_list.items.all() if item.ingredient_id}
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
