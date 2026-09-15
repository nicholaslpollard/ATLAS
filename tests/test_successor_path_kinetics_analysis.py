from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

from packages.backtesting.successor_path_kinetics_analysis import (
    _first_hit_class,
    _net_return_with_cost,
    _path_record,
    _threshold_timing_curve,
)
from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.strategies.successor_path_kinetics_contract import (
    ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
    ACCEPTED_SELECTED_COMPARABLE_TOTAL,
    ACCEPTED_SELECTED_DAILY_COMPARABLE,
    ACCEPTED_SELECTED_INTRADAY_COMPARABLE,
    MOVE_THRESHOLDS,
    SESSION_HORIZONS,
    SUCCESSOR_PATH_KINETICS_FINGERPRINT,
    successor_path_kinetics_manifest,
)


def _instrument() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "session_date": [
                date(2026, 1, 2),
                date(2026, 1, 5),
                date(2026, 1, 6),
                date(2026, 1, 7),
                date(2026, 1, 8),
                date(2026, 1, 9),
            ],
            "open": [99.0, 100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [100.0, 101.5, 103.0, 104.0, 106.0, 107.0],
            "low": [98.0, 99.5, 99.0, 97.0, 96.0, 95.0],
            "close": [99.5, 101.0, 102.0, 103.0, 105.0, 103.0],
        }
    )


def _selected(direction: str = "LONG") -> SimpleNamespace:
    entry = 100.0
    exit_price = 103.0
    return SimpleNamespace(
        fold_id=1,
        policy_id="synthetic_v1",
        economic_family_id="synthetic",
        direction=direction,
        instrument_key="inst-1",
        ticker="SYN",
        session_date=date(2026, 1, 2),
        primary_net_return=_net_return_with_cost(direction, entry, exit_price, 10.0),
        stress_net_return=_net_return_with_cost(direction, entry, exit_price, 25.0),
        selector_score=0.001,
        fallback_level=1,
    )


def test_path_kinetics_contract_is_self_hash_bound() -> None:
    manifest = successor_path_kinetics_manifest()
    fingerprint = manifest.pop("fingerprint")
    assert fingerprint == SUCCESSOR_PATH_KINETICS_FINGERPRINT
    assert canonical_sha256(manifest) == fingerprint
    assert MOVE_THRESHOLDS == (0.01, 0.02, 0.03, 0.05)
    assert SESSION_HORIZONS == (1, 2, 3, 5, 10, 20)
    assert ACCEPTED_SELECTED_COMPARABLE_TOTAL == 36_254
    assert ACCEPTED_SELECTED_DAILY_COMPARABLE == 35_995
    assert ACCEPTED_SELECTED_INTRADAY_COMPARABLE == 259
    assert ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT == (
        "6f82ac0e55be43b8cf95fc362c7f292cb592b41c15ff897b24665470e95410f3"
    )


def test_long_path_uses_next_open_and_day_resolution_thresholds() -> None:
    record = _path_record(_selected("LONG"), _instrument(), 0)
    assert record["entry_session"] == date(2026, 1, 5)
    assert record["entry_price"] == 100.0
    assert record["available_sessions"] == 5
    assert np.isclose(record["close_return_h5"], 0.03)
    assert np.isclose(record["mfe_h5"], 0.07)
    assert np.isclose(record["mae_h5"], -0.05)
    assert record["first_favorable_2pct_session"] == 2
    assert record["first_adverse_2pct_session"] == 3
    assert record["first_hit_2pct_classification"] == "FAVORABLE_BEFORE_ADVERSE"
    assert record["first_favorable_5pct_session"] == 4
    assert record["first_adverse_5pct_session"] == 5
    assert record["close_return_h10"] is None


def test_short_path_flips_favorable_and_adverse_geometry() -> None:
    record = _path_record(_selected("SHORT"), _instrument(), 0)
    assert np.isclose(record["close_return_h5"], -0.03)
    assert np.isclose(record["mfe_h5"], 0.05)
    assert np.isclose(record["mae_h5"], -0.07)
    assert record["first_favorable_2pct_session"] == 3
    assert record["first_adverse_2pct_session"] == 2
    assert record["first_hit_2pct_classification"] == "ADVERSE_BEFORE_FAVORABLE"


def test_same_session_sequence_is_explicitly_ambiguous() -> None:
    assert _first_hit_class(2, 2) == "SAME_SESSION_AMBIGUOUS"
    assert _first_hit_class(1, 2) == "FAVORABLE_BEFORE_ADVERSE"
    assert _first_hit_class(2, 1) == "ADVERSE_BEFORE_FAVORABLE"
    assert _first_hit_class(1, None) == "FAVORABLE_ONLY"
    assert _first_hit_class(None, 1) == "ADVERSE_ONLY"
    assert _first_hit_class(None, None) == "NEITHER"


def test_threshold_curve_respects_horizon_and_ambiguity() -> None:
    paths = pd.DataFrame(
        [
            {
                "policy_id": "synthetic_v1",
                "economic_family_id": "synthetic",
                "direction": "LONG",
                "available_sessions": 20,
                "first_favorable_1pct_session": 1,
                "first_adverse_1pct_session": 3,
                "first_favorable_2pct_session": 2,
                "first_adverse_2pct_session": 2,
                "first_favorable_3pct_session": 4,
                "first_adverse_3pct_session": np.nan,
                "first_favorable_5pct_session": np.nan,
                "first_adverse_5pct_session": 5,
            },
            {
                "policy_id": "synthetic_v1",
                "economic_family_id": "synthetic",
                "direction": "LONG",
                "available_sessions": 20,
                "first_favorable_1pct_session": 2,
                "first_adverse_1pct_session": 1,
                "first_favorable_2pct_session": 4,
                "first_adverse_2pct_session": np.nan,
                "first_favorable_3pct_session": np.nan,
                "first_adverse_3pct_session": np.nan,
                "first_favorable_5pct_session": 10,
                "first_adverse_5pct_session": np.nan,
            },
        ]
    )
    curve = _threshold_timing_curve(paths)
    row = curve[
        np.isclose(curve["move_threshold"], 0.02)
        & (curve["horizon_sessions"] == 5)
    ].iloc[0]
    assert row["observations"] == 2
    assert np.isclose(row["favorable_hit_rate"], 1.0)
    assert np.isclose(row["adverse_hit_rate"], 0.5)
    assert np.isclose(row["same_session_ambiguous_rate"], 0.5)
    assert np.isclose(row["favorable_only_rate"], 0.5)
    assert np.isclose(row["median_first_favorable_session"], 3.0)
