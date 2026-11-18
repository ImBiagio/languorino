"""Gli alimenti di colazione e merenda restano fuori da pranzo e cena (foods.py)."""

from __future__ import annotations

from apps.plans.foods import (
    food_matches,
    is_side_food,
    plan_side_foods,
    prepared_rules,
    prepared_weekly,
    side_only_foods,
    updated_diet_foods,
)
from apps.plans.nutritionist import rules_prompt

# Come il piano vero che ha messo lo yogurt a pranzo e a cena (2026-11-18).
RULES = {
    "meals": [
        {"slot": "breakfast", "options": ["200 g Yogurt intero + 30 g Cereali da colazione"]},
        {
            "slot": "afternoon_snack",
            "options": [
                "125 g / 1 Vasetto Yogurt intero + 150 g / 1 Frutto medio Frutta fresca",
                "30 g Crackers integrali + 30 g Parmigiano",
            ],
        },
        {
            "slot": "lunch",
            "options": [
                "90 g Cereali a chicco (riso, farro, orzo) + 60 g Legumi secchi + 200 g Verdura"
            ],
        },
        {"slot": "dinner", "options": ["300 g Pesce bianco + 60 g Pane integrale + 200 g Verdura"]},
    ],
    "substitutions": [
        {
            "group": "Fonti proteiche",
            "equivalents": ["60 g Legumi secchi", "50 g Parmigiano", "80 g Feta"],
            "note": "a pranzo",
        },
        {
            "group": "Yogurt intero",
            "equivalents": ["125 g Yogurt intero", "70 g Yogurt greco intero"],
            "note": "a merenda",
        },
    ],
    "weekly": [
        {"food": "Salmone / tonno", "times": 2},
        {"food": "Formaggi", "times": 1},
        {"food": "Yogurt", "times": 3},
    ],
    "free_foods": [],
    "avoid_foods": [],
    "notes": "",
}


def test_alimenti_da_merenda():
    side = side_only_foods(RULES)
    assert {"yogurt", "frutta", "crackers", "cereali da colazione"} <= set(side)
    # Il parmigiano e' anche nelle sostituzioni del pranzo: a pranzo ci puo' stare.
    assert is_side_food("yogurt greco", side)
    assert is_side_food("frutta fresca", side)
    assert not is_side_food("parmigiano", side)
    assert not is_side_food("cereali a chicco", side)
    assert not is_side_food("pasta integrale", side)
    assert not is_side_food("frutti di mare", side)
    assert not is_side_food("fiocchi di latte", side)
    assert plan_side_foods(RULES)[:2] == ["yogurt", "cereali da colazione"]


def test_frequenze_dei_pasti_preparati():
    lunch_dinner = [item["food"] for item in prepared_weekly(RULES, ["lunch", "dinner"])]
    assert lunch_dinner == ["Salmone / tonno", "Formaggi"]
    # Se si prepara anche la merenda, lo yogurt conta.
    with_snack = prepared_weekly(RULES, ["afternoon_snack", "lunch", "dinner"])
    assert [item["food"] for item in with_snack][-1] == "Yogurt"
    assert prepared_weekly(RULES, None) == RULES["weekly"]


def test_regole_ridotte_ai_pasti_preparati():
    rules = prepared_rules(RULES, ["lunch", "dinner"])
    assert [meal["slot"] for meal in rules["meals"]] == ["lunch", "dinner"]
    assert [group["group"] for group in rules["substitutions"]] == ["Fonti proteiche"]
    prompt = rules_prompt(RULES, True, slots=["lunch", "dinner"])
    assert "Yogurt 3 volte" not in prompt and "Vasetto" not in prompt
    assert "A pranzo e a cena MAI gli alimenti di colazione" in prompt
    assert "yogurt, cereali da colazione" in prompt
    # Senza pasti scelti (chat, vecchi usi) le regole restano tutte.
    assert "Yogurt 3 volte" in rules_prompt(RULES, True)


