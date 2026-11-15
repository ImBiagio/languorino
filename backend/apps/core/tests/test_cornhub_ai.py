"""Client AI di cornhub: forma delle richieste ed errori."""

from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from apps.core import cornhub


class Out(BaseModel):
    total: float


def _fake(monkeypatch, status, payload, seen):
    def post(url, json=None, headers=None, timeout=None):
        seen.append((url, json, headers))
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(cornhub.httpx, "post", post)


def test_generate_sends_schema_and_validates(monkeypatch, user):
    seen = []
    user.cornhub_sub = "2b6f5a8e-0000-4000-8000-000000000001"
    _fake(monkeypatch, 200, {"data": {"total": 12.5}, "billed_to": "house", "pannocchie": 1}, seen)
    result = cornhub.generate("demo", ["ciao", cornhub.file_part(b"x", "image/png")], Out,
                              user=user, fast=True)
    assert result.data == Out(total=12.5) and result.billed_to == "house"
    url, body, headers = seen[0]
    assert url == "http://cornhub-backend:8000/internal/ai/generate"
    assert headers["Authorization"] == "Bearer token-test"
    assert headers["X-Cornhub-App"] == "languorino"
    assert body["user"].endswith("0001") and body["fast"] is True
    assert body["json_schema"]["properties"]["total"]["type"] == "number"
    assert body["parts"][0] == {"text": "ciao"} and body["parts"][1]["mime"] == "image/png"


def test_needs_key_error_carries_link(monkeypatch):
    _fake(monkeypatch, 402, {"code": "needs_key", "detail": "Serve la tua chiave",
                             "account_url": "https://cornhub.test/account/ai/"}, [])
    with pytest.raises(cornhub.AIError) as exc:
        cornhub.generate("demo", ["x"])
    assert exc.value.code == "needs_key" and exc.value.account_url.endswith("/account/ai/")


def test_overloaded_is_retryable(monkeypatch):
    _fake(monkeypatch, 503, {"code": "overloaded", "detail": "giu'"}, [])
    with pytest.raises(cornhub.AIOverloaded) as exc:
        cornhub.generate("demo", ["x"])
    assert exc.value.retry_later
