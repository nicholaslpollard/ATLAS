from __future__ import annotations

import pandas as pd
import pytest

from packages.regimes.persistence_probe import (
    MARKET_PERSISTED_DIMENSIONS,
    REGIME_PERSISTENCE_CONFIRMATION_WINDOWS,
    REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION,
    SECTOR_PERSISTED_DIMENSIONS,
    agreement_diagnostics,
    confirm_states,
    persist_market_states,
    persist_sector_states,
)


def test_persistence_probe_contract_and_windows_are_locked():
    assert REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION == (
        "regime-persistence-probe-v1-dimension-confirmation-grid"
    )
    assert REGIME_PERSISTENCE_CONFIRMATION_WINDOWS == (2, 3)
    assert MARKET_PERSISTED_DIMENSIONS == (
        "structure",
        "momentum",
        "participation",
        "volatility",
        "efficiency",
    )
    assert SECTOR_PERSISTED_DIMENSIONS == (
        "structure",
        "momentum",
        "volatility",
        "efficiency",
    )


def test_two_session_confirmation_rejects_single_session_flip():
    raw = ["BULL", "BEAR", "BULL", "BEAR", "BEAR", "BEAR"]
    assert confirm_states(raw, 2) == ["BULL", "BULL", "BULL", "BULL", "BEAR", "BEAR"]
    with pytest.raises(ValueError):
        confirm_states(raw, 0)


def test_three_session_confirmation_waits_for_third_observation():
    raw = ["BULL", "BEAR", "BEAR", "BEAR", "MIXED", "MIXED", "MIXED"]
    assert confirm_states(raw, 3) == [
        "BULL",
        "BULL",
        "BULL",
        "BEAR",
        "BEAR",
        "BEAR",
        "MIXED",
    ]


def test_agreement_diagnostics_separates_exact_family_and_opposite_lag():
    raw = ["BULL", "BEAR", "MIXED", "STRONG_BEAR"]
    persisted = ["BULL", "BULL", "MIXED", "BEAR"]
    diagnostic = agreement_diagnostics(raw, persisted)
    assert diagnostic["exact_agreement_rate"] == pytest.approx(0.50)
    assert diagnostic["direction_family_agreement_rate"] == pytest.approx(0.75)
    assert diagnostic["opposite_direction_mismatch_count"] == 1
    assert diagnostic["opposite_direction_mismatch_rate"] == pytest.approx(0.25)


def test_dimension_persistence_recomputes_market_and_sector_composites():
    market = pd.DataFrame(
        {
            "trading_date": pd.to_datetime(["2026-08-12", "2026-08-13", "2026-08-14"]),
            "structure": ["UP", "DOWN", "DOWN"],
            "momentum": ["POSITIVE", "NEGATIVE", "NEGATIVE"],
            "participation": ["MIXED", "BROAD_NEGATIVE", "BROAD_NEGATIVE"],
            "volatility": ["NORMAL", "STRESSED", "STRESSED"],
            "efficiency": ["NORMAL", "LOW", "LOW"],
            "composite": ["BULL", "BEAR", "BEAR"],
        }
    )
    persisted_market = persist_market_states(market, 2)
    assert persisted_market["composite"].tolist() == ["BULL", "BULL", "BEAR"]
    assert persisted_market["volatility"].tolist() == ["NORMAL", "NORMAL", "STRESSED"]

    sector = pd.DataFrame(
        {
            "trading_date": pd.to_datetime(["2026-08-12", "2026-08-13", "2026-08-14"]),
            "symbol": ["XLK", "XLK", "XLK"],
            "structure": ["UP", "STRONG_DOWN", "STRONG_DOWN"],
            "momentum": ["POSITIVE", "STRONG_NEGATIVE", "STRONG_NEGATIVE"],
            "volatility": ["NORMAL", "ELEVATED", "ELEVATED"],
            "efficiency": ["NORMAL", "HIGH", "HIGH"],
            "composite": ["BULL", "STRONG_BEAR", "STRONG_BEAR"],
        }
    )
    persisted_sector = persist_sector_states(sector, 2)
    assert persisted_sector["composite"].tolist() == ["BULL", "BULL", "STRONG_BEAR"]
    assert persisted_sector["volatility"].tolist() == ["NORMAL", "NORMAL", "ELEVATED"]
