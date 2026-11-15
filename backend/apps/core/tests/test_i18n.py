"""Lingua dell'interfaccia: catalogo djangojs, cookie, User.language (ADR 0001)."""

from __future__ import annotations

import pytest
from django.conf import settings
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db
COOKIE = settings.LANGUAGE_COOKIE_NAME


def test_catalogo_di_default_in_italiano():
    data = APIClient().get("/api/i18n/catalog").json()
    assert data["language"] == "it"
    assert data["explicit"] is False
    assert [lang["code"] for lang in data["languages"]] == ["it", "en"]
    assert "catalog" in data


def test_catalogo_segue_il_cookie():
    client = APIClient()
    client.cookies[COOKIE] = "en"
    data = client.get("/api/i18n/catalog").json()
    assert data["language"] == "en"
    assert data["explicit"] is True


def test_catalogo_dedotto_dal_browser_non_e_esplicito():
    data = APIClient().get("/api/i18n/catalog", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9").json()
    assert data["language"] == "en"
    assert data["explicit"] is False


def test_scelta_della_lingua_scrive_il_cookie():
    response = APIClient().post("/api/i18n/language", {"language": "en"}, format="json")
    assert response.status_code == 200
    assert response.cookies[COOKIE].value == "en"


def test_scelta_della_lingua_si_salva_sull_utente(user, api):
    response = api(user).post("/api/i18n/language", {"language": "en"}, format="json")
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.language == "en"
    assert api(user).get("/api/me").data["language"] == "en"


@pytest.mark.parametrize("value", ["fr", "", "EN", None])
def test_lingua_sconosciuta_rifiutata(value):
    response = APIClient().post("/api/i18n/language", {"language": value}, format="json")
    assert response.status_code == 400
    assert COOKIE not in response.cookies


def test_catalogo_inglese_traduce_il_frontend():
    client = APIClient()
    client.cookies[COOKIE] = "en"
    catalog = client.get("/api/i18n/catalog").json()["catalog"]
    assert catalog["Ancora nessun piano"] == "No plan yet"
    assert catalog["Esci"] == "Sign out"
