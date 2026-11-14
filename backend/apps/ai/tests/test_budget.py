"""Tetto giornaliero delle chiamate a Gemini: per utente, globale, sessioni a voce."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from pydantic import BaseModel

from apps.ai import client as ai
from apps.ai.budget import LIVE_FEATURE, calls_today, exhausted
from apps.ai.models import AiCall

pytestmark = pytest.mark.django_db

LIMITS = {"AI_CALLS_PER_DAY": 3, "AI_CALLS_PER_DAY_GLOBAL": 5, "AI_LIVE_SESSIONS_PER_DAY": 1}


class Answer(BaseModel):
    text: str


def _calls(user, count, *, feature="test", ok=True):
    for _ in range(count):
        AiCall.objects.create(user=user, feature=feature, model="m", ok=ok)


@pytest.fixture
def gemini_calls(monkeypatch):
    """Un Gemini finto che conta le chiamate arrivate fino a lui."""
    calls: list[str] = []

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            calls.append(model)
            return SimpleNamespace(parsed=None, text='{"text": "ciao"}', usage_metadata=None)

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

    monkeypatch.setattr("google.genai.Client", FakeClient)
    cache.clear()
    return calls


@override_settings(**LIMITS)
def test_sotto_il_tetto_niente_messaggio(user):
    _calls(user, 2)
    assert calls_today(user) == 2
    assert exhausted(user) == ""


@override_settings(**LIMITS)
def test_tetto_per_utente(user, other_user):
    _calls(user, 3)
    assert "3 al giorno" in exhausted(user)
    # Il tetto e' di ciascuno: l'altro continua.
    assert exhausted(other_user) == ""


@override_settings(**LIMITS)
def test_tetto_globale(user, other_user):
    _calls(user, 2)
    _calls(other_user, 2)
    _calls(None, 1)
    assert "tutta l'app" in exhausted(user)
    # Vale anche per le chiamate senza utente (attivita' di sistema).
    assert "tutta l'app" in exhausted(None)


@override_settings(**LIMITS)
def test_non_contano_le_chiamate_fallite_ne_quelle_di_ieri(user):
    _calls(user, 5, ok=False)
    _calls(user, 5)
    AiCall.objects.filter(ok=True).update(created_at=timezone.now() - timedelta(days=1, hours=1))
    assert calls_today(user) == 0
    assert exhausted(user) == ""


@override_settings(AI_CALLS_PER_DAY=0, AI_CALLS_PER_DAY_GLOBAL=0, AI_LIVE_SESSIONS_PER_DAY=0)
def test_zero_spegne_i_tetti(user):
    _calls(user, 30, feature=LIVE_FEATURE)
    assert exhausted(user, live=True) == ""


@override_settings(**LIMITS)
def test_tetto_delle_sessioni_a_voce(user):
    _calls(user, 1, feature=LIVE_FEATURE)
    assert exhausted(user) == ""
    assert "conversazioni a voce" in exhausted(user, live=True)


@override_settings(GEMINI_API_KEY="k", GEMINI_MODEL="main", GEMINI_FALLBACK_MODELS=[], **LIMITS)
def test_il_client_non_chiama_gemini_a_tetto_finito(gemini_calls, user):
    """Vale anche dentro Celery: un lavoro gia' in coda si ferma qui."""
    for _ in range(3):
        ai.generate(lambda types: ["ciao"], Answer, feature="test", user=user)
    with pytest.raises(ai.AIBudgetExceeded, match="Riprova domani"):
        ai.generate(lambda types: ["ciao"], Answer, feature="test", user=user)
    with pytest.raises(ai.AIBudgetExceeded):
        ai.generate_image("una torta", feature="recipe_image", user=user)
    assert len(gemini_calls) == 3
    assert AiCall.objects.count() == 3


@override_settings(GEMINI_API_KEY="k", **LIMITS)
def test_le_view_ai_rispondono_429_in_italiano(api, user):
    _calls(user, 3)
    response = api(user).post("/api/ask", {"messages": [{"role": "user", "text": "ciao"}]})
    assert response.status_code == 429
    assert "Per oggi hai finito le richieste" in response.json()["detail"]
    # Leggere resta libero: il tetto e' solo sulle view che chiamano Gemini.
    assert api(user).get("/api/recipes").status_code == 200


@override_settings(GEMINI_API_KEY="k", **LIMITS)
def test_429_anche_col_tetto_globale(api, user, other_user):
    _calls(other_user, 5)
    response = api(user).post("/api/ask", {"messages": [{"role": "user", "text": "ciao"}]})
    assert response.status_code == 429
    assert "tutta l'app" in response.json()["detail"]


@override_settings(GEMINI_API_KEY="k", **LIMITS)
def test_la_voce_in_tempo_reale_risponde_429(api, user):
    _calls(user, 1, feature=LIVE_FEATURE)
    response = api(user).post("/api/profile/interview/live")
    assert response.status_code == 429
    assert "conversazioni a voce" in response.json()["detail"]
