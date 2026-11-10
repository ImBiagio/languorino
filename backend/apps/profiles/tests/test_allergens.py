"""Riconoscimento degli allergeni dalle etichette scritte a mano."""

from __future__ import annotations

import pytest

from apps.profiles.allergens import detect_allergen


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Glutine", "gluten"),
        ("celiachia", "gluten"),
        ("Frumento", "gluten"),
        ("gamberetti", "crustaceans"),
        ("Gamberi", "crustaceans"),
        ("uova", "eggs"),
        ("tonno", "fish"),
        ("arachidi", "peanuts"),
        ("noccioline", "peanuts"),
        ("nocciole", "nuts"),
        ("Pistacchi", "nuts"),
        ("lattosio", "milk"),
        ("Latticini", "milk"),
        ("sedano", "celery"),
        ("semi di sesamo", "sesame"),
        ("solfiti", "sulphites"),
        ("cozze", "molluscs"),
        ("polpo", "molluscs"),
        ("Lactose", "milk"),
        ("peanuts", "peanuts"),
        ("latte di mandorla", "nuts"),
        ("latte di soia", "soy"),
        # I chip del frontend salvano il codice come etichetta.
        ("nuts", "nuts"),
        ("crustaceans", "crustaceans"),
    ],
)
def test_allergene_riconosciuto(label, expected):
    assert detect_allergen(label) == expected


@pytest.mark.parametrize(
    "label",
    [
        "",
        "fragole",
        "polpette",
        "noce moscata",
        "latte di cocco",
        "granoturco",
        "grano saraceno",
        # Due allergeni insieme: meglio nessuno che quello sbagliato.
        "pesce e gamberi",
    ],
)
def test_nessun_allergene_se_non_e_chiaro(label):
    assert detect_allergen(label) == ""
