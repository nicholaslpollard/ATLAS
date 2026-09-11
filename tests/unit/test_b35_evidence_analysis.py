from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

from packages.backtesting.b35_evidence_analysis import (
    _bootstrap_lcb,
    _empirical_lower_quantile,
    _normalization_query,
    _selector_assignments_sql,
    build_walk_forward_folds,
)
from packages.strategies.b35_conditional_evidence_contract import (
    ROLLING_TRAIN_SESSIONS,
    SESSION_CLUSTER_BOOTSTRAP_DRAWS,
    WALK_FORWARD_EMBARGO_SESSIONS,
    WALK_FORWARD_TEST_SESSIONS,
)


def test_empirical_lower_quantile_uses_lower_order_statistic() -> None:
    values = np.arange(1.0, 1001.0)
    assert _empirical_lower_quantile(values, 0.05) == 50.0


def test_session_cluster_bootstrap_is_deterministic() -> None:
    sums = np.asarray([1.0, -0.5, 2.0, 0.25], dtype=float)
    counts = np.asarray([2, 1, 4, 1], dtype=np.int64)
    first = _bootstrap_lcb(sums, counts, seed_material="same-cell")
    second = _bootstrap_lcb(sums, counts, seed_material="same-cell")
    assert SESSION_CLUSTER_BOOTSTRAP_DRAWS == 1000
    assert first == second
    assert first is not None
    assert np.isfinite(first)


def test_walk_forward_folds_use_complete_xnys_sessions() -> None:
    start = date(2016, 1, 4)
    end = date(2026, 4, 30)
    folds = build_walk_forward_folds(start, end)
    assert len(folds) > 20
    first = folds[0]
    calendar = xcals.get_calendar("XNYS")
    sessions = [
        stamp.date()
        for stamp in calendar.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    ]
    assert first.train_start == sessions[0]
    assert (
        sessions.index(first.train_end) - sessions.index(first.train_start) + 1
        == ROLLING_TRAIN_SESSIONS
    )
    assert (
        sessions.index(first.embargo_session)
        == sessions.index(first.train_end) + WALK_FORWARD_EMBARGO_SESSIONS
    )
    assert (
        sessions.index(first.test_end) - sessions.index(first.test_start) + 1
        == WALK_FORWARD_TEST_SESSIONS
    )


def test_normalization_reads_numeric_cost_keys_and_derives_net_r(tmp_path: Path) -> None:
    record = {
        "context": {
            "strategy_id": "b34_opening_range_breakout_15m_v1",
            "symbol": "TEST",
            "session_date": "2024-01-03",
            "prior_market_regime": "UNAVAILABLE",
            "prior_close_price": "20_TO_100",
            "median_dollar_volume_20": "50M_TO_250M",
            "realized_volatility_20": "25_TO_50PCT",
            "prior_trend_20_50": "UP",
            "absolute_gap_pct": "LT_2PCT",
            "premarket_relvol_20": "2_TO_4",
            "premarket_dollar_volume": "1M_TO_5M",
            "opening_range_width_pct": "1_TO_2PCT",
            "signal_time_et": "0945_TO_1000",
            "hvd_volume_ratio": "UNAVAILABLE",
            "setup_intensity_bucket": "1_TO_2PCT",
        },
        "outcome": {
            "direction": "LONG",
            "comparable": True,
            "status": "EXITED",
            "entry_bar_timestamp_utc": "2024-01-03T14:46:00+00:00",
            "exit_bar_timestamp_utc": "2024-01-03T15:16:00+00:00",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "target_price": 102.0,
            "exit_price": 102.0,
            "exit_reason": "TARGET_2R",
            "risk_multiple": 2.0,
            "maximum_favorable_excursion": 0.02,
            "maximum_adverse_excursion": -0.002,
            "net_directional_returns_by_cost_bps": {
                "0": 0.0200,
                "10": 0.0190,
                "25": 0.0175,
                "50": 0.0150,
                "100": 0.0100,
            },
        },
    }
    path = tmp_path / "one.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    conn = duckdb.connect()
    row = conn.execute(_normalization_query(path)).fetchdf().iloc[0]
    assert row["strategy_id"] == "b34_opening_range_breakout_15m_v1"
    assert row["net_return_50"] == pytest.approx(0.015)
    assert row["net_r_50"] == pytest.approx(1.5)
    assert row["holding_minutes"] == 30
    assert row["selector_key_1"].startswith("b34_opening_range_breakout_15m_v1|")


