"""Login con cornhub: cornhub finto (httpx sostituito), id_token firmati qui."""

from __future__ import annotations

import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from rest_framework.test import APIClient

from apps.core import cornhub
from apps.users.models import User

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key())), "kid": "k1"}


def _token(nonce, sub="2b6f5a8e-0000-4000-8000-000000000001", key=KEY, **claims):
    now = int(time.time())
    payload = {
        "iss": "https://cornhub.test/o", "aud": "client-test", "sub": sub,
        "iat": now, "exp": now + 300, "nonce": nonce,
        "email": "anna@example.com", "email_verified": True, "name": "Anna Bianchi",
        "locale": "it", **claims,
    }
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture
def fake_cornhub(monkeypatch):
    state = {"claims": {}, "key": KEY, "status": {"active": True, "allowed": True}}

    def fake_get(url, **kwargs):
        if url.endswith("/o/.well-known/jwks.json"):
            return httpx.Response(200, json={"keys": [JWK]}, request=httpx.Request("GET", url))
        if "/internal/users/" in url:
            return httpx.Response(200, json=state["status"], request=httpx.Request("GET", url))
        raise AssertionError(url)

    def fake_post(url, **kwargs):
        assert url == "http://cornhub-backend:8000/o/token/"
        assert kwargs["data"]["client_secret"] == "secret-test"
        token = _token(state["nonce"], key=state["key"], **state["claims"])
        return httpx.Response(200, json={"id_token": token}, request=httpx.Request("POST", url))

    monkeypatch.setattr(cornhub.httpx, "get", fake_get)
    monkeypatch.setattr(cornhub.httpx, "post", fake_post)
    return state


def _login(client, state, next_url="/conti"):
    start = client.get(f"/api/auth/sso/start?next={next_url}")
    assert start.status_code == 302
    query = parse_qs(urlparse(start["Location"]).query)
    assert start["Location"].startswith("https://cornhub.test/o/authorize/")
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["https://app.test/api/auth/sso/callback"]
    state["nonce"] = query["nonce"][0]
    return client.get(f"/api/auth/sso/callback?code=abc&state={query['state'][0]}")


@pytest.mark.django_db
def test_login_creates_user_and_session(fake_cornhub):
    client = APIClient()
    r = _login(client, fake_cornhub)
    assert r.status_code == 302 and r["Location"] == "https://app.test/conti"
    user = User.objects.get()
    assert user.email == "anna@example.com" and user.display_name == "Anna Bianchi"
    assert not user.has_usable_password()
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200 and r.json()["user"]["email"] == "anna@example.com"


@pytest.mark.django_db
def test_existing_user_is_linked_by_verified_email(fake_cornhub, user):
    user.email = "anna@example.com"
    user.save()
    _login(APIClient(), fake_cornhub)
    user.refresh_from_db()
    assert str(user.cornhub_sub).endswith("0001")
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_unverified_email_does_not_link(fake_cornhub, user):
    user.email = "anna@example.com"
    user.save()
    fake_cornhub["claims"] = {"email_verified": False}
    _login(APIClient(), fake_cornhub)
    user.refresh_from_db()
    assert user.cornhub_sub is None


@pytest.mark.django_db
def test_forged_token_and_wrong_state_are_rejected(fake_cornhub):
    fake_cornhub["key"] = OTHER_KEY
    r = _login(APIClient(), fake_cornhub)
    assert "/accedi?errore=" in r["Location"]
    fake_cornhub["key"] = KEY
    client = APIClient()
    client.get("/api/auth/sso/start")
    r = client.get("/api/auth/sso/callback?code=abc&state=sbagliato")
    assert "errore=stato" in r["Location"]
    assert not User.objects.exists()


@pytest.mark.django_db
def test_open_redirect_is_blocked(fake_cornhub):
    r = _login(APIClient(), fake_cornhub, next_url="//evil.example")
    assert r["Location"] == "https://app.test/"


@pytest.mark.django_db
def test_disabled_account_loses_session(fake_cornhub):
    client = APIClient()
    _login(client, fake_cornhub)
    fake_cornhub["status"] = {"active": False, "allowed": False}
    from django.core.cache import cache

    cache.clear()
    assert client.post("/api/auth/refresh").status_code == 401


@pytest.mark.django_db
def test_logout_points_to_cornhub(fake_cornhub):
    client = APIClient()
    _login(client, fake_cornhub)
    r = client.post("/api/auth/logout")
    assert r.json()["logout_url"].startswith("https://cornhub.test/o/logout/")
    assert client.post("/api/auth/refresh").status_code == 401
