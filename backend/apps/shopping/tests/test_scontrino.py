"""Il cibo del piano va a Scontrino (ADR 0026): cornhub e Scontrino finti."""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest

from apps.core import cornhub
from apps.plans.models import MealPlan, PlannedMeal
from apps.shopping import scontrino

pytestmark = pytest.mark.django_db
START = date(2026, 11, 16)
LIST = {"id": "4b0c", "title": "Spesa di casa", "url": "https://scontr.inoo.it/liste/4b0c"}


@pytest.fixture
def calls(monkeypatch):
    """Le richieste a Scontrino; ``calls.status`` cambia la risposta."""

    class Calls(list):
        status = 200

    seen = Calls()

    def token(audience, scope, *, user):
        assert (audience, scope) == ("scontrino", "shopping:food")
        return "tok"

    def request(method, url, json=None, headers=None, timeout=None):
        seen.append((method, url, json, headers))
        body = {"list": LIST, "added": 3, "removed": 0, "kept_edited": 0}
        if method == "DELETE":
            body = {"removed": 3}
        return httpx.Response(seen.status, json=body)

    monkeypatch.setattr(cornhub, "app_token", token)
    monkeypatch.setattr(scontrino.httpx, "request", request)
    return seen


@pytest.fixture
def plan(user):
    plan = MealPlan.objects.create(
        owner=user, start_date=START, days=7, status="active", settings={"servings": 2}
    )
    components = [
        {"name": "pasta", "quantity": 80, "unit": "g"},
        {"name": "zucchine", "quantity": 200, "unit": "g"},
        {"name": "sale", "quantity": None, "unit": ""},
    ]
    for offset in range(2):
        day = START + timedelta(offset)
        PlannedMeal.objects.create(
            plan=plan, date=day, slot="lunch", servings=2, cooked_on=day, components=components
        )
    return plan


def test_manda_il_cibo_del_piano(user, api, plan, calls):
    r = api(user).post(f"/api/plans/{plan.id}/scontrino", {}, format="json")
    assert r.status_code == 200, r.data
    assert r.data["list"]["url"] == LIST["url"]
    method, url, body, headers = calls[0]
    assert (method, url) == ("PUT", "http://scontrino-backend:8000/api/suite/food")
    assert headers == {"Authorization": "Bearer tok"}
    assert body["ref"] == f"plan:{plan.id}"
    assert body["label"] == "Piano dal 16 al 22 novembre"
    assert body["days"] == 7 and "new_list" not in body
    rows = {row["label"]: row for row in body["items"]}
    # Sommato su tutto il piano, coi reparti di Scontrino; il sale no (basilare).
    assert rows["pasta"]["quantity"] == "320" and rows["pasta"]["unit"] == "g"
    assert rows["pasta"]["department"] == "pantry"
    assert "sale" not in rows
    plan.refresh_from_db()
    assert plan.scontrino_sent_at is not None
    assert plan.scontrino_list_url == LIST["url"]
    detail = api(user).get(f"/api/plans/{plan.id}").data["scontrino"]
    assert detail["enabled"] is True and detail["list_title"] == "Spesa di casa"


def test_mai_aperto_scontrino(user, api, plan, calls):
    calls.status = 409
    r = api(user).post(f"/api/plans/{plan.id}/scontrino", {}, format="json")
    assert r.status_code == 409 and r.data["code"] == "not_linked"
    plan.refresh_from_db()
    assert plan.scontrino_sent_at is None


def test_solo_il_proprietario(other_user, api, plan, calls):
    assert api(other_user).post(f"/api/plans/{plan.id}/scontrino").status_code == 404
    assert calls == []


def test_un_cambio_di_pasti_si_rimanda(user, api, plan, calls, django_capture_on_commit_callbacks):
    meal = plan.meals.first()
    # Mai mandato: niente rinvii.
    with django_capture_on_commit_callbacks(execute=True):
        meal.servings = 3
        meal.save()
    assert calls == []
    api(user).post(f"/api/plans/{plan.id}/scontrino", {}, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        meal.servings = 4
        meal.save()
    assert [call[0] for call in calls] == ["PUT", "PUT"]
    # "Mangiato" non cambia la spesa.
    with django_capture_on_commit_callbacks(execute=True):
        meal.eaten = True
        meal.save(update_fields=["eaten"])
    assert len(calls) == 2


def test_eliminato_il_piano_esce_da_scontrino(
    user, api, plan, calls, django_capture_on_commit_callbacks
):
    api(user).post(f"/api/plans/{plan.id}/scontrino", {}, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        assert api(user).delete(f"/api/plans/{plan.id}").status_code == 204
    method, url, *_ = calls[-1]
    assert method == "DELETE"
    assert url == f"http://scontrino-backend:8000/api/suite/food/plan:{plan.id}"
    assert [call[0] for call in calls] == ["PUT", "DELETE"]
