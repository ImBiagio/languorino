"""Ricorrenti della spesa (ADR 0024): suggerimenti dal piano alimentare,
configurazione, somma nella lista."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.plans.models import MealPlan, NutritionistPlan, PlannedMeal
from apps.shopping.recurring import parse_food

pytestmark = pytest.mark.django_db
SHOP = "/api/shopping"
RECURRING = f"{SHOP}/recurring"
START = date.today()


@pytest.fixture
def prepared(user):
    diet = NutritionistPlan.objects.create(
        owner=user,
        title="Piano",
        status=NutritionistPlan.Status.CONFIRMED,
        rules={
            "meals": [
                {
                    "slot": "breakfast",
                    "options": [
                        "200 g yogurt greco + 30 g fiocchi d'avena",
                        "1 tazza di latte + 3 fette biscottate + caffè",
                    ],
                },
                {"slot": "afternoon_snack", "options": ["1 frutto"]},
                {"slot": "lunch", "options": ["80 g pasta + verdure a volontà"]},
            ]
        },
    )
    # La preparazione fa solo pranzi e cene: la colazione e' tolta.
    plan = MealPlan.objects.create(
        owner=user,
        start_date=START,
        days=7,
        status="active",
        settings={"slots": ["lunch", "dinner"], "nutritionist_plan": str(diet.id)},
    )
    PlannedMeal.objects.create(
        plan=plan,
        date=START,
        slot="lunch",
        cooked_on=START,
        components=[{"name": "yogurt greco", "quantity": 100, "unit": "g"}],
    )
    return plan


def test_leggere_gli_alimenti_delle_opzioni():
    assert parse_food("200 g yogurt greco") == {
        "label": "yogurt greco",
        "quantity": Decimal(200),
        "unit": "g",
    }
    assert parse_food("1 tazza di latte") == {"label": "latte", "quantity": 1, "unit": "cup"}
    assert parse_food("3 fette biscottate")["unit"] == "pz"
    # La misura in pezzi dopo la barra non e' il nome.
    assert parse_food("150 g / 1 Frutto medio Frutta fresca (media)")["label"] == "frutta fresca"
    assert parse_food("125 g / 1 Vasetto Yogurt intero")["label"] == "yogurt intero"
    assert parse_food("150 g / 1 frutto")["label"] == "frutto"
    assert parse_food("20 g Crema 100% frutta secca")["label"] == "crema 100% frutta secca"
    assert parse_food("Frutta fresca a volontà (mela, pera)") == {
        "label": "frutta fresca",
        "quantity": None,
        "unit": "",
    }


def test_suggerimenti_solo_dei_pasti_non_preparati(user, api, prepared):
    data = api(user).get(f"{RECURRING}/suggestions").data
    items = {item["label"]: item for item in data["items"]}
    assert data["plan"]["title"] == "Piano"
    # Il pranzo e' nella preparazione: niente pasta fra i ricorrenti.
    assert "pasta" not in items
    assert {item["slot"] for item in data["items"]} == {"breakfast", "afternoon_snack"}
    # Due colazioni diverse si dividono la settimana.
    assert items["yogurt greco"]["times_per_week"] == 4
    assert Decimal(items["yogurt greco"]["quantity"]) == 200
    assert items["caffè"]["quantity"] is None
    assert items["frutto"]["times_per_week"] == 7
    assert not items["frutto"]["saved"]


def test_configurare_e_spesa_con_i_ricorrenti(user, api, prepared):
    client = api(user)
    rows = [
        {"label": "yogurt greco", "quantity": "200", "unit": "g", "times_per_week": 4,
         "slot": "breakfast"},
        {"label": "Detersivo piatti"},
        {"label": "latte", "quantity": "1", "unit": "cup", "times_per_week": 7, "active": False},
    ]
    created = client.post(RECURRING, rows, format="json")
    assert created.status_code == 201, created.data
    assert [item["label"] for item in client.get(RECURRING).data] == [
        "yogurt greco",
        "Detersivo piatti",
        "latte",
    ]
    # Gia' salvato: il suggerimento lo dice.
    suggested = client.get(f"{RECURRING}/suggestions").data["items"]
    assert next(item for item in suggested if item["label"] == "yogurt greco")["saved"]

    body = {
        "plan": str(prepared.id),
        "date_from": START.isoformat(),
        "date_to": (START + timedelta(6)).isoformat(),
        "include_recurring": True,
    }
    data = client.post(SHOP, body, format="json").data
    assert data["include_recurring"] is True
    labels = {item["label"]: item for item in data["items"]}
    yogurt = next(item for item in data["items"] if "yogurt" in item["label"])
    # 100 g del pranzo + 200 g x 4 volte: una voce sola.
    assert Decimal(yogurt["quantity"]) == 900
    assert any(source.get("recurring") for source in yogurt["sources"])
    assert labels["Detersivo piatti"]["category"] == "other"
    # Spento: non va in spesa.
    assert not any(item["label"] == "latte" for item in data["items"])

    # Spegnere i ricorrenti sulla lista li toglie; riaccenderli li rimette.
    url = f"{SHOP}/{data['id']}"
    off = client.patch(url, {"include_recurring": False}, format="json").data
    assert "Detersivo piatti" not in {item["label"] for item in off["items"]}
    yogurt = next(item for item in off["items"] if "yogurt" in item["label"])
    assert Decimal(yogurt["quantity"]) == 100
    on = client.patch(url, {"include_recurring": True}, format="json").data
    assert "Detersivo piatti" in {item["label"] for item in on["items"]}


def test_lista_senza_piano_coi_ricorrenti(user, api):
    client = api(user)
    item = client.post(
        RECURRING, {"label": "caffè", "quantity": "1", "times_per_week": 2}, format="json"
    ).data
    assert item["unit"] == "pz"
    data = client.post(SHOP, {"include_recurring": True}, format="json").data
    assert [row["label"] for row in data["items"]] == ["caffè"]
    # Si ricalcola anche senza piano: cambia la quantita' del ricorrente.
    client.patch(f"{RECURRING}/{item['id']}", {"times_per_week": 4}, format="json")
    again = client.post(f"{SHOP}/{data['id']}/regenerate").data
    assert Decimal(again["items"][0]["quantity"]) == 4


def test_ricorrenti_di_altri(user, other_user, api):
    item = api(user).post(RECURRING, {"label": "pane"}, format="json").data
    assert api(other_user).get(RECURRING).data == []
    url = f"{RECURRING}/{item['id']}"
    assert api(other_user).patch(url, {"label": "x"}, format="json").status_code == 404
    assert api(other_user).delete(url).status_code == 404
    assert api(user).delete(url).status_code == 204
