"""Intervista a voce in tempo reale (ADR 0014): token, istruzioni, pulizia."""

from __future__ import annotations

import httpx
import pytest
from django.test import override_settings

from apps.core import cornhub
from apps.profiles.live import clean_call, session_config
from apps.profiles.models import FoodPreference, Profile

pytestmark = pytest.mark.django_db


def test_istruzioni_e_strumenti(user):
    profile = Profile.objects.create(user=user, first_name="Giulia", sport_sessions_per_week=2)
    FoodPreference.objects.create(profile=profile, kind="allergy", label="noci")
    config = session_config(user, "it")
    text = config["system_instruction"]
    assert text.startswith("REGOLA PRINCIPALE")
    assert "sport a settimana: 2" in text and "allergia: noci" in text
    assert "Giulia" not in text and user.email not in text
    names = [f["name"] for f in config["tools"][0]["function_declarations"]]
    assert names == ["segna_preferenza", "segna_profilo", "fine_intervista"]
    assert config["speech_config"] == {"language_code": "it-IT"}


@pytest.mark.parametrize(
    ("name", "args", "expected"),
    [
        (
            "segna_profilo",
            {"campo": "sport_sessions_per_week", "valore": "3 volte"},
            {"sport_sessions_per_week": 3},
        ),
        ("segna_profilo", {"campo": "height_cm", "valore": "170"}, {"height_cm": 170}),
        ("segna_profilo", {"campo": "height_cm", "valore": "900"}, {}),
        (
            "segna_profilo",
            {"campo": "goals", "valore": "more_protein, save_time"},
            {"goals": ["more_protein", "save_time"]},
        ),
        ("segna_profilo", {"campo": "goals", "valore": "diventare ricco"}, {}),
        (
            "segna_profilo",
            {"campo": "followed_by_nutritionist", "valore": "sì"},
            {"followed_by_nutritionist": True},
        ),
        ("segna_profilo", {"campo": "email", "valore": "x@y.it"}, {}),
        ("altro", {"campo": "height_cm", "valore": "170"}, {}),
    ],
)
def test_pulizia_dei_dati(user, name, args, expected):
    assert clean_call(user, name, args) == {"updates": expected, "preferences": []}


def test_pulizia_delle_preferenze(user):
    result = clean_call(user, "segna_preferenza", {"tipo": "allergy", "alimento": " gamberi "})
    assert result["preferences"] == [
        {"kind": "allergy", "label": "gamberi", "allergen": "crustaceans"}
    ]
    bad = clean_call(user, "segna_preferenza", {"tipo": "odio", "alimento": "funghi"})
    assert bad == {"updates": {}, "preferences": []}


def test_endpoint_della_proposta(user, api):
    response = api(user).post(
        "/api/profile/interview/proposal",
        {"name": "segna_profilo", "args": {"campo": "household_size", "valore": "due persone 2"}},
        format="json",
    )
    assert response.data == {"updates": {"household_size": 2}, "preferences": []}
    assert api(user).post("/api/profile/interview/proposal", [], format="json").data == {
        "updates": {},
        "preferences": [],
    }


def test_token_della_sessione(user, api, monkeypatch):
    """Il token lo crea cornhub (ADR 0021) con la configurazione decisa qui."""
    seen = []

    def post(url, json=None, headers=None, timeout=None):
        seen.append((url, json))
        payload = {"token": "auth_tokens/finto", "model": "live-model", "billed_to": "user"}
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(cornhub.httpx, "post", post)
    response = api(user).post("/api/profile/interview/live")
    assert response.data == {"token": "auth_tokens/finto", "model": "live-model"}
    url, body = seen[0]
    assert url.endswith("/internal/ai/live-token") and body["feature"] == "interview_live"
    assert body["config"]["system_instruction"].startswith("REGOLA PRINCIPALE")


def test_limite_di_cornhub(user, api, monkeypatch):
    def post(url, json=None, headers=None, timeout=None):
        payload = {"code": "needs_key", "detail": "Usa la tua chiave API.",
                   "account_url": "https://cornhub.test/account/ai/"}
        return httpx.Response(402, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(cornhub.httpx, "post", post)
    response = api(user).post("/api/profile/interview/live")
    assert response.status_code == 502
    assert response.data["code"] == "needs_key"
    assert response.data["account_url"].endswith("/account/ai/")


@override_settings(CORNHUB_APP_TOKEN="")
def test_senza_chiave(user, api):
    assert api(user).post("/api/profile/interview/live").status_code == 503