def test_alimenti_delle_frequenze():
    assert food_matches("ceci lessati", "legumi")
    assert food_matches("lenticchie rosse", "Legumi secchi o in scatola")
    assert food_matches("tonno al naturale", "Salmone / tonno")
    assert food_matches("uova", "Uova (4 uova totali)")
    assert food_matches("petto di pollo", "carne bianca")
    assert food_matches("parmigiano", "Formaggi")
    assert not food_matches("pollo", "carne rossa")
    assert not food_matches("pasta integrale", "legumi")


def test_frequenze_dopo_un_cambio():
    before = [{"name": "pasta"}, {"name": "ceci lessati"}, {"name": "sgombro"}]
    after = [{"name": "pasta"}, {"name": "pollo"}, {"name": "sgombro"}]
    weekly = [{"food": "legumi"}, {"food": "carne bianca"}, {"food": "pesce strano"}]
    foods = ["legumi", "pesce strano"]
    # Via i legumi coi ceci, dentro la carne bianca col pollo; il pesce che il
    # codice non riconosce resta com'era, perche' lo sgombro c'e' ancora.
    assert updated_diet_foods(foods, before, after, weekly) == ["pesce strano", "carne bianca"]


DINNER = {
    "meals": [
        {
            "slot": "dinner",
            "options": [
                "300 g Pesce bianco: merluzzo, sogliola, orata... + 60 g Pane integrale o "
                "multicereali + 200 g Verdura"
            ],
        },
        {"slot": "lunch", "options": ["90 g Cereali a chicco (riso, farro, orzo..) + 60 g Legumi"]},
    ],
    "substitutions": [
        {
            "group": "Fonti proteiche",
            "note": "a cena",
            "equivalents": [
                "300 g Pesce bianco: merluzzo, sogliola, orata...",
                "170 g Tonno",
                "250 g Carne bianca: petto di pollo o tacchino",
                "80 g Legumi secchi",
            ],
        },
        {"group": "Pane", "note": "a cena", "equivalents": ["60 g Pane integrale", "220 g Patate"]},
    ],
    "weekly": [],
}


def _names(component, slot):
    from apps.plans.nutritionist import equivalents_for

    return [(e["name"], e["quantity"]) for e in equivalents_for(component, DINNER, slot)]


def test_equivalenti_dalle_voci_con_elenco():
    from apps.plans.nutritionist import food_members, siblings

    assert food_members("Carne bianca: petto di pollo o tacchino, coniglio") == (
        "Carne bianca",
        ["petto di pollo", "tacchino", "coniglio"],
    )
    # Prima gli altri pesci della voce, stessa grammatura; poi le sostituzioni.
    assert _names({"name": "merluzzo", "quantity": 300, "unit": "g"}, "dinner") == [
        ("sogliola", 300),
        ("orata", 300),
        ("tonno", 170),
        ("petto di pollo", 250),
        ("tacchino", 250),
        ("legumi secchi", 80),
    ]
    # Il tonno c'e' col suo nome: non e' "pesce bianco".
    assert _names({"name": "tonno", "quantity": 170, "unit": "g"}, "dinner")[0] == (
        "merluzzo",
        300,
    )
    assert _names({"name": "pane integrale", "quantity": 60, "unit": "g"}, "dinner") == [
        ("patate", 220)
    ]
    # I ceci non sono nominati: valgono come "Legumi secchi".
    assert ("tonno", 213) in _names({"name": "ceci secchi", "quantity": 100, "unit": "g"}, "dinner")
    assert [n for n, _q in _names({"name": "riso", "quantity": 90, "unit": "g"}, "lunch")] == [
        "farro",
        "orzo",
    ]
    assert siblings("merluzzo", DINNER, "dinner") == ["sogliola", "orata"]
    # Il gruppo "a cena" non vale a pranzo.
    assert _names({"name": "merluzzo", "quantity": 300, "unit": "g"}, "lunch") == []
