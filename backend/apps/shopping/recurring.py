"""I ricorrenti della spesa (ADR 0024).

Cose che si comprano sempre, anche se la preparazione non le mette nei giorni:
la colazione tolta dal piano, le merende, il caffe', il detersivo. L'utente le
sceglie in una lista sua (``RecurringItem``); la spesa le aggiunge per i giorni
della lista, sommate alle voci del piano.

I suggerimenti vengono dal piano alimentare: le opzioni dei pasti che la
preparazione non prepara (di solito colazione e merende), lette alimento per
alimento con le grammature ("200 g yogurt greco + 30 g avena"). Tutto codice,
niente LLM: le opzioni hanno gia' le grammature scritte.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from apps.plans.foods import SIDE_SLOTS
from apps.plans.models import MealPlan, NutritionistPlan, current_plan
from apps.plans.nutritionist import food_members, parse_equivalent
from apps.profiles.models import MEAL_SLOT_ORDER, MealSlot
from apps.recipes.matching import normalize
from apps.recipes.models import Category, Unit

from .aggregate import round_up
from .models import RecurringItem, ShoppingList

FAMILY_UNIT = {"g": Unit.GRAM, "ml": Unit.MILLILITRE, "pz": Unit.PIECE}
# "1 tazza di latte", "2 cucchiai di miele": la misura davanti all'alimento.
MEASURES = [
    (re.compile(r"^(tazz[ae]|bicchier[ei])\s+(di\s+|d')", re.I), Unit.CUP),
    (re.compile(r"^(cucchiai[on]?)\s+(di\s+|d')", re.I), Unit.TABLESPOON),
    (re.compile(r"^(cucchiain[oi])\s+(di\s+|d')", re.I), Unit.TEASPOON),
    (re.compile(r"^(fett[ae])\s+(di\s+|d')", re.I), Unit.SLICE),
    (re.compile(r"^(vasett[oi])\s+(di\s+|d')", re.I), Unit.PIECE),
]
# "150 g / 1 Frutto medio Frutta fresca", "125 g / 1 Vasetto Yogurt": la
# misura in pezzi dopo la barra non e' il nome dell'alimento.
ALT_MEASURE = re.compile(
    r"^/\s*[\d.,½¼¾]+\s*(?:(?:frutt[oi]|vasett[oi]|pacchett[oi]|cucchiai[on]?|cucchiain[oi]"
    r"|fett[ae]|tazz[ae]|bicchier[ei]|porzion[ei]|confezion[ei]|scatolett[ae]|panin[oi])"
    r"(?:\s+(?:medi[oa]|piccol[oa]|grand[ei]))?\b\s*)?",
    re.I,
)
# Parole che dicono "quanto", non "cosa": "frutta a volonta'" e' frutta.
FREE_WORDS = re.compile(r"\b(a\s+volont[aà]'?|q\.?\s?b\.?|a\s+piacere|libera?)\b", re.I)
WEEK = 7


def _split_option(option: str) -> list[str]:
    """Gli alimenti di un'opzione: "200 g yogurt + 30 g avena, 1 frutto"."""
    parts = re.split(r"\s+\+\s+|\s*,\s*(?=\d)|\s+e\s+(?=\d)", option)
    return [" ".join(part.split()).strip(" .;-") for part in parts if part.strip(" .;-")]


def parse_food(text: str) -> dict | None:
    """``{label, quantity, unit}`` a persona per un alimento di un'opzione."""
    parsed = parse_equivalent(text)
    if parsed:
        quantity, family, name = parsed
        unit = FAMILY_UNIT[family]
        if family == "pz":
            for pattern, measure in MEASURES:
                if match := pattern.match(name):
                    name, unit = name[match.end() :], measure
                    break
    else:
        quantity, unit, name = None, "", text
    if match := ALT_MEASURE.match(name):
        rest = name[match.end() :].strip()
        # "150 g / 1 frutto": senza altro nome l'alimento e' la misura stessa.
        name = rest or re.sub(r"^/\s*[\d.,½¼¾]+\s*", "", name)
    name = FREE_WORDS.sub(" ", re.sub(r"\(.*?\)", " ", name))
    head, _members = food_members(name)
    head = " ".join(head.split()).strip(" .,;-")
    if not head or len(head) > 60 or re.match(r"[\d/]", head):
        return None
    return {
        "label": head[:1].lower() + head[1:],
        "quantity": quantity,
        "unit": unit if quantity is not None else "",
    }


