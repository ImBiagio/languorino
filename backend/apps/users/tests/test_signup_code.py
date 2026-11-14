"""Codice di invito alla registrazione (``SIGNUP_CODE``): vuoto = aperta."""

from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.users.models import User

pytestmark = pytest.mark.django_db

CODE = "amici-di-casa"


def _register(**extra):
    return APIClient().post(
        "/api/auth/register",
        {"email": "nuova@languorino.test", "password": "una-password-lunga", **extra},
        format="json",
    )


def test_senza_codice_la_registrazione_resta_aperta():
    assert APIClient().get("/api/auth/config").json() == {"signup_code_required": False}
    # Un codice mandato comunque non da' fastidio.
    assert _register(invite_code="qualcosa").status_code == 201
    assert User.objects.filter(email="nuova@languorino.test").exists()


@override_settings(SIGNUP_CODE=CODE)
def test_il_frontend_sa_che_serve_ma_non_lo_legge():
    response = APIClient().get("/api/auth/config")
    assert response.json() == {"signup_code_required": True}
    assert CODE not in response.content.decode()


@override_settings(SIGNUP_CODE=CODE)
@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"invite_code": ""},
        {"invite_code": "sbagliato"},
        {"invite_code": CODE.upper()},
        {"invite_code": None},
        {"invite_code": ["x"]},
    ],
)
def test_senza_il_codice_giusto_non_ci_si_registra(extra):
    response = _register(**extra)
    assert response.status_code == 400
    assert response.json() == {"invite_code": ["Codice di invito non valido."]}
    assert not User.objects.exists()


@override_settings(SIGNUP_CODE=CODE)
def test_col_codice_giusto_si(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = _register(invite_code=f" {CODE} ")
    assert response.status_code == 201
    assert User.objects.filter(email="nuova@languorino.test").exists()


@override_settings(SIGNUP_CODE=CODE)
def test_senza_codice_non_si_scopre_se_un_email_ha_un_account(user):
    """L'errore sull'email gia' usata esce solo a chi ha il codice."""
    response = APIClient().post(
        "/api/auth/register",
        {"email": user.email, "password": "una-password-lunga"},
        format="json",
    )
    assert response.json() == {"invite_code": ["Codice di invito non valido."]}
    response = APIClient().post(
        "/api/auth/register",
        {"email": user.email, "password": "una-password-lunga", "invite_code": CODE},
        format="json",
    )
    assert "email" in response.json()
