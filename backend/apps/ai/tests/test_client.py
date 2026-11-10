"""Client Gemini: riserve, modelli giu', errori, registro delle chiamate.

Nessuna richiesta vera: ``genai.Client`` e' finto.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.test import override_settings
from google.genai import errors
from pydantic import BaseModel

from apps.ai import client as ai
from apps.ai.models import AiCall

pytestmark = pytest.mark.django_db


class Answer(BaseModel):
    text: str


def _response(text='{"text": "ciao"}'):
    return SimpleNamespace(
        parsed=None,
        text=text,
        usage_metadata=SimpleNamespace(prompt_token_count=120, candidates_token_count=30),
    )


@pytest.fixture
def fake_gemini(monkeypatch):
    """``behaviour[model]``: una risposta o un'eccezione da alzare."""
    behaviour: dict = {}
    calls: list[str] = []

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            calls.append(model)
            outcome = behaviour.get(model, _response())
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

    monkeypatch.setattr("google.genai.Client", FakeClient)
    monkeypatch.setattr(ai.time, "sleep", lambda seconds: None)
    cache.clear()
    return behaviour, calls


def _ask(user=None):
    return ai.generate(lambda types: ["ciao"], Answer, feature="test", user=user)


@override_settings(GEMINI_API_KEY="")
def test_senza_chiave():
    with pytest.raises(ai.AIError, match="GEMINI_API_KEY"):
        _ask()


@override_settings(GEMINI_API_KEY="k", GEMINI_MODEL="main", GEMINI_FALLBACK_MODELS=["spare"])
def test_risposta_e_registro(fake_gemini, user):
    answer, model = _ask(user)
    assert answer.text == "ciao"
    assert model == "main"
    call = AiCall.objects.get()
    assert (call.feature, call.model, call.ok, call.user) == ("test", "main", True, user)
    assert (call.input_tokens, call.output_tokens) == (120, 30)


@override_settings(GEMINI_API_KEY="k", GEMINI_MODEL="main", GEMINI_FALLBACK_MODELS=["spare"])
def test_modello_sovraccarico_passa_alla_riserva(fake_gemini):
    behaviour, calls = fake_gemini
    behaviour["main"] = errors.ServerError(503, {"error": {"message": "overloaded"}})
    _, model = _ask()
    assert model == "spare"
    assert calls == ["main", "spare"]
    # Il principale resta giu': la chiamata dopo parte dalla riserva.
    calls.clear()
    _ask()
    assert calls == ["spare"]
    assert AiCall.objects.filter(ok=False).count() == 1


@override_settings(GEMINI_API_KEY="k", GEMINI_MODEL="main", GEMINI_FALLBACK_MODELS=["spare"])
def test_tutti_giu_dopo_i_tentativi(fake_gemini):
    behaviour, calls = fake_gemini
    behaviour["main"] = errors.ServerError(503, {"error": {"message": "overloaded"}})
    behaviour["spare"] = errors.ClientError(429, {"error": {"message": "quota"}})
    with pytest.raises(ai.AIError, match="sovraccarico"):
        _ask()
    # Tre giri (due pause) su due modelli.
    assert len(calls) == 6


@override_settings(GEMINI_API_KEY="k", GEMINI_MODEL="main", GEMINI_FALLBACK_MODELS=["spare"])
def test_chiave_rifiutata_si_ferma_subito(fake_gemini):
    behaviour, calls = fake_gemini
    behaviour["main"] = errors.ClientError(403, {"error": {"message": "denied"}})
    with pytest.raises(ai.AIError, match="rifiutato la chiave"):
        _ask()
    assert calls == ["main"]


@override_settings(GEMINI_API_KEY="k", GEMINI_MODEL="main", GEMINI_FALLBACK_MODELS=[])
def test_risposta_non_valida(fake_gemini):
    behaviour, _calls = fake_gemini
    behaviour["main"] = _response("non e' json")
    with pytest.raises(ai.AIError, match="formato"):
        _ask()
