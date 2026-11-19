"""Spesa condivisa con chi vede il piano (ADR 0025)."""

from __future__ import annotations

import pytest

from apps.plans.models import PlanShare

pytestmark = pytest.mark.django_db
SHOP = "/api/shopping"


@pytest.fixture
def shared_list(user, other_user, api):
    """``user`` fa vedere il piano a ``other_user`` e ha una lista con una voce."""
    PlanShare.objects.create(owner=user, viewer=other_user)
    data = api(user).post(SHOP, {"title": "Spesa di casa"}, format="json").data
    api(user).post(f"{SHOP}/{data['id']}/items", {"label": "pane"}, format="json")
    return data


def test_chi_vede_il_piano_vede_e_usa_la_spesa(user, other_user, api, shared_list):
    client = api(other_user)
    lists = client.get(SHOP).data
    assert [row["id"] for row in lists] == [shared_list["id"]]
    assert lists[0]["shared_by"] == str(user)
    assert lists[0]["item_count"] == 1
    url = f"{SHOP}/{shared_list['id']}"
    detail = client.get(url).data
    item = detail["items"][0]
    # Spunta, aggiunge e modifica come chi l'ha fatta.
    assert client.patch(f"{url}/items/{item['id']}", {"checked": True}, format="json").data[
        "checked"
    ]
    added = client.post(f"{url}/items", {"label": "latte"}, format="json")
    assert added.status_code == 201
    # Chi l'ha fatta vede tutto quello che ha fatto l'altro.
    mine = api(user).get(url).data
    assert mine["shared_by"] is None
    assert mine["checked_count"] == 1
    assert {row["label"] for row in mine["items"]} == {"pane", "latte"}


def test_eliminare_resta_di_chi_ha_fatto_la_lista(user, other_user, api, shared_list):
    url = f"{SHOP}/{shared_list['id']}"
    assert api(other_user).delete(url).status_code == 403
    assert api(user).delete(url).status_code == 204


def test_senza_condivisione_niente_spesa(user, other_user, api, shared_list):
    # Si condivide in un verso solo: le liste di chi riceve restano sue.
    theirs = api(other_user).post(SHOP, {"title": "Mia"}, format="json").data
    assert [row["id"] for row in api(user).get(SHOP).data] == [shared_list["id"]]
    assert api(user).get(f"{SHOP}/{theirs['id']}").status_code == 404
    # Tolta la condivisione, la lista non si vede piu'.
    PlanShare.objects.filter(owner=user, viewer=other_user).delete()
    assert api(other_user).get(f"{SHOP}/{shared_list['id']}").status_code == 404
    item = api(user).get(f"{SHOP}/{shared_list['id']}").data["items"][0]
    patched = api(other_user).patch(
        f"{SHOP}/{shared_list['id']}/items/{item['id']}", {"checked": True}, format="json"
    )
    assert patched.status_code == 404


def test_conteggi_giusti_con_piu_condivisioni(user, other_user, api, shared_list):
    from apps.conftest import UserFactory

    # Un join coi PlanShare raddoppierebbe i conteggi: la sottoquery no.
    PlanShare.objects.create(owner=user, viewer=UserFactory())
    assert api(user).get(SHOP).data[0]["item_count"] == 1
    assert api(other_user).get(SHOP).data[0]["item_count"] == 1
