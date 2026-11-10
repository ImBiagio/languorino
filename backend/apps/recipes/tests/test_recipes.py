"""Ricettario: catalogo, ricette, tag, filtri, allergeni e avvisi dal profilo."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.profiles.models import FoodPreference, Profile
from apps.recipes.catalog import CATALOG
from apps.recipes.matching import variants
from apps.recipes.models import Ingredient, Recipe, Tag
from apps.recipes.services import match_ingredient

pytestmark = pytest.mark.django_db
RECIPES = "/api/recipes"

CARBONARA = {
    "title": "  Carbonara ",
    "description": "Quella vera, senza panna.",
    "servings": 2,
    "prep_minutes": 10,
    "cook_minutes": 12,
    "difficulty": "medium",
    "meal_slots": ["dinner", "lunch", "dinner"],
    "steps": ["Rosola il guanciale.", "", "  Manteca con uova e pecorino. "],
    "tags": ["pasta", "Veloce", "veloce", " "],
    "keeps_days": 1,
    "ingredients": [
        {"name": "Spaghetti", "quantity": "180", "unit": "g"},
        {"name": "guanciale", "quantity": "80", "unit": "g"},
        {"name": "Uova", "quantity": "2", "unit": "pz", "note": "solo tuorli"},
        {"name": "pecorino", "quantity": "50", "unit": "g"},
        {"name": "pepe nero", "quantity": "5", "unit": "to_taste"},
    ],
}


def _create(api, user, payload=None):
    response = api(user).post(RECIPES, payload or CARBONARA, format="json")
    assert response.status_code == 201, response.data
    return response.data


# --- catalogo e riconoscimento ---


def test_catalogo_caricato_dalla_migrazione():
    assert Ingredient.objects.filter(created_by__isnull=True).count() == len(CATALOG)
    eggs = Ingredient.objects.get(name="uova")
    assert eggs.allergens == ["eggs"]
    assert eggs.grams_per_piece == 60


def test_ricaricare_il_catalogo_non_duplica():
    call_command("load_catalog")
    assert Ingredient.objects.filter(created_by__isnull=True).count() == len(CATALOG)


def test_varianti_singolare_plurale():
    assert "peperone rosso" in variants("Peperoni  Rossi")
    assert variants("Zucchìne")[0] == "zucchine"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Zucchine", "zucchina"),
        ("carote", "carota"),
        ("spaghetti", "pasta"),
        ("olio evo", "olio extravergine d'oliva"),
        ("gamberetti", "gamberi"),
        ("uovo", "uova"),
        ("Peperoni rossi", "peperone"),
        ("caffe", "caffè"),
        ("parmigiano grattugiato", "parmigiano reggiano"),
        ("Cipolla tritata finemente", None),
        ("cipolla rossa tritata", "cipolla rossa"),
        ("macinato misto", "macinato misto"),
    ],
)
def test_ingrediente_riconosciuto(user, name, expected):
    found = match_ingredient(name, user)
    # "finemente" non e' una parola di preparazione: meglio nessuna corrispondenza.
    assert (found.name if found else None) == expected


def test_ricerca_ingredienti(user, api):
    assert api().get("/api/ingredients?q=zu").status_code == 401
    names = [item["name"] for item in api(user).get("/api/ingredients?q=zucc").data]
    # Prima chi inizia con la ricerca, i nomi corti in testa.
    assert names[0] == "zucca"
    assert "zucchina" in names[:3]
    assert api(user).get("/api/ingredients?q=z").data == []


def test_ricerca_in_inglese(user, api):
    data = api(user).get("/api/ingredients?q=chickpea", HTTP_ACCEPT_LANGUAGE="en").data
    assert data[0]["name"] in {"dried chickpeas", "canned chickpeas"}


# --- creare e leggere ---


def test_crea_ricetta(user, api):
    data = _create(api, user)
    assert data["title"] == "Carbonara"
    assert data["total_minutes"] == 22
    assert data["meal_slots"] == ["lunch", "dinner"]
    assert data["steps"] == ["Rosola il guanciale.", "Manteca con uova e pecorino."]
    assert data["tags"] == ["pasta", "Veloce"]
    names = [line["ingredient"]["name"] for line in data["ingredients"]]
    assert names == ["pasta", "guanciale", "uova", "pecorino", "pepe nero"]
    # q.b. non ha quantita'.
    assert data["ingredients"][4]["quantity"] is None
    assert data["ingredients"][2]["note"] == "solo tuorli"
    assert data["allergens"] == ["eggs", "gluten", "milk"]
    assert data["main_category"] == "pantry"
    assert data["source"] == "manual"
    assert data["status"] == "confirmed"


def test_ingrediente_nuovo_creato_per_l_utente(user, other_user, api):
    payload = {"title": "Zuppa", "ingredients": [{"name": "Topinambur", "quantity": "300"}]}
    data = _create(api, user, payload)
    ingredient = data["ingredients"][0]["ingredient"]
    assert ingredient["name"] == "topinambur"
    assert ingredient["custom"] is True
    # Lo vede solo chi l'ha aggiunto.
    assert api(user).get("/api/ingredients?q=topin").data
    assert api(other_user).get("/api/ingredients?q=topin").data == []
    # Lo stesso nome la volta dopo riusa lo stesso ingrediente.
    again = _create(api, user, payload)
    assert again["ingredients"][0]["ingredient"]["id"] == ingredient["id"]


def test_ingrediente_nuovo_con_allergene_riconosciuto(user, api):
    payload = {"title": "Torta", "ingredients": [{"name": "farina di nocciole"}]}
    data = _create(api, user, payload)
    assert data["allergens"] == ["nuts"]


def test_ingrediente_di_un_altro_utente_rifiutato(user, other_user, api):
    mine = _create(api, user, {"title": "A", "ingredients": [{"name": "Topinambur"}]})
    foreign_id = mine["ingredients"][0]["ingredient"]["id"]
    response = api(other_user).post(
        RECIPES, {"title": "B", "ingredients": [{"ingredient_id": foreign_id}]}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   "},
        {"title": "X", "servings": 0},
        {"title": "X", "servings": 60},
        {"title": "X", "prep_minutes": 2000},
        {"title": "X", "difficulty": "impossibile"},
        {"title": "X", "meal_slots": ["brunch"]},
        {"title": "X", "keeps_days": 30},
        {"title": "X", "ingredients": [{"quantity": "10"}]},
        {"title": "X", "ingredients": [{"name": "sale", "quantity": "-1"}]},
        {"title": "X", "ingredients": [{"name": "sale", "unit": "barile"}]},
        {"title": "X", "tags": [f"t{n}" for n in range(20)]},
    ],
)
def test_ricette_rifiutate(user, api, payload):
    assert api(user).post(RECIPES, payload, format="json").status_code == 400


def test_modifica_sostituisce_ingredienti_e_tag(user, api):
    recipe = _create(api, user)
    response = api(user).patch(
        f"{RECIPES}/{recipe['id']}",
        {"ingredients": [{"name": "riso", "quantity": "160"}], "tags": ["riso"], "servings": 4},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert [line["ingredient"]["name"] for line in response.data["ingredients"]] == ["riso"]
    assert response.data["tags"] == ["riso"]
    assert response.data["servings"] == 4
    # Un PATCH che non nomina ingredienti e tag non li tocca.
    other = api(user).patch(f"{RECIPES}/{recipe['id']}", {"title": "Risotto"}, format="json")
    assert other.data["tags"] == ["riso"]
    assert len(other.data["ingredients"]) == 1


def test_eliminare_nasconde_la_ricetta(user, api):
    recipe = _create(api, user)
    assert api(user).delete(f"{RECIPES}/{recipe['id']}").status_code == 204
    assert api(user).get(f"{RECIPES}/{recipe['id']}").status_code == 404
    assert api(user).get(RECIPES).data["results"] == []
    assert Recipe.all_objects.filter(id=recipe["id"]).exists()


def test_ricette_degli_altri_invisibili(user, other_user, api):
    recipe = _create(api, user)
    assert api(other_user).get(RECIPES).data["results"] == []
    assert api(other_user).get(f"{RECIPES}/{recipe['id']}").status_code == 404
    assert api(other_user).patch(f"{RECIPES}/{recipe['id']}", {"title": "Mia"}).status_code == 404
    assert api(other_user).delete(f"{RECIPES}/{recipe['id']}").status_code == 404


# --- elenco e filtri ---


@pytest.fixture
def cookbook(user, api):
    _create(api, user)
    _create(
        api,
        user,
        {
            "title": "Insalata di ceci",
            "prep_minutes": 10,
            "meal_slots": ["lunch"],
            "tags": ["veloce", "legumi"],
            "ingredients": [{"name": "ceci in scatola", "quantity": "240"}],
        },
    )
    _create(
        api,
        user,
        {
            "title": "Lasagne",
            "prep_minutes": 60,
            "cook_minutes": 40,
            "difficulty": "hard",
            "meal_slots": ["lunch"],
            "freezable": True,
            "tags": ["forno"],
            "ingredients": [{"name": "lasagne"}, {"name": "macinato"}],
        },
    )


def _titles(api, user, query=""):
    return sorted(item["title"] for item in api(user).get(f"{RECIPES}{query}").data["results"])


@pytest.mark.usefixtures("cookbook")
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ["Carbonara", "Insalata di ceci", "Lasagne"]),
        ("?q=ceci", ["Insalata di ceci"]),
        ("?q=guanciale", ["Carbonara"]),
        ("?q=Forno", ["Lasagne"]),
        ("?tag=veloce", ["Carbonara", "Insalata di ceci"]),
        ("?tag=veloce&tag=legumi", ["Insalata di ceci"]),
        ("?slot=dinner", ["Carbonara"]),
        ("?max_minutes=30", ["Carbonara", "Insalata di ceci"]),
        ("?difficulty=hard", ["Lasagne"]),
    ],
)
def test_filtri(user, api, query, expected):
    assert _titles(api, user, query) == expected


@pytest.mark.usefixtures("cookbook")
def test_ricette_fuori_dal_ricettario(user, api):
    Recipe.objects.filter(title="Lasagne").update(in_cookbook=False)
    assert "Lasagne" not in _titles(api, user)
    assert _titles(api, user, "?in_cookbook=false") == ["Lasagne"]


@pytest.mark.usefixtures("cookbook")
def test_tag_con_conteggio(user, other_user, api):
    tags = {tag["name"]: tag["recipe_count"] for tag in api(user).get("/api/tags").data}
    assert tags == {"forno": 1, "legumi": 1, "pasta": 1, "Veloce": 2}
    assert api(other_user).get("/api/tags").data == []


@pytest.mark.usefixtures("cookbook")
def test_togliere_un_tag(user, other_user, api):
    tag = Tag.objects.get(owner=user, name="forno")
    assert api(other_user).delete(f"/api/tags/{tag.id}").status_code == 404
    assert api(user).delete(f"/api/tags/{tag.id}").status_code == 204
    lasagne = Recipe.objects.get(title="Lasagne")
    assert list(lasagne.tags.all()) == []


# --- avvisi dal profilo ---


def _prefer(user, kind, label, allergen=""):
    profile, _ = Profile.objects.get_or_create(user=user)
    return FoodPreference.objects.create(profile=profile, kind=kind, label=label, allergen=allergen)


def test_avviso_per_allergene_del_profilo(user, api):
    _prefer(user, "allergy", "eggs", "eggs")
    data = _create(api, user)
    assert [(w["kind"], w["allergen"]) for w in data["warnings"]] == [("allergy", "eggs")]
    listed = api(user).get(RECIPES).data["results"][0]
    assert listed["warnings"][0]["allergen"] == "eggs"


def test_avviso_per_intolleranza_al_lattosio(user, api):
    _prefer(user, "intolerance", "Lattosio", "milk")
    data = _create(api, user)
    assert [w["label"] for w in data["warnings"]] == ["Lattosio"]


def test_avviso_per_cosa_non_piace(user, api):
    _prefer(user, "dislike", "Guanciale")
    _prefer(user, "dislike", "Funghi")
    data = _create(api, user)
    assert [w["label"] for w in data["warnings"]] == ["Guanciale"]


def test_i_gusti_non_contano_per_allergene(user, api):
    # "Non mi piace il pecorino" non deve accendere tutto il latte.
    _prefer(user, "dislike", "Formaggi")
    data = _create(api, user, {"title": "Pane e burro", "ingredients": [{"name": "burro"}]})
    assert data["warnings"] == []


def test_nessun_avviso_senza_profilo(user, api):
    assert _create(api, user)["warnings"] == []
