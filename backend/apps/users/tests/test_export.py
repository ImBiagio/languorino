"""Esportazione degli utenti verso cornhub (``export_cornhub_users``)."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.profiles.models import Profile


def _export() -> list[dict]:
    out = StringIO()
    call_command("export_cornhub_users", stdout=out)
    return json.loads(out.getvalue())


@pytest.mark.django_db
def test_export_divide_il_nome_visibile(user):
    user.display_name = "Anna Maria Bianchi"
    user.save()
    [row] = _export()
    assert row["email"] == user.email
    assert row["first_name"] == "Anna" and row["last_name"] == "Maria Bianchi"
    assert row["password"].startswith("md5$")  # l'hash, mai la password
    assert row["is_active"] is True and row["email_verified"] is False
    assert row["language"] == "it" and row["last_login"] is None
    assert set(row) == {
        "email", "password", "first_name", "last_name", "display_name", "language",
        "email_verified", "is_active", "date_joined", "last_login",
    }


@pytest.mark.django_db
def test_export_usa_nome_e_cognome_del_profilo(user, other_user):
    Profile.objects.create(user=user, first_name="Giulia", last_name="Rossi")
    other_user.set_unusable_password()
    other_user.save()
    rows = {row["email"]: row for row in _export()}
    assert (rows[user.email]["first_name"], rows[user.email]["last_name"]) == ("Giulia", "Rossi")
    assert rows[other_user.email]["password"] == ""
