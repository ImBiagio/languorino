"""Condivisione con link e copia nel proprio ricettario (ADR 0012)."""

from __future__ import annotations

import io

import pytest
from django.core.files.base import ContentFile
from PIL import Image
from rest_framework.test import APIClient

from apps.recipes.models import Ingredient, Recipe
from apps.recipes.serializers import RecipeSerializer

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def recipe(user):
    user.display_name = "Giulia"
    user.save()
    serializer = RecipeSerializer(
        data={
            "title": "Torta della nonna",
            "steps": ["Impasta.", "Inforna."],
            "tags": ["dolci"],
            "ingredients": [
                {"name": "farina 00", "quantity": "300", "unit": "g"},
                {"name": "crema segreta di zia", "quantity": "2", "unit": "tbsp"},
                {"name": "uova", "quantity": "3", "unit": "pz"},
            ],
        },
        context={},
    )
    serializer.is_valid(raise_exception=True)
    made = serializer.save(owner=user)
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "red").save(buffer, "WEBP")
    made.image.save("x.webp", ContentFile(buffer.getvalue()))
    made.image_source = "photo"
    made.save()
    return made


def test_link_pubblico(user, api, recipe):
    response = api(user).post(f"/api/recipes/{recipe.id}/share")
    token = response.data["share_token"]
    assert token and len(token) >= 16
    # Di nuovo: stesso link. Con renew: link nuovo, il vecchio non va piu'.
    assert api(user).post(f"/api/recipes/{recipe.id}/share").data["share_token"] == token
    public = APIClient().get(f"/api/shared/recipes/{token}")
    assert public.status_code == 200
    data = public.data
    assert (data["title"], data["author"], data["is_mine"]) == (
        "Torta della nonna",
        "Giulia",
        False,
    )
    assert set(data["allergens"]) == {"eggs", "gluten"}
    assert data["ingredients"][0]["ingredient"]["name"] == "farina 00"
    assert "email" not in str(data) and user.email not in str(data)
    renewed = api(user).post(f"/api/recipes/{recipe.id}/share", {"renew": True}, format="json")
    assert renewed.data["share_token"] != token
    assert APIClient().get(f"/api/shared/recipes/{token}").status_code == 404
    api(user).delete(f"/api/recipes/{recipe.id}/share")
    gone = APIClient().get(f"/api/shared/recipes/{renewed.data['share_token']}")
    assert gone.status_code == 404


def test_copia_nel_mio_ricettario(user, other_user, api, recipe):
    token = api(user).post(f"/api/recipes/{recipe.id}/share").data["share_token"]
    url = f"/api/shared/recipes/{token}/copy"
    assert APIClient().post(url).status_code == 401
    assert api(user).post(url).status_code == 400  # e' gia' sua
    response = api(other_user).post(url)
    assert response.status_code == 201, response.data
    copy = Recipe.objects.get(id=response.data["id"])
    assert (copy.owner, copy.source, copy.copied_from, copy.in_cookbook) == (
        other_user,
        "copy",
        recipe,
        True,
    )
    assert copy.share_token is None
    assert list(copy.tags.values_list("name", flat=True)) == ["dolci"]
    names = [line.ingredient.name for line in copy.ingredients.order_by("position")]
    assert names == ["farina 00", "crema segreta di zia", "uova"]
    # L'ingrediente creato dall'autore non si condivide: chi copia ne ha uno suo.
    custom = copy.ingredients.get(position=1).ingredient
    assert custom.created_by == other_user
    assert Ingredient.objects.filter(name="crema segreta di zia").count() == 2
    # Immagine copiata in un file suo: cancellare l'originale non la tocca.
    assert copy.image and copy.image.name != recipe.image.name
    Recipe.all_objects.get(id=recipe.id).delete(hard=True)
    copy.refresh_from_db()
    assert copy.image.storage.exists(copy.image.name)
    assert copy.copied_from is None


def test_ricette_degli_altri_non_si_condividono(other_user, api, recipe):
    assert api(other_user).post(f"/api/recipes/{recipe.id}/share").status_code == 404


def test_vista_dall_autore(user, api, recipe):
    token = api(user).post(f"/api/recipes/{recipe.id}/share").data["share_token"]
    assert api(user).get(f"/api/shared/recipes/{token}").data["is_mine"] is True
