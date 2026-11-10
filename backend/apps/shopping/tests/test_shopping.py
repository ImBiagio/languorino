"""Lista della spesa: somme, unita', basilari, ricalcolo, API."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.plans.models import MealPlan, PlannedMeal
from apps.recipes.models import Ingredient
from apps.recipes.serializers import RecipeSerializer
from apps.shopping.aggregate import build_items, convert, plan_meals, round_up
from apps.shopping.models import ShoppingItem, ShoppingList

pytestmark = pytest.mark.django_db
SHOP = "/api/shopping"
START = date.today()


def _recipe(user, title, servings, lines):
    data = {
        "title": title,
        "servings": servings,
        "ingredients": [
            {"name": name, "quantity": qty, "unit": unit, "optional": optional}
            for name, qty, unit, *rest in lines
            for optional in [bool(rest and rest[0])]
        ],
    }
    serializer = RecipeSerializer(data=data, context={})
    serializer.is_valid(raise_exception=True)
    return serializer.save(owner=user)


@pytest.fixture
def plan(user):
    carbonara = _recipe(
        user,
        "Carbonara",
        2,
        [
            ("spaghetti", "180", "g"),
            ("uova", "2", "pz"),
            ("pecorino", "50", "g"),
            ("pepe nero", None, "to_taste"),
            ("guanciale", "0.08", "kg"),
        ],
    )
    frittata = _recipe(
        user,
        "Frittata di zucchine",
        1,
        [
            ("uova", "120", "g"),
            ("zucchine", "150", "g"),
            ("olio evo", "1", "tbsp"),
            ("ceci in scatola", "1", "can"),
            ("parmigiano", "20", "g", True),
        ],
    )
    plan = MealPlan.objects.create(
        owner=user, start_date=START, days=7, status="active", settings={"servings": 2}
    )
    rows = [
        (START, "lunch", carbonara, 4),
        (START, "dinner", frittata, 2),
        (START + timedelta(1), "dinner", frittata, 2),
        (START + timedelta(5), "dinner", carbonara, 2),
    ]
    for day, slot, recipe, servings in rows:
        PlannedMeal.objects.create(
            plan=plan, date=day, slot=slot, recipe=recipe, servings=servings, cooked_on=day
        )
    PlannedMeal.objects.create(
        plan=plan, date=START + timedelta(2), slot="lunch", cooked_on=START + timedelta(2)
    )  # pasto libero
    return plan


def _items(plan, days=3):
    meals = plan_meals(plan, START, START + timedelta(days - 1))
    return {(item["label"], item["unit"]): item for item in build_items(list(meals))}


def test_conversioni():
    eggs = Ingredient.objects.get(name="uova")
    oil = Ingredient.objects.get(name="olio extravergine d'oliva")
    courgette = Ingredient.objects.get(name="zucchina")
    assert convert(Decimal(2), "pz", eggs) == (Decimal(2), "pz")
    assert convert(Decimal(120), "g", eggs) == (Decimal(2), "pz")
    assert convert(Decimal(1), "tbsp", oil) == (Decimal(15), "ml")
    assert convert(Decimal(300), "g", courgette) == (Decimal("1.5"), "pz")
    assert convert(Decimal(1), "can", courgette) is None


def test_arrotondamenti():
    assert round_up(Decimal("13.3"), "g") == 14
    assert round_up(Decimal("181"), "g") == 185
    assert round_up(Decimal("1.2"), "pz") == 2
    assert round_up(Decimal("1.2"), "can") == Decimal("1.5")


def test_somma_e_porzioni(plan):
    items = _items(plan)
    # Carbonara x2 (4 porzioni su 2): 360 g di pasta, 4 uova; due frittate da 2
    # porzioni: 4 x 120 g di uova = 480 g = 8 uova da 60 g. Totale 12 uova.
    assert items[("pasta", "g")]["quantity"] == 360
    assert items[("uova", "pz")]["quantity"] == 12
    assert items[("guanciale", "g")]["quantity"] == 160
    # 150 g x 4 = 600 g di zucchine = 3 zucchine da 200 g.
    assert items[("zucchina", "pz")]["quantity"] == 3
    # 1 cucchiaio x 4 = 60 ml di olio, basilare: "ce l'ho gia'".
    oil = items[("olio extravergine d'oliva", "ml")]
    assert oil["quantity"] == 60 and oil["in_pantry"] is True
    # La scatola non si converte: resta a se', 4 scatole.
    assert items[("ceci in scatola", "can")]["quantity"] == 4
    # Q.b.: c'e', senza quantita'.
    assert items[("pepe nero", "")]["quantity"] is None
    # Facoltativo: non si compra.
    assert ("parmigiano reggiano", "g") not in items
    # Da dove viene: i pasti.
    assert {source["recipe"] for source in items[("uova", "pz")]["sources"]} == {
        "Carbonara",
        "Frittata di zucchine",
    }


def test_intervallo_di_giorni(plan):
    assert _items(plan, days=1)[("uova", "pz")]["quantity"] == 8
    assert _items(plan, days=7)[("pasta", "g")]["quantity"] == 540


def test_ordine_per_reparto(plan):
    categories = [
        item["category"]
        for item in build_items(list(plan_meals(plan, START, START + timedelta(6))))
    ]
    order = [
        "produce",
        "meat",
        "fish",
        "dairy",
        "bakery",
        "pantry",
        "spices",
        "frozen",
        "drinks",
        "other",
    ]
    assert categories == sorted(categories, key=order.index)


# --- API -------------------------------------------------------------------------------


def _create(api, user, plan, days=3, **extra):
    body = {
        "plan": str(plan.id),
        "date_from": START.isoformat(),
        "date_to": (START + timedelta(days - 1)).isoformat(),
        **extra,
    }
    response = api(user).post(SHOP, body, format="json")
    assert response.status_code == 201, response.data
    return response.data


def test_lista_dal_piano(user, api, plan):
    data = _create(api, user, plan)
    assert data["title"].startswith("Spesa dal")
    assert data["title"] == data["title"].lower().replace("spesa", "Spesa", 1)
    assert any(item["label"] == "uova" and item["quantity"] == "12.00" for item in data["items"])
    # Le voci "ce l'ho gia'" non contano tra quelle da comprare.
    pantry = sum(1 for item in data["items"] if item["in_pantry"])
    assert pantry >= 2
    assert data["item_count"] == len(data["items"]) - pantry
    assert data["checked_count"] == 0


def test_intervallo_fuori_dal_piano(user, api, plan):
    body = {
        "plan": str(plan.id),
        "date_from": (START - timedelta(10)).isoformat(),
        "date_to": (START + timedelta(30)).isoformat(),
    }
    data = api(user).post(SHOP, body, format="json").data
    # Ristretto ai giorni del piano.
    assert (data["date_from"], data["date_to"]) == (
        START.isoformat(),
        (START + timedelta(6)).isoformat(),
    )
    bad = {
        "plan": str(plan.id),
        "date_from": (START + timedelta(5)).isoformat(),
        "date_to": (START + timedelta(1)).isoformat(),
    }
    assert api(user).post(SHOP, bad, format="json").status_code == 400


def test_lista_vuota_e_voce_a_mano(user, api):
    data = api(user).post(SHOP, {}, format="json").data
    assert (data["title"], data["items"]) == ("Spesa", [])
    url = f"{SHOP}/{data['id']}/items"
    item = api(user).post(url, {"label": " Detersivo piatti "}, format="json").data
    assert (item["label"], item["category"], item["manual"]) == ("Detersivo piatti", "other", True)
    # Un nome del catalogo prende il suo reparto.
    milk = api(user).post(url, {"label": "latte", "quantity": "1", "unit": "l"}, format="json").data
    assert milk["category"] == "dairy"
    assert api(user).post(url, {"label": "  "}, format="json").status_code == 400


def test_spuntare_e_modificare(user, api, plan):
    data = _create(api, user, plan)
    eggs = next(item for item in data["items"] if item["label"] == "uova")
    url = f"{SHOP}/{data['id']}/items/{eggs['id']}"
    checked = api(user).patch(url, {"checked": True}, format="json").data
    assert (checked["checked"], checked["edited"]) == (True, False)
    assert api(user).get(f"{SHOP}/{data['id']}").data["checked_count"] == 1
    edited = api(user).patch(url, {"quantity": "10"}, format="json").data
    assert edited["edited"] is True


def test_ricalcolo_rispetta_le_mani(user, api, plan):
    data = _create(api, user, plan)
    list_id = data["id"]
    by_label = {item["label"]: item for item in data["items"]}
    # Spunto la pasta, correggo le uova a mano, aggiungo il pane.
    api(user).patch(
        f"{SHOP}/{list_id}/items/{by_label['pasta']['id']}", {"checked": True}, format="json"
    )
    api(user).patch(
        f"{SHOP}/{list_id}/items/{by_label['uova']['id']}", {"quantity": "12"}, format="json"
    )
    api(user).post(f"{SHOP}/{list_id}/items", {"label": "pane"}, format="json")
    # Il piano cambia: un pasto in piu' di carbonara il primo giorno.
    meal = PlannedMeal.objects.get(plan=plan, date=START, slot="dinner")
    meal.recipe = PlannedMeal.objects.get(plan=plan, date=START, slot="lunch").recipe
    meal.save()
    regenerated = api(user).post(f"{SHOP}/{list_id}/regenerate").data
    items = {item["label"]: item for item in regenerated["items"]}
    assert items["pasta"]["checked"] is True  # la spunta resta
    assert items["pasta"]["quantity"] == "540.00"  # ricalcolata
    assert items["uova"]["quantity"] == "12.00"  # modificata a mano: non si tocca
    assert sum(1 for item in regenerated["items"] if item["label"] == "uova") == 1
    assert "pane" in items


def test_rinominare_e_eliminare(user, api, plan):
    data = _create(api, user, plan)
    url = f"{SHOP}/{data['id']}"
    assert (
        api(user)
        .patch(url, {"title": "Spesa Esselunga", "status": "done"}, format="json")
        .data["status"]
        == "done"
    )
    assert [item["id"] for item in api(user).get(f"{SHOP}?status=done").data] == [data["id"]]
    assert api(user).delete(url).status_code == 204
    assert not ShoppingList.all_objects.exists()
    assert not ShoppingItem.objects.exists()


def test_liste_degli_altri(user, other_user, api, plan):
    data = _create(api, user, plan)
    item = data["items"][0]
    assert api(other_user).get(SHOP).data == []
    assert api(other_user).get(f"{SHOP}/{data['id']}").status_code == 404
    assert (
        api(other_user)
        .patch(f"{SHOP}/{data['id']}/items/{item['id']}", {"checked": True}, format="json")
        .status_code
        == 404
    )
    assert (
        api(other_user)
        .post(f"{SHOP}/{data['id']}/items", {"label": "x"}, format="json")
        .status_code
        == 404
    )
    other = {"plan": str(plan.id)}
    assert api(other_user).post(SHOP, other, format="json").status_code == 400
