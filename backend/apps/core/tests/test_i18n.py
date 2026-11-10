"""Lingua dell'interfaccia: catalogo djangojs, cookie, User.language (ADR 0001)."""

from __future__ import annotations

import pytest
from django.conf import settings
from django.core import mail
from rest_framework.test import APIClient

from apps.users.emails import send_password_reset_email
from apps.users.models import User

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


def test_registrazione_nella_lingua_del_cookie():
    client = APIClient()
    client.cookies[COOKIE] = "en"
    response = client.post(
        "/api/auth/register",
        {"email": "english@languorino.test", "password": "una-password-lunga"},
        format="json",
    )
    assert response.status_code == 201
    assert User.objects.get(email="english@languorino.test").language == "en"


def test_catalogo_inglese_traduce_il_frontend():
    client = APIClient()
    client.cookies[COOKIE] = "en"
    catalog = client.get("/api/i18n/catalog").json()["catalog"]
    assert catalog["Ancora niente qui"] == "Nothing here yet"
    assert catalog["Esci"] == "Sign out"


def test_errori_dell_api_nella_lingua_scelta(user):
    payload = {"email": user.email, "password": "una-password-lunga"}
    italiano = APIClient().post("/api/auth/register", payload, format="json")
    client = APIClient()
    client.cookies[COOKIE] = "en"
    english = client.post("/api/auth/register", payload, format="json")
    assert italiano.status_code == english.status_code == 400
    assert "gia'" in str(italiano.data["email"][0])
    assert "already" in str(english.data["email"][0])


def test_mail_nella_lingua_dell_utente(user, django_capture_on_commit_callbacks):
    user.language = "en"
    user.save()
    with django_capture_on_commit_callbacks(execute=True):
        send_password_reset_email(user)
    [message] = mail.outbox
    assert "password" in message.subject.lower()
    assert "Reimposta" not in message.subject
    assert message.body.startswith("Hi ")
    assert 'lang="en"' in message.alternatives[0][0]
