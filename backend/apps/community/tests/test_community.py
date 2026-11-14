"""Ricette pubbliche, profili pubblici, voti e commenti (ADR 0017)."""

from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.community.models import Comment
from apps.conftest import UserFactory
from apps.recipes.models import Recipe
from apps.recipes.serializers import RecipeSerializer

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _recipe(owner, title="Torta della nonna"):
    serializer = RecipeSerializer(
        data={
            "title": title,
            "steps": ["Impasta."],
            "ingredients": [{"name": "farina 00", "quantity": "300", "unit": "g"}],
        },
        context={},
    )
    serializer.is_valid(raise_exception=True)
    return serializer.save(owner=owner)


def _photo(name="foto.jpg"):
    buffer = io.BytesIO()
    Image.new("RGB", (50, 40), "green").save(buffer, "JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def _publish(api, user, recipe, visibility="public"):
    response = api(user).post(
        f"/api/recipes/{recipe.id}/share", {"visibility": visibility}, format="json"
    )
    assert response.status_code == 200, response.data
    return response.data


def test_visibilita_e_profilo_pubblico(user, api):
    user.display_name = "Giulia Rossi"
    user.save()
    recipe = _recipe(user)
    assert RecipeSerializer(recipe).data["visibility"] == "private"

    # Con il link: la pagina c'e', il profilo no.
    data = _publish(api, user, recipe, "unlisted")
    assert data["visibility"] == "unlisted" and data["share_token"]
    user.refresh_from_db()
    assert user.handle is None
    assert api().get(f"/api/shared/recipes/{data['share_token']}").data["author_handle"] is None

    # Pubblica: nasce l'indirizzo dal nome e il profilo si apre senza login.
    data = _publish(api, user, recipe)
    user.refresh_from_db()
    assert user.handle == "giulia-rossi"
    profile = api().get("/api/public/profiles/giulia-rossi")
    assert profile.status_code == 200
    assert [card["title"] for card in profile.data["recipes"]] == ["Torta della nonna"]
    assert "warnings" not in profile.data["recipes"][0]
    assert "email" not in str(profile.data)
    shared = api().get(f"/api/shared/recipes/{data['share_token']}").data
    assert shared["author_handle"] == "giulia-rossi"

    # Di nuovo privata: link spento e profilo chiuso (nessuna ricetta pubblica).
    api(user).delete(f"/api/recipes/{recipe.id}/share")
    recipe.refresh_from_db()
    assert recipe.visibility == "private" and recipe.share_token is None
    assert api().get("/api/public/profiles/giulia-rossi").status_code == 404


def test_solo_le_ricette_del_ricettario_si_pubblicano(user, api):
    recipe = _recipe(user)
    Recipe.objects.filter(pk=recipe.pk).update(in_cookbook=False)
    response = api(user).post(
        f"/api/recipes/{recipe.id}/share", {"visibility": "public"}, format="json"
    )
    assert response.status_code == 400


def test_indirizzo_del_profilo(user, other_user, api):
    other_user.handle = "preso"
    other_user.save()
    assert api(user).patch("/api/me", {"handle": "preso"}, format="json").status_code == 400
    assert api(user).patch("/api/me", {"handle": "A b"}, format="json").status_code == 400
    assert api(user).patch("/api/me", {"handle": "admin"}, format="json").status_code == 400
    response = api(user).patch("/api/me", {"handle": "Cuoca-Felice"}, format="json")
    assert response.status_code == 200 and response.data["handle"] == "cuoca-felice"


def test_voti(user, other_user, api):
    recipe = _recipe(user)
    token = _publish(api, user, recipe)["share_token"]
    url = f"/api/shared/recipes/{token}/rating"
    assert api().put(url, {"stars": 4}, format="json").status_code == 401
    assert api(user).put(url, {"stars": 4}, format="json").status_code == 400  # la sua
    assert api(other_user).put(url, {"stars": 6}, format="json").status_code == 400
    assert api(other_user).put(url, {"stars": 4}, format="json").data == {
        "average": 4.0,
        "count": 1,
        "mine": 4,
    }
    third = UserFactory()
    api(third).put(url, {"stars": 1}, format="json")
    # Cambiare voto non ne aggiunge un altro.
    data = api(other_user).put(url, {"stars": 5}, format="json").data
    assert data == {"average": 3.0, "count": 2, "mine": 5}
    assert api(user).get(f"/api/recipes/{recipe.id}").data["rating"]["count"] == 2
    assert api(other_user).delete(url).data["count"] == 1


def test_commenti_risposte_e_foto(user, other_user, api):
    recipe = _recipe(user)
    token = _publish(api, user, recipe, "unlisted")["share_token"]
    url = f"/api/shared/recipes/{token}/comments"
    assert api().post(url, {"text": "Ciao"}).status_code == 401
    assert api(other_user).post(url, {"text": "  "}).status_code == 400

    response = api(other_user).post(
        url,
        {"text": "Venuta benissimo!", "images": [_photo(), _photo("b.png")]},
        format="multipart",
    )
    assert response.status_code == 201
    root = response.data[0]
    assert root["author"]["name"] == other_user.display_name
    assert len(root["images"]) == 2 and root["images"][0].endswith(".webp")

    reply = api(user).post(url, {"text": "Grazie!", "parent": root["id"]}).data[0]["replies"][0]
    # Risposta a una risposta: finisce nello stesso filo.
    api(other_user).post(url, {"text": "Di niente", "parent": reply["id"]})
    thread = api().get(url).data[0]
    assert [item["text"] for item in thread["replies"]] == ["Grazie!", "Di niente"]
    assert thread["replies"][0]["author"]["is_recipe_author"] is True
    assert thread["can_delete"] is False  # senza login

    # Troppe foto, o un file che non e' una foto.
    too_many = {"text": "x", "images": [_photo(f"{n}.jpg") for n in range(4)]}
    assert api(other_user).post(url, too_many, format="multipart").status_code == 400
    fake = SimpleUploadedFile("a.jpg", b"non sono una foto", content_type="image/jpeg")
    assert api(other_user).post(url, {"images": [fake]}, format="multipart").status_code == 400


def test_chi_cancella_i_commenti(user, other_user, api):
    recipe = _recipe(user)
    token = _publish(api, user, recipe, "unlisted")["share_token"]
    url = f"/api/shared/recipes/{token}/comments"
    root = api(other_user).post(url, {"text": "Primo"}).data[0]
    api(user).post(url, {"text": "Risposta", "parent": root["id"]})
    lonely = api(other_user).post(url, {"text": "Secondo"}).data[0]
    third = UserFactory()
    assert api(third).delete(f"/api/comments/{root['id']}").status_code == 404

    # L'autore della ricetta modera: il commento con risposte resta "eliminato".
    assert api(user).delete(f"/api/comments/{root['id']}").status_code == 204
    # L'autore del commento cancella il suo: senza risposte sparisce.
    assert api(other_user).delete(f"/api/comments/{lonely['id']}").status_code == 204
    threads = api().get(url).data
    assert len(threads) == 1
    assert threads[0]["is_deleted"] is True and threads[0]["text"] == ""
    assert threads[0]["author"] is None
    assert threads[0]["replies"][0]["text"] == "Risposta"
    assert Comment.all_objects.filter(recipe=recipe).count() == 3


def test_ricetta_privata_non_si_commenta(user, other_user, api):
    recipe = _recipe(user)
    token = _publish(api, user, recipe, "unlisted")["share_token"]
    api(user).delete(f"/api/recipes/{recipe.id}/share")
    assert api(other_user).get(f"/api/shared/recipes/{token}/comments").status_code == 404
    assert (
        api(other_user).put(f"/api/shared/recipes/{token}/rating", {"stars": 3}).status_code == 404
    )
