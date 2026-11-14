"""Segnalazione degli errori: spenta senza DSN, mai accesa nei test."""

from __future__ import annotations

import sentry_sdk

from config.sentry import init_sentry


def test_nei_test_non_parte():
    assert not sentry_sdk.is_initialized()


def test_senza_dsn_resta_spenta(monkeypatch):
    called = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: called.append(kwargs))
    assert init_sentry("") is False
    assert init_sentry("   ") is False
    assert called == []


def test_con_il_dsn_parte_senza_dati_personali(monkeypatch):
    called = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: called.append(kwargs))
    assert init_sentry("https://chiave@glitchtip.example/1", "staging") is True
    [options] = called
    assert options["dsn"] == "https://chiave@glitchtip.example/1"
    assert options["environment"] == "staging"
    assert options["send_default_pii"] is False
    assert options["traces_sample_rate"] == 0
    assert options["include_local_variables"] is False
    assert options["max_request_body_size"] == "never"
    names = {type(item).__name__ for item in options["integrations"]}
    assert names == {"DjangoIntegration", "CeleryIntegration"}


def test_i_settings_dei_test_ignorano_il_dsn_dell_ambiente(monkeypatch):
    """Anche con SENTRY_DSN nel .env di chi lancia i test non si avvia niente."""
    import importlib

    import config.settings.test as test_settings

    called = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: called.append(kwargs))
    monkeypatch.setenv("SENTRY_DSN", "https://chiave@glitchtip.example/1")
    importlib.reload(importlib.import_module("config.settings.base"))
    importlib.reload(test_settings)
    assert called == []
    monkeypatch.delenv("SENTRY_DSN")
    importlib.reload(importlib.import_module("config.settings.base"))
    importlib.reload(test_settings)
