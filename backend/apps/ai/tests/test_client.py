"""Adattatore verso cornhub: richiesta, risposta e traduzione degli errori.

Nessuna richiesta vera: ``httpx.post`` del client di cornhub e' finto.
"""

from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from apps.ai import client as ai
from apps.core import cornhub


class Answer(BaseModel):
    text: str


@pytest.fixture
def fake_post(monkeypatch):
    state = {"status": 200, "payload": {"data": {"text": "ciao"}, "model": "m1"}, "seen": []}

    def post(url, json=None, headers=None, timeout=None):
        state["seen"].append((url, json, timeout))
        return httpx.Response(
            state["status"], json=state["payload"], request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(cornhub.httpx, "post", post)
    return state


def test_generate_manda_parti_e_feature(fake_post, user):
    user.cornhub_sub = "2b6f5a8e-0000-4000-8000-000000000001"
    answer, model = ai.generate(
        ["leggi", ai.file_part(b"pdf", "application/pdf")],
        Answer,
        feature="import_recipes",
        user=user,
        fast=True,
        media_resolution="high",
        timeout_ms=180_000,
    )
    assert answer == Answer(text="ciao") and model == "m1"
    url, body, timeout = fake_post["seen"][0]
    assert url.endswith("/internal/ai/generate") and timeout == 180
    assert body["feature"] == "import_recipes" and body["fast"] is True
    assert body["media_resolution"] == "high" and body["user"].endswith("0001")
    assert body["parts"][0] == {"text": "leggi"}
    assert body["parts"][1]["mime"] == "application/pdf"


@pytest.mark.parametrize(
    ("status", "code", "kind"),
    [
        (503, "overloaded", ai.AIOverloaded),
        (402, "needs_key", ai.AIBudgetExceeded),
        (402, "limit", ai.AIBudgetExceeded),
        (402, "house_empty", ai.AIBudgetExceeded),
        (400, "bad_request", ai.AIError),
    ],
)
def test_errori_tradotti(fake_post, status, code, kind):
    fake_post["status"] = status
    fake_post["payload"] = {
        "code": code, "detail": "Messaggio", "account_url": "https://cornhub.test/account/ai/"
    }
    with pytest.raises(kind) as exc:
        ai.generate(["x"], Answer, feature="ask")
    assert str(exc.value) == "Messaggio" and exc.value.code == code
    assert exc.value.account_url.endswith("/account/ai/")
    # Solo un sovraccarico e' da riprovare; gli altri fermano il lavoro.
    assert isinstance(exc.value, ai.AIOverloaded) == (code == "overloaded")


def test_immagine(fake_post):
    fake_post["payload"] = {"image": "aW1n", "mime": "image/png", "model": "img"}
    data, mime, model = ai.generate_image("un piatto", feature="recipe_image")
    assert (data, mime, model) == (b"img", "image/png", "img")
    assert fake_post["seen"][0][1]["feature"] == "recipe_image"


def test_spenta_senza_token(settings):
    settings.CORNHUB_APP_TOKEN = ""
    assert not ai.is_enabled()
    with pytest.raises(ai.AIError):
        ai.generate(["x"], Answer, feature="ask")