def diet_for(user) -> tuple[NutritionistPlan | None, set[str]]:
    """Il piano alimentare da cui suggerire e i pasti che la preparazione
    prepara gia' (quelli non servono: sono nella spesa dal piano)."""
    from apps.plans.generation import nutritionist_of

    plan: MealPlan | None = current_plan(user)
    diet = nutritionist_of(plan) if plan else None
    if diet is None:
        diet = (
            NutritionistPlan.objects.filter(owner=user, status=NutritionistPlan.Status.CONFIRMED)
            .order_by("-created_at")
            .first()
        )
    prepared = set(plan.settings.get("slots", [])) if plan else set(MEAL_SLOT_ORDER) - set(
        SIDE_SLOTS
    )
    return diet, prepared


def suggestions(user) -> dict:
    """I ricorrenti da proporre: per ogni pasto non preparato, gli alimenti
    delle sue opzioni. La quantita' e' per tutta la casa; le volte a
    settimana dividono i 7 giorni fra le opzioni (3 colazioni diverse: ognuna
    2 volte), e un alimento che sta in piu' opzioni le somma."""
    diet, prepared = diet_for(user)
    if diet is None:
        return {"plan": None, "items": []}
    profile = getattr(user, "food_profile", None)
    household = Decimal(getattr(profile, "household_size", 1) or 1)
    # Il ricorrente gia' salvato per ogni nome: la pagina lo toglie da qui.
    saved = {
        normalize(label): item_id
        for item_id, label in user.recurring_items.order_by("-id").values_list("id", "label")
    }
    items: list[dict] = []
    for meal in diet.rules.get("meals", []):
        slot, options = meal.get("slot"), meal.get("options") or []
        if slot in prepared or not options:
            continue
        share = Decimal(WEEK) / len(options)
        found: dict[tuple, dict] = {}
        for option in options:
            for part in _split_option(option):
                food = parse_food(part)
                if food is None:
                    continue
                key = (normalize(food["label"]), food["unit"])
                if key in found:
                    found[key]["times"] += share
                    continue
                found[key] = {**food, "times": share, "option": option}
        for (name, _unit), food in found.items():
            quantity = food["quantity"]
            items.append(
                {
                    "key": f"{slot}:{name}:{food['unit']}",
                    "label": food["label"],
                    "quantity": None if quantity is None else str(quantity * household),
                    "unit": food["unit"],
                    "times_per_week": max(1, min(WEEK, round(food["times"]))),
                    "slot": slot,
                    "option": food["option"],
                    "saved": name in saved,
                    "saved_id": saved.get(name),
                }
            )
    items.sort(key=lambda item: MEAL_SLOT_ORDER.index(item["slot"]))
    return {"plan": {"id": str(diet.id), "title": diet.title}, "items": items}


def _days(shopping_list: ShoppingList) -> int:
    start: date | None = shopping_list.date_from
    end: date | None = shopping_list.date_to
    return (end - start).days + 1 if start and end else WEEK


def recurring_lines(shopping_list: ShoppingList) -> tuple[list[tuple], list[dict]]:
    """I ricorrenti attivi per i giorni della lista.

    Restituisce le righe da sommare al piano ``(ingrediente, quantita', unita',
    fonte)`` e, a parte, le voci gia' pronte di quello che non e' nel catalogo
    (detersivo): non si somma con niente."""
    days = Decimal(_days(shopping_list))
    extras: list[tuple] = []
    loose: list[dict] = []
    items = RecurringItem.objects.filter(owner=shopping_list.owner, active=True).select_related(
        "ingredient"
    )
    for item in items:
        quantity = None
        if item.quantity is not None:
            quantity = item.quantity * item.times_per_week * days / WEEK
        source = {
            "date": None,
            "slot": item.slot,
            "recipe": str(MealSlot(item.slot).label) if item.slot in MEAL_SLOT_ORDER else "",
            "recurring": True,
        }
        if item.ingredient is not None:
            extras.append((item.ingredient, quantity, item.unit or Unit.PIECE, source))
            continue
        has_quantity = quantity is not None and bool(item.unit)
        loose.append(
            {
                "ingredient": None,
                "label": item.label,
                "quantity": round_up(quantity, item.unit) if has_quantity else None,
                "unit": item.unit if has_quantity else "",
                "category": Category.OTHER,
                "in_pantry": False,
                "sources": [source],
            }
        )
    return extras, loose
