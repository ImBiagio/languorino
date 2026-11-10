"""Profilo alimentare e preferenze: API, validazioni, isolamento fra utenti."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.conftest import UserFactory
from apps.profiles.models import FoodPreference, Profile

pytestmark = pytest.mark.django_db
URL = "/api/profile"
PREFS = "/api/profile/preferences"


def test_serve_il_login(api):
    assert api().get(URL).status_code == 401
    assert api().get(PREFS).status_code == 401


def test_profilo_nasce_vuoto_alla_prima_richiesta(user, api):
    data = api(user).get(URL).data
    assert data["onboarding_completed"] is False
    assert data["meal_slots"] == ["breakfast", "lunch", "dinner"]
    assert data["household_size"] == 1
    assert data["followed_by_nutritionist"] is None
    assert data["preferences"] == []
    assert Profile.objects.filter(user=user).count() == 1
    # Una seconda richiesta non ne crea un altro.
    api(user).get(URL)
    assert Profile.objects.filter(user=user).count() == 1


def test_modifica_e_eta(user, api):
    birth = date.today().replace(year=date.today().year - 30) - timedelta(days=1)
    response = api(user).patch(
        URL,
        {
            "birth_date": birth.isoformat(),
            "sex": "f",
            "height_cm": 168,
            "weight_kg": "61.5",
            "goals": ["more_protein", "eat_better", "more_protein"],
            "activity_level": "moderate",
            "sport_sessions_per_week": 3,
            "followed_by_nutritionist": False,
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["age"] == 30
    assert response.data["weight_kg"] == "61.5"
    assert response.data["goals"] == ["more_protein", "eat_better"]
    assert response.data["followed_by_nutritionist"] is False


def test_compleanno_domani_non_conta_ancora(user, api):
    tomorrow = date.today() + timedelta(days=1)
    try:
        birth = tomorrow.replace(year=tomorrow.year - 40)
    except ValueError:  # 29 febbraio
        birth = (tomorrow + timedelta(days=1)).replace(year=tomorrow.year - 40)
    data = api(user).patch(URL, {"birth_date": birth.isoformat()}, format="json").data
    assert data["age"] == 39


@pytest.mark.parametrize(
    "payload",
    [
        {"birth_date": (date.today() + timedelta(days=1)).isoformat()},
        {"birth_date": "1850-01-01"},
        {"height_cm": 30},
        {"height_cm": 300},
        {"weight_kg": "5"},
        {"sport_sessions_per_week": 30},
        {"household_size": 0},
        {"goals": ["diventare ricco"]},
        {"sex": "x"},
        {"meal_slots": []},
        {"meal_slots": ["brunch"]},
        {"conditions": [f"patologia {n}" for n in range(25)]},
    ],
)
def test_valori_rifiutati(user, api, payload):
    assert api(user).patch(URL, payload, format="json").status_code == 400


def test_pasti_in_ordine_di_giornata(user, api):
    data = (
        api(user)
        .patch(
            URL, {"meal_slots": ["dinner", "breakfast", "dinner", "afternoon_snack"]}, format="json"
        )
        .data
    )
    assert data["meal_slots"] == ["breakfast", "afternoon_snack", "dinner"]


def test_patologie_ripulite(user, api):
    data = (
        api(user)
        .patch(
            URL, {"conditions": ["  Reflusso ", "reflusso", "", "Diabete  tipo 2"]}, format="json"
        )
        .data
    )
    assert data["conditions"] == ["Reflusso", "Diabete tipo 2"]


def test_il_nome_sostituisce_quello_di_default(api):
    user = UserFactory(email="mario.rossi@languorino.test", display_name="")
    assert user.display_name == "mario.rossi"
    api(user).patch(URL, {"first_name": " Mario ", "last_name": "Rossi"}, format="json")
    user.refresh_from_db()
    assert user.display_name == "Mario"


def test_il_nome_scelto_a_mano_resta(user, api):
    user.display_name = "Marietto"
    user.save()
    api(user).patch(URL, {"first_name": "Mario"}, format="json")
    user.refresh_from_db()
    assert user.display_name == "Marietto"


def test_fine_del_wizard(user, api):
    response = api(user).post(f"{URL}/complete")
    assert response.status_code == 200
    assert response.data["onboarding_completed"] is True
    first = Profile.objects.get(user=user).onboarding_completed_at
    # Una seconda volta non sposta la data.
    api(user).post(f"{URL}/complete")
    assert Profile.objects.get(user=user).onboarding_completed_at == first


def test_ogni_utente_vede_il_suo_profilo(user, other_user, api):
    api(user).patch(URL, {"first_name": "Anna"}, format="json")
    assert api(other_user).get(URL).data["first_name"] == ""


# --- preferenze ---


def test_allergia_scritta_a_mano_collegata_all_allergene(user, api):
    response = api(user).post(PREFS, {"kind": "allergy", "label": "gamberetti"}, format="json")
    assert response.status_code == 201
    assert response.data["allergen"] == "crustaceans"
    assert api(user).get(URL).data["preferences"][0]["label"] == "gamberetti"


def test_allergene_scelto_dalla_lista(user, api):
    response = api(user).post(
        PREFS, {"kind": "allergy", "label": "Frutta a guscio", "allergen": "nuts"}, format="json"
    )
    assert response.data["allergen"] == "nuts"


def test_intolleranza_al_lattosio(user, api):
    response = api(user).post(PREFS, {"kind": "intolerance", "label": "Lattosio"}, format="json")
    assert response.data["allergen"] == "milk"


def test_i_gusti_non_hanno_allergene(user, api):
    response = api(user).post(
        PREFS, {"kind": "dislike", "label": "gamberi", "allergen": "crustaceans"}, format="json"
    )
    assert response.status_code == 201
    assert response.data["allergen"] == ""


def test_la_stessa_voce_due_volte_rimanda_quella_che_ce(user, api):
    first = api(user).post(PREFS, {"kind": "like", "label": "Zucca"}, format="json")
    again = api(user).post(PREFS, {"kind": "like", "label": "  zucca "}, format="json")
    assert first.status_code == 201
    assert again.status_code == 200
    assert again.data["id"] == first.data["id"]
    # Lo stesso cibo puo' stare in due elenchi diversi.
    other = api(user).post(PREFS, {"kind": "dislike", "label": "zucca"}, format="json")
    assert other.status_code == 201


@pytest.mark.parametrize(
    "payload",
    [{"kind": "like", "label": "   "}, {"kind": "love", "label": "pizza"}, {"label": "pizza"}],
)
def test_preferenze_rifiutate(user, api, payload):
    assert api(user).post(PREFS, payload, format="json").status_code == 400


def test_togliere_una_preferenza(user, api):
    created = api(user).post(PREFS, {"kind": "like", "label": "Pizza"}, format="json").data
    assert api(user).delete(f"{PREFS}/{created['id']}").status_code == 204
    assert not FoodPreference.all_objects.filter(id=created["id"]).exists()
    # Tolta si puo' rimettere.
    again = api(user).post(PREFS, {"kind": "like", "label": "Pizza"}, format="json")
    assert again.status_code == 201


def test_preferenze_degli_altri_intoccabili(user, other_user, api):
    created = api(user).post(PREFS, {"kind": "like", "label": "Pizza"}, format="json").data
    assert api(other_user).delete(f"{PREFS}/{created['id']}").status_code == 404
    assert api(other_user).get(PREFS).data == []
    assert FoodPreference.objects.filter(id=created["id"]).exists()
