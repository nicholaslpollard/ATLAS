from datetime import date

import pandas as pd

from packages.regimes.ticker_state_engine import (
    TICKER_STATE_MANIFEST_VERSION,
    TICKER_STATE_POLICY_CONTRACT_VERSION,
    TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
    classify_current_ticker_dimensions,
    persisted_current_dimensions,
)


def _current_row() -> pd.Series:
    return pd.Series(
        {
            "close_1d": 120.0,
            "ema20_1d": 110.0,
            "ema50_1d": 100.0,
            "ema200_1d": 90.0,
            "return1_1d": 0.02,
            "rsi_1d": 60.0,
            "macd_hist_1d": 0.5,
            "ema20_slope_1d": 1.0,
            "close_4h": 120.0,
            "ema20_4h": 110.0,
            "ema50_4h": 100.0,
            "rsi_4h": 60.0,
            "macd_hist_4h": 0.5,
            "ema20_slope_4h": 1.0,
            "close_1h": 120.0,
            "ema20_1h": 110.0,
            "ema50_1h": 100.0,
            "rsi_1h": 60.0,
            "macd_hist_1h": 0.5,
            "ema20_slope_1h": 1.0,
        }
    )


def test_gate12_contracts_are_explicit() -> None:
    assert TICKER_STATE_POLICY_CONTRACT_VERSION == (
        "ticker-state-policy-v1-confirm2-dimensional-risk126-60"
    )
    assert TICKER_STATE_SNAPSHOT_CONTRACT_VERSION == (
        "ticker-state-snapshot-v1-routed-identity-persistence-risk"
    )
    assert TICKER_STATE_MANIFEST_VERSION == "ticker-state-manifest-v1-policy-lineage"


def test_gate12_current_classifier_reuses_accepted_ticker_semantics() -> None:
    result = classify_current_ticker_dimensions(_current_row())
    assert result == {
        "daily_structure": "STRONG_UP",
        "short_alignment": "ALIGNED_UP",
        "momentum": "POSITIVE",
        "ticker_state": "STRONG_UPTREND",
    }


def test_gate12_current_classifier_refuses_incomplete_state() -> None:
    row = _current_row()
    row["ema50_1h"] = None
    assert classify_current_ticker_dimensions(row) is None


def test_gate12_persistence_requires_two_consecutive_new_dimension_states() -> None:
    frame = pd.DataFrame(
        [
            {
                "instrument_id": "ins_1",
                "trading_date": date(2026, 8, 10),
                "daily_structure": "UP",
                "short_alignment": "MIXED",
                "momentum": "POSITIVE",
                "candidate_state": "UPTREND",
            },
            {
                "instrument_id": "ins_1",
                "trading_date": date(2026, 8, 11),
                "daily_structure": "DOWN",
                "short_alignment": "ALIGNED_DOWN",
                "momentum": "NEGATIVE",
                "candidate_state": "DOWNTREND",
            },
            {
                "instrument_id": "ins_1",
                "trading_date": date(2026, 8, 12),
                "daily_structure": "DOWN",
                "short_alignment": "ALIGNED_DOWN",
                "momentum": "NEGATIVE",
                "candidate_state": "DOWNTREND",
            },
        ]
    )
    result = persisted_current_dimensions(
        frame,
        as_of_date=date(2026, 8, 12),
        session_ordinals={
            date(2026, 8, 10): 0,
            date(2026, 8, 11): 1,
            date(2026, 8, 12): 2,
        },
    )
    assert result["ins_1"]["ticker_state"] == "DOWNTREND"
    assert result["ins_1"]["raw_ticker_state"] == "DOWNTREND"


def test_gate12_persistence_resets_after_missing_exchange_session() -> None:
    frame = pd.DataFrame(
        [
            {
                "instrument_id": "ins_1",
                "trading_date": date(2026, 8, 10),
                "daily_structure": "UP",
                "short_alignment": "MIXED",
                "momentum": "POSITIVE",
                "candidate_state": "UPTREND",
            },
            {
                "instrument_id": "ins_1",
                "trading_date": date(2026, 8, 12),
                "daily_structure": "DOWN",
                "short_alignment": "ALIGNED_DOWN",
                "momentum": "NEGATIVE",
                "candidate_state": "DOWNTREND",
            },
        ]
    )
    result = persisted_current_dimensions(
        frame,
        as_of_date=date(2026, 8, 12),
        session_ordinals={
            date(2026, 8, 10): 0,
            date(2026, 8, 11): 1,
            date(2026, 8, 12): 2,
        },
    )
    assert result["ins_1"]["ticker_state"] == "DOWNTREND"
