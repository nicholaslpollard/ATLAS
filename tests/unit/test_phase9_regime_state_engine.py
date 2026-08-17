from __future__ import annotations

from datetime import date

import pandas as pd

import packages.regimes.state_engine as state_engine
from packages.regimes.persistence_policy import REGIME_SELECTED_CONFIRMATION_SESSIONS
from packages.regimes.state_engine import (
    REGIME_STATE_POLICY_CONTRACT_VERSION,
    REGIME_STATE_SNAPSHOT_CONTRACT_VERSION,
    _score_fields,
    _stable_hash,
    _state_fields,
    _thresholds_from_row,
    compute_regime_state_history,
)
from packages.regimes.threshold_policy import (
    REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
    REGIME_HISTORY_ORIGIN_DATE,
    REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
    REGIME_THRESHOLD_POLICY_NAME,
    REGIME_THRESHOLD_TRAINING_SESSIONS,
)


def test_production_regime_policy_contracts_are_locked():
    assert REGIME_THRESHOLD_POLICY_CONTRACT_VERSION == (
        "regime-threshold-policy-v1-expanding-252-prior-only"
    )
    assert REGIME_THRESHOLD_POLICY_NAME == "expanding_252"
    assert REGIME_THRESHOLD_TRAINING_SESSIONS == 252
    assert REGIME_HISTORY_ORIGIN_DATE == date(2021, 8, 16)
    assert REGIME_BREADTH_POPULATION_CONTRACT_VERSION == (
        "regime-breadth-population-v1-250k-dollar-volume-complete-1d"
    )
    assert REGIME_SELECTED_CONFIRMATION_SESSIONS == 2
    assert REGIME_STATE_POLICY_CONTRACT_VERSION == (
        "regime-state-policy-v1-expanding252-confirm2-dimensional"
    )
    assert REGIME_STATE_SNAPSHOT_CONTRACT_VERSION == (
        "regime-state-snapshot-v1-market-sector-proxies"
    )


def test_regime_state_dependency_hash_is_deterministic_and_sensitive():
    payload = {"policy": "expanding_252", "confirmation": 2, "as_of": "2026-08-14"}
    first = _stable_hash(payload)
    second = _stable_hash(dict(reversed(tuple(payload.items()))))
    changed = _stable_hash({**payload, "confirmation": 3})
    assert first == second
    assert first != changed
    assert len(first) == 64


def test_threshold_audit_serialization_preserves_available_quantiles():
    row = pd.Series(
        {
            "trend__p25": 0.10,
            "trend__p75": 0.70,
            "risk__p25": 0.20,
            "risk__p75": 0.80,
            "risk__p90": 0.95,
        }
    )
    thresholds = _thresholds_from_row(row, ("trend", "risk"))
    assert thresholds["trend"] == {"p25": 0.10, "p75": 0.70}
    assert thresholds["risk"] == {"p25": 0.20, "p75": 0.80, "p90": 0.95}


def test_state_snapshot_helpers_keep_scores_and_effective_dimensions_separate():
    row = pd.Series(
        {
            "composite": "BULL",
            "structure": "UP",
            "momentum": "POSITIVE",
            "participation": "MIXED",
            "volatility": "NORMAL",
            "efficiency": "HIGH",
            "structure_score": 2,
            "momentum_score": 1,
        }
    )
    state = _state_fields(row, market=True)
    scores = _score_fields(row)
    assert state == {
        "composite": "BULL",
        "structure": "UP",
        "momentum": "POSITIVE",
        "volatility": "NORMAL",
        "efficiency": "HIGH",
        "participation": "MIXED",
    }
    assert scores == {"structure_score": 2, "momentum_score": 1}
    assert "structure_score" not in state


def test_compute_history_uses_expanding_thresholds_and_two_session_confirmation(monkeypatch):
    dates = pd.date_range("2026-08-12", periods=3, freq="D").date
    raw_market = pd.DataFrame(
        {
            "trading_date": dates,
            "structure_score": [2, -2, -2],
            "structure": ["UP", "DOWN", "DOWN"],
            "momentum_score": [0, 0, 0],
            "momentum": ["MIXED", "MIXED", "MIXED"],
            "participation": ["MIXED", "MIXED", "MIXED"],
            "volatility": ["NORMAL", "NORMAL", "NORMAL"],
            "efficiency": ["NORMAL", "NORMAL", "NORMAL"],
            "composite": ["BULL", "BEAR", "BEAR"],
        }
    )
    raw_sector = pd.DataFrame(
        {
            "trading_date": dates,
            "symbol": ["XLB", "XLB", "XLB"],
            "structure_score": [1, -1, -1],
            "structure": ["UP", "DOWN", "DOWN"],
            "momentum_score": [0, 0, 0],
            "momentum": ["MIXED", "MIXED", "MIXED"],
            "volatility": ["NORMAL", "NORMAL", "NORMAL"],
            "efficiency": ["NORMAL", "NORMAL", "NORMAL"],
            "composite": ["BULL", "BEAR", "BEAR"],
        }
    )
    seen: list[str] = []

    def fake_market(_breadth, _basket, policy_name):
        seen.append(policy_name)
        return raw_market.copy()

    def fake_sector(_sector, policy_name):
        seen.append(policy_name)
        return raw_sector.copy()

    monkeypatch.setattr(state_engine, "_market_point_in_time_states", fake_market)
    monkeypatch.setattr(state_engine, "_sector_point_in_time_states", fake_sector)
    monkeypatch.setattr(state_engine, "basket_daily", lambda _frame: pd.DataFrame())

    proxies = pd.DataFrame({"symbol": ["SPY", "XLB"]})
    raw_m, effective_m, raw_s, effective_s = compute_regime_state_history(
        pd.DataFrame(),
        proxies,
    )

    assert seen == ["expanding_252", "expanding_252"]
    assert raw_m["composite"].tolist() == ["BULL", "BEAR", "BEAR"]
    assert effective_m["composite"].tolist() == ["BULL", "BULL", "BEAR"]
    assert raw_s["composite"].tolist() == ["BULL", "BEAR", "BEAR"]
    assert effective_s["composite"].tolist() == ["BULL", "BULL", "BEAR"]