def test_supported_negative_specific_cell_is_not_rescued_by_broader_positive_cell(
    tmp_path: Path,
) -> None:
    day = date(2024, 1, 3)
    rows = pd.DataFrame(
        [
            {
                "session_date": day,
                "strategy_id": "s1",
                "symbol": "A",
                "direction": "LONG",
                "comparable": True,
                "status": "EXITED",
                "entry_time_utc": datetime(2024, 1, 3, 15, 0, tzinfo=timezone.utc),
                "exit_time_utc": datetime(2024, 1, 3, 16, 0, tzinfo=timezone.utc),
                "net_return_0": 0.01,
                "net_return_10": 0.009,
                "net_return_25": 0.008,
                "net_return_50": 0.007,
                "net_return_100": 0.005,
                "net_r_50": 0.7,
                "selector_key_1": "specific-negative",
                "selector_key_2": "broader-positive",
                "selector_key_3": "l3",
                "selector_key_4": "l4",
                "selector_key_5": "l5",
            },
            {
                "session_date": day,
                "strategy_id": "s1",
                "symbol": "B",
                "direction": "LONG",
                "comparable": True,
                "status": "EXITED",
                "entry_time_utc": datetime(2024, 1, 3, 15, 1, tzinfo=timezone.utc),
                "exit_time_utc": datetime(2024, 1, 3, 16, 1, tzinfo=timezone.utc),
                "net_return_0": 0.01,
                "net_return_10": 0.009,
                "net_return_25": 0.008,
                "net_return_50": 0.007,
                "net_return_100": 0.005,
                "net_r_50": 0.7,
                "selector_key_1": "specific-unsupported",
                "selector_key_2": "broader-positive",
                "selector_key_3": "l3",
                "selector_key_4": "l4",
                "selector_key_5": "l5",
            },
        ]
    )
    conn = duckdb.connect()
    conn.register("source_rows", rows)
    path = tmp_path / "opportunities.parquet"
    safe_path = str(path).replace("\\", "/")
    conn.execute(f"COPY source_rows TO '{safe_path}' (FORMAT PARQUET)")
    conn.register(
        "folds",
        pd.DataFrame([{"fold_id": 1, "test_start": day, "test_end": day}]),
    )
    scores = pd.DataFrame(
        [
            {
                "fold_id": 1,
                "hierarchy_level": 1,
                "cell_key": "specific-negative",
                "minimum_support": True,
                "score_lcb_net_r_50": -0.1,
            },
            {
                "fold_id": 1,
                "hierarchy_level": 1,
                "cell_key": "specific-unsupported",
                "minimum_support": False,
                "score_lcb_net_r_50": None,
            },
            {
                "fold_id": 1,
                "hierarchy_level": 2,
                "cell_key": "broader-positive",
                "minimum_support": True,
                "score_lcb_net_r_50": 0.2,
            },
        ]
    )
    conn.register("selector_scores", scores)
    result = conn.execute(_selector_assignments_sql(path)).fetchdf().sort_values("symbol")
    first = result.iloc[0]
    second = result.iloc[1]
    assert first["symbol"] == "A"
    assert int(first["fallback_level"]) == 1
    assert first["selector_score"] == pytest.approx(-0.1)
    assert bool(first["selected"]) is False
    assert second["symbol"] == "B"
    assert int(second["fallback_level"]) == 2
    assert second["selector_score"] == pytest.approx(0.2)
    assert bool(second["selected"]) is True
