from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from packages.backtesting.successor_selected_minute_path_analysis import _analyze_case_bars
from packages.strategies.successor_selected_daily_path_contract import MOVE_THRESHOLDS
from packages.strategies.successor_selected_minute_path_contract import (
    AUTHORITY,
    EXPECTED_POLICY_ID,
    EXPECTED_SELECTED_MINUTE_COMPARABLE,
    successor_selected_minute_path_manifest,
)


def _case(*, direction: str = "LONG", gross: float = 0.015, exit_minute: int = 3) -> pd.Series:
    entry = pd.Timestamp("2026-01-05T14:45:00Z")
    exit_time = entry + pd.Timedelta(minutes=exit_minute)
    return pd.Series(
        {
            "case_id": "case-1",
            "fold_id": 1,
            "policy_id": EXPECTED_POLICY_ID,
            "economic_family_id": "opening_range_breakout",
            "instrument_key": "TEST",
            "session_date": date(2026, 1, 5),
            "direction": direction,
            "entry_time_utc": entry,
            "exit_time_utc": exit_time,
            "holding_minutes": exit_minute,
            "gross_return": gross,
            "primary_net_return": gross - 0.005,
            "stress_net_return": gross - 0.010,
            "mfe": 0.03,
            "mae": -0.02,
        }
    )


def _bars(rows: list[tuple[int, float, float, float, float]]) -> pd.DataFrame:
    entry = pd.Timestamp("2026-01-05T14:45:00Z")
    return pd.DataFrame(
        [
            {
                "case_id": "case-1",
                "symbol": "TEST",
                "session_date": date(2026, 1, 5),
                "timestamp_utc": entry + pd.Timedelta(minutes=minute),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
            for minute, open_, high, low, close in rows
        ]
    )


def test_contract_is_descriptive_and_authority_closed() -> None:
    manifest = successor_selected_minute_path_manifest()
    assert EXPECTED_SELECTED_MINUTE_COMPARABLE == 259
    assert EXPECTED_POLICY_ID == "orb_15m_close_retest_v2"
    assert MOVE_THRESHOLDS == (0.01, 0.02, 0.03, 0.05)
    assert manifest["population"] == "WALK_FORWARD_SELECTED_COMPARABLE_MINUTE_ONLY"
    assert manifest["minute_first_touch_semantics"]["same_minute_both_sides"] == (
        "SAME_MINUTE_COLLISION_UNORDERED"
    )
    assert manifest["minute_first_touch_semantics"]["exit_bar"].startswith(
        "DO_NOT_USE_EXIT_BAR_HIGH_LOW"
    )
    assert AUTHORITY["consumed_master_rows_permitted"] == 0
    assert AUTHORITY["future_blind_rows_permitted"] == 0
    assert AUTHORITY["paper_authority"] is False
    assert AUTHORITY["live_authority"] is False
    assert AUTHORITY["strategy_promotion_authority"] is False
    assert AUTHORITY["option_trading_authority"] is False


def test_long_minute_path_first_touch_and_exit_bar_extremes_are_excluded() -> None:
    case = _case(direction="LONG", gross=0.015, exit_minute=3)
    bars = _bars(
        [
            (0, 100.0, 100.6, 99.6, 100.2),
            (1, 100.2, 102.2, 99.5, 101.8),
            (2, 101.8, 103.4, 97.4, 100.5),
            # The exit bar contains a post-exit-looking 10% high. It must not
            # create a 5% threshold touch; only the retained +1.5% exit return applies.
            (3, 100.5, 110.0, 90.0, 105.0),
        ]
    )
    path, thresholds = _analyze_case_bars(case, bars)
    assert path["entry_price"] == pytest.approx(100.0)
    assert path["path_mfe_before_exit_plus_terminal"] == pytest.approx(0.034)
    assert path["path_adverse_before_exit_plus_terminal"] == pytest.approx(0.026)
    assert path["exit_bar_extremes_excluded"] is True

    by_threshold = {float(row["move_threshold"]): row for row in thresholds}
    assert by_threshold[0.01]["first_favorable_minutes"] == 1
    assert by_threshold[0.02]["first_favorable_minutes"] == 1
    assert by_threshold[0.02]["first_adverse_minutes"] == 2
    assert by_threshold[0.02]["first_touch_class"] == "FAVORABLE_FIRST"
    assert by_threshold[0.03]["first_favorable_minutes"] == 2
    assert by_threshold[0.05]["first_favorable_minutes"] is None
    assert by_threshold[0.05]["first_adverse_minutes"] is None


def test_same_minute_two_sided_touch_is_unordered() -> None:
    case = _case(direction="LONG", gross=0.005, exit_minute=2)
    bars = _bars(
        [
            (0, 100.0, 100.5, 99.5, 100.0),
            (1, 100.0, 102.5, 97.5, 100.0),
            (2, 100.0, 101.0, 99.0, 100.5),
        ]
    )
    _path, thresholds = _analyze_case_bars(case, bars)
    two = {float(row["move_threshold"]): row for row in thresholds}[0.02]
    assert two["first_favorable_minutes"] == 1
    assert two["first_adverse_minutes"] == 1
    assert two["first_touch_class"] == "SAME_MINUTE_COLLISION_UNORDERED"


def test_short_path_uses_low_as_favorable_and_high_as_adverse() -> None:
    case = _case(direction="SHORT", gross=0.012, exit_minute=2)
    bars = _bars(
        [
            (0, 100.0, 100.4, 99.6, 99.8),
            (1, 99.8, 101.5, 97.0, 98.0),
            (2, 98.0, 105.0, 90.0, 98.8),
        ]
    )
    path, thresholds = _analyze_case_bars(case, bars)
    assert path["path_mfe_before_exit_plus_terminal"] == pytest.approx(0.03)
    assert path["path_adverse_before_exit_plus_terminal"] == pytest.approx(0.015)
    by_threshold = {float(row["move_threshold"]): row for row in thresholds}
    assert by_threshold[0.02]["first_favorable_minutes"] == 1
    assert by_threshold[0.01]["first_adverse_minutes"] == 1


def test_holding_minutes_must_match_retained_entry_exit_geometry() -> None:
    case = _case(direction="LONG", gross=0.01, exit_minute=2)
    case["holding_minutes"] = 3
    bars = _bars(
        [
            (0, 100.0, 100.5, 99.5, 100.0),
            (1, 100.0, 101.0, 99.0, 100.5),
            (2, 100.5, 101.5, 100.0, 101.0),
        ]
    )
    with pytest.raises(Exception, match="holding minutes drifted"):
        _analyze_case_bars(case, bars)
