"""Mail dell'account: conferma, reinvio, reset della password."""

from __future__ import annotations

import re

import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.conftest import UserFactory

pytestmark = pytest.mark.django_db
PASSWORD = "password-di-prova"


def _link(message, prefix: str) -> str:
    """Il link della mail, dal testo semplice (lo stesso sta nella parte HTML)."""
    match = re.search(rf"https?://[^/\s]+/{prefix}/(\S+)", message.body)
    assert match, message.body
    return match.group(1)


@override_settings(REQUIRE_EMAIL_VERIFICATION=True)
def test_registrazione_manda_la_conferma(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = APIClient().post(
            "/api/auth/register",
            {"email": "Nuova@Templatino.test", "password": "una-password-lunga"},
            format="json",
        )
    assert response.status_code == 201
    assert "access" not in response.data
    [message] = mail.outbox
    assert message.to == ["nuova@templatino.test"]
    assert message.alternatives[0][1] == "text/html"
    token = _link(message, "verifica-email")
    assert APIClient().post(f"/api/auth/verify-email/{token}").status_code == 200


@override_settings(REQUIRE_EMAIL_VERIFICATION=True)
def test_login_non_confermato_e_reinvio(user, django_capture_on_commit_callbacks):
    user.email_verified_at = None
    user.save()
    response = APIClient().post(
        "/api/auth/login", {"email": user.email, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 403
    assert response.data["code"] == "email_not_verified"

    with django_capture_on_commit_callbacks(execute=True):
        resend = APIClient().post(
            "/api/auth/verify-email/resend", {"email": user.email}, format="json"
        )
    assert resend.status_code == 204
    assert len(mail.outbox) == 1


def test_reinvio_e_reset_non_dicono_chi_e_registrato(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        for url in ("/api/auth/verify-email/resend", "/api/auth/password-reset"):
            response = APIClient().post(url, {"email": "nessuno@templatino.test"}, format="json")
            assert response.status_code == 204
    assert mail.outbox == []


def test_reset_password_completo(user, django_capture_on_commit_callbacks):
    other_session = APIClient()
    other_session.post(
        "/api/auth/login", {"email": user.email, "password": PASSWORD}, format="json"
    )
    with django_capture_on_commit_callbacks(execute=True):
        APIClient().post("/api/auth/password-reset", {"email": user.email}, format="json")
    uid, token = _link(mail.outbox[0], "reset-password").split("/")

    confirm = APIClient().post(
        "/api/auth/password-reset/confirm",
        {"uid": uid, "token": token, "new_password": "nuova-password-lunga"},
        format="json",
    )
    assert confirm.status_code == 200
    assert "access" in confirm.data
    user.refresh_from_db()
    assert user.check_password("nuova-password-lunga")
    # Le sessioni aperte con la vecchia password cadono.
    assert other_session.post("/api/auth/refresh").status_code == 401
    # Il link vale una volta sola.
    again = APIClient().post(
        "/api/auth/password-reset/confirm",
        {"uid": uid, "token": token, "new_password": "terza-password-lunga"},
        format="json",
    )
    assert again.status_code == 400


def test_reset_rifiuta_password_debole_e_link_falsi(user, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        APIClient().post("/api/auth/password-reset", {"email": user.email}, format="json")
    uid, token = _link(mail.outbox[0], "reset-password").split("/")
    weak = APIClient().post(
        "/api/auth/password-reset/confirm",
        {"uid": uid, "token": token, "new_password": "123"},
        format="json",
    )
    assert weak.status_code == 400
    assert "new_password" in weak.data
    for bad_uid, bad_token in [("xx", token), (uid, "1-abc"), ("bm90LWEtdXVpZA", token)]:
        response = APIClient().post(
            "/api/auth/password-reset/confirm",
            {"uid": bad_uid, "token": bad_token, "new_password": "nuova-password-lunga"},
            format="json",
        )
        assert response.status_code == 400



def test_utente_disattivato_non_riceve_il_reset(django_capture_on_commit_callbacks):
    ghost = UserFactory(is_active=False)
    with django_capture_on_commit_callbacks(execute=True):
        APIClient().post("/api/auth/password-reset", {"email": ghost.email}, format="json")
    assert mail.outbox == []
