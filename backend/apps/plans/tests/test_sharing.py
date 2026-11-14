"""Piano fatto vedere a un altro account, in sola lettura (ADR 0019)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core import mail

from apps.conftest import UserFactory
from apps.plans.models import MealPlan, PlannedMeal, PlanShare
from apps.recipes.serializers import RecipeSerializer

pytestmark = pytest.mark.django_db
URL = "/api/plan-shares"
TODAY = date.today()


def _recipe(user, title):
    serializer = RecipeSerializer(
        data={
            "title": title,
            "ingredients": [{"name": "pasta", "quantity": "160", "unit": "g"}],
            "steps": ["Cuoci."],
        },
        context={},
    )
    serializer.is_valid(raise_exception=True)
    return serializer.save(owner=user)


@pytest.fixture
def plan(user):
    plan = MealPlan.objects.create(
        owner=user,
        start_date=TODAY - timedelta(days=1),
        days=7,
        status=MealPlan.Status.ACTIVE,
        settings={
            "slots": ["lunch"],
            "servings": 2,
            "prep_mode": "none",
            "goal_note": "perdere 5 kg",
            "nutritionist_plan": "6f1c2b9e-0d7a-4c55-9a3e-2f0b8a1d4e77",
        },
    )
    recipe = _recipe(user, "Pasta e ceci")
    PlannedMeal.objects.create(
        plan=plan, date=TODAY, slot="lunch", recipe=recipe, servings=2, cooked_on=TODAY
    )
    return plan


def _share(api, owner, viewer, capture):
    with capture(execute=True):
        response = api(owner).post(URL, {"email": viewer.email.upper()}, format="json")
    assert response.status_code == 201, response.data
    return PlanShare.objects.get(owner=owner, viewer=viewer)


def test_condividere_e_vedere(
    user, other_user, api, plan, settings, django_capture_on_commit_callbacks
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    share = _share(api, user, other_user, django_capture_on_commit_callbacks)
    # Chi riceve lo sa da una mail con il link alla pagina.
    assert len(mail.outbox) == 1
    assert f"/piano/condivisi/{share.id}" in mail.outbox[0].body

    mine = api(user).get(URL).data
    assert mine["given"][0]["email"] == other_user.email
    theirs = api(other_user).get(URL).data
    assert theirs["received"][0] == {
        "id": str(user.id),
        "name": user.display_name,
        "share": str(share.id),
        "has_plan": True,
    }
    assert "email" not in theirs["received"][0]

    data = api(other_user).get(f"{URL}/{share.id}/plan").data
    assert data["owner"]["name"] == user.display_name
    seen = data["plan"]
    assert seen["meals"][0]["recipe"]["title"] == "Pasta e ceci"
    # Niente obiettivo, note o piano del nutrizionista di chi condivide.
    assert seen["settings"] == {"slots": ["lunch"], "servings": 2, "prep_mode": "none"}
    assert seen["nutritionist"] is None

    recipe_id = seen["meals"][0]["recipe"]["id"]
    recipe = api(other_user).get(f"{URL}/{share.id}/recipes/{recipe_id}").data
    assert recipe["steps"] == ["Cuoci."] and recipe["is_mine"] is False


def test_sola_lettura(user, other_user, api, plan, django_capture_on_commit_callbacks):
    _share(api, user, other_user, django_capture_on_commit_callbacks)
    meal = plan.meals.first()
    # Le API del piano restano del proprietario.
    assert api(other_user).get(f"/api/plans/{plan.id}").status_code == 404
    assert (
        api(other_user)
        .patch(f"/api/plans/{plan.id}/meals/{meal.id}", {"servings": 4}, format="json")
        .status_code
        == 404
    )
    assert api(other_user).get(f"/api/recipes/{meal.recipe_id}").status_code == 404


def test_solo_le_ricette_del_piano(user, other_user, api, plan, django_capture_on_commit_callbacks):
    share = _share(api, user, other_user, django_capture_on_commit_callbacks)
    secret = _recipe(user, "Ricetta segreta")
    response = api(other_user).get(f"{URL}/{share.id}/recipes/{secret.id}")
    assert response.status_code == 404


def test_email_sbagliate(user, api):
    assert api(user).post(URL, {"email": user.email}, format="json").status_code == 400
    response = api(user).post(URL, {"email": "nessuno@languorino.test"}, format="json")
    assert response.status_code == 400


def test_condividere_due_volte_non_duplica(
    user, other_user, api, plan, settings, django_capture_on_commit_callbacks
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    _share(api, user, other_user, django_capture_on_commit_callbacks)
    _share(api, user, other_user, django_capture_on_commit_callbacks)
    assert PlanShare.objects.count() == 1 and len(mail.outbox) == 1


def test_spegnere_e_togliere(user, other_user, api, plan, django_capture_on_commit_callbacks):
    share = _share(api, user, other_user, django_capture_on_commit_callbacks)
    third = UserFactory()
    assert api(third).get(f"{URL}/{share.id}/plan").status_code == 404
    assert api(third).delete(f"{URL}/{share.id}").status_code == 404
    # Chi condivide non "riceve" il suo piano.
    assert api(user).get(f"{URL}/{share.id}/plan").status_code == 404
    # Chi riceve lo toglie dal suo elenco.
    assert api(other_user).delete(f"{URL}/{share.id}").status_code == 204
    assert api(other_user).get(f"{URL}/{share.id}/plan").status_code == 404

    share = _share(api, user, other_user, django_capture_on_commit_callbacks)
    assert api(user).delete(f"{URL}/{share.id}").status_code == 204
    assert not PlanShare.objects.exists()


def test_senza_piano(user, other_user, api, django_capture_on_commit_callbacks):
    share = _share(api, user, other_user, django_capture_on_commit_callbacks)
    data = api(other_user).get(f"{URL}/{share.id}/plan").data
    assert data["plan"] is None
    assert api(other_user).get(URL).data["received"][0]["has_plan"] is False
