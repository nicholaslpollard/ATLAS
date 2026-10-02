from __future__ import annotations

from datetime import UTC, datetime

from packages.core.market_calendar import get_market_calendar
from packages.simulation.multiyear_intraday_stock_exit_clock_v1 import (
    resolve_intraday_exit_case,
)


def _case(
    *,
    case_id: str,
    daily_disposition: str,
    decision: str = "2025-01-06T14:35:00+00:00",
) -> dict:
    return {
        "case_id": case_id,
        "year": "2025",
        "ticker": "ABC",
        "policy_id": "p1",
        "economic_family_id": "family",
        "signal_session": "2025-01-03",
        "entry_session": "2025-01-06",
        "decision_at_utc": decision,
        "raw_stock_open": "100",
        "stop_fraction": "0.03",
        "target_fraction": "0.05",
        "daily_exit_disposition": daily_disposition,
        "daily_exit_session": "2025-01-06",
        "daily_exit_session_offset": 1,
        "daily_gap_through_stop": False,
        "daily_gap_through_target": False,
        "daily_same_session_collision": False,
        "symbol": "ABC",
        "expiration": "2025-02-21",
        "strike": "100",
        "right": "call",
        "option_symbol": "ABC250221C00100000",
    }


def _bar(stamp: str, *, open_: float, high: float, low: float, close: float) -> dict:
    return {
        "timestamp_utc": datetime.fromisoformat(stamp).astimezone(UTC),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
    }


def test_stop_before_0935_is_not_option_expression_ready():
    result = resolve_intraday_exit_case(
        _case(case_id="early-stop", daily_disposition="STOP"),
        [
            _bar(
                "2025-01-06T14:33:00+00:00",
                open_=100,
                high=100.2,
                low=96.8,
                close=97.2,
            )
        ],
        calendar=get_market_calendar(),
    )
    assert result["minute_exit_disposition"] == "STOP"
    assert result["causal_exit_action_at_utc"] == "2025-01-06T14:34:00+00:00"
    assert result["status"] == "STOCK_EXIT_AT_OR_BEFORE_OPTION_DECISION"
    assert result["option_expression_clock_ready"] is False
    assert result["entry_quote_demand"] is None
    assert result["exit_quote_demand"] is None


def test_target_after_0935_emits_entry_and_exit_quote_demands():
    result = resolve_intraday_exit_case(
        _case(case_id="later-target", daily_disposition="TARGET"),
        [
            _bar(
                "2025-01-06T15:01:00+00:00",
                open_=103,
                high=105.2,
                low=102.5,
                close=105.0,
            )
        ],
        calendar=get_market_calendar(),
    )
    assert result["minute_exit_disposition"] == "TARGET"
    assert result["causal_exit_action_at_utc"] == "2025-01-06T15:02:00+00:00"
    assert result["status"] == "INTRADAY_EXIT_CLOCK_READY"
    assert result["option_expression_clock_ready"] is True
    assert result["entry_quote_demand"]["time_of_day_et"] == "09:35:00.000"
    assert result["exit_quote_demand"]["time_of_day_et"] == "10:02:00.000"


def test_minute_path_can_reorder_daily_collision_without_silent_rewrite():
    result = resolve_intraday_exit_case(
        _case(case_id="reordered", daily_disposition="STOP"),
        [
            _bar(
                "2025-01-06T14:40:00+00:00",
                open_=100,
                high=105.2,
                low=99.0,
                close=104.8,
            ),
            _bar(
                "2025-01-06T15:00:00+00:00",
                open_=104.8,
                high=105.0,
                low=96.5,
                close=97.0,
            ),
        ],
        calendar=get_market_calendar(),
    )
    assert result["minute_exit_disposition"] == "TARGET"
    assert result["daily_vs_minute_disposition_changed"] is True
    assert result["status"] == "MINUTE_PATH_REORDERS_DAILY_EXIT"
    assert result["option_expression_clock_ready"] is True


def test_same_minute_collision_remains_adverse_first():
    result = resolve_intraday_exit_case(
        _case(case_id="same-minute", daily_disposition="STOP"),
        [
            _bar(
                "2025-01-06T14:45:00+00:00",
                open_=100,
                high=106.0,
                low=96.0,
                close=101.0,
            )
        ],
        calendar=get_market_calendar(),
    )
    assert result["minute_exit_disposition"] == "STOP"
    assert result["minute_same_bar_collision_adverse_first"] is True
    assert result["status"] == "INTRADAY_EXIT_CLOCK_READY"


def test_time_exit_uses_official_exchange_close_without_minute_rows():
    result = resolve_intraday_exit_case(
        _case(case_id="time", daily_disposition="TIME"),
        (),
        calendar=get_market_calendar(),
    )
    assert result["minute_exit_disposition"] == "TIME"
    assert result["causal_exit_action_at_utc"] == "2025-01-06T21:00:00+00:00"
    assert result["status"] == "INTRADAY_EXIT_CLOCK_READY"
    assert result["exit_quote_demand"]["time_of_day_et"] == "16:00:00.000"


def test_missing_stop_target_minute_source_is_explicit():
    result = resolve_intraday_exit_case(
        _case(case_id="missing", daily_disposition="STOP"),
        (),
        calendar=get_market_calendar(),
    )
    assert result["status"] == "MINUTE_SOURCE_SESSION_MISSING"
    assert result["option_expression_clock_ready"] is False
