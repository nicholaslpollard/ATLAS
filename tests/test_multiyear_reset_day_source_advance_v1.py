from __future__ import annotations

import pytest

import scripts.run_multiyear_reset_day_source_advance_v1 as m
from scripts.run_multiyear_reset_day_source_advance_v1 import (
    _load_runtime, _remaining_after,
)


def test_provider_remaining_header_is_hardest_bound():
    assert _remaining_after(10000, 9512, 487) == 9512
    assert _remaining_after(5000, 7000, 100) == 5000
    assert _remaining_after(5000, 0, 100) == 0


def test_missing_provider_remaining_falls_back_to_observed_debit():
    assert _remaining_after(10000, None, 487) == 9513
    assert _remaining_after(100, None, 100) == 0


def test_malformed_observation_never_invents_extra_budget():
    assert _remaining_after(1000, "900", "100") == 1000


def test_root_dotenv_settings_load_precedes_marketdata_token_lookup(monkeypatch):
    monkeypatch.delenv("MARKETDATA_TOKEN", raising=False)
    sentinel = object()
    calls = []

    def fake_load_settings(root, environment):
        calls.append((root, environment))
        monkeypatch.setenv("MARKETDATA_TOKEN", "loaded-from-root-dotenv")
        return sentinel

    monkeypatch.setattr(m, "load_settings", fake_load_settings)
    settings, token = _load_runtime()
    assert settings is sentinel
    assert token == "loaded-from-root-dotenv"
    assert calls == [(m.ROOT, "development")]


def test_missing_marketdata_token_after_settings_load_fails_closed(monkeypatch):
    monkeypatch.delenv("MARKETDATA_TOKEN", raising=False)
    monkeypatch.setattr(m, "load_settings", lambda *_: object())
    with pytest.raises(ValueError, match="root \\.env"):
        _load_runtime()
