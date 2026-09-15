from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import duckdb
import numpy as np
import pandas as pd
import pytest

from packages.backtesting.successor_orb_stocks_in_play_literature_v2_development import (
    _group_token,
    _rank_selected_candidates,
    build_prior_daily_features,
    evaluate_selected_case,
)
from packages.strategies.successor_orb_stocks_in_play_literature_v2_development_contract import (
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_CONTRACT,
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT,
    contract_fingerprint,
)


def _write_parquet(path, frame: pd.DataFrame) -> None:
    conn = duckdb.connect(":memory:")
    conn.register("frame", frame)
    try:
        conn.execute(f"COPY frame TO '{str(path).replace(chr(39), chr(39) * 2)}' (FORMAT PARQUET)")
    finally:
        conn.unregister("frame")
        conn.close()


def test_development_contract_is_frozen_and_grants_no_authority() -> None:
    assert contract_fingerprint() == ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT
    assert ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT == (
        "2a62b54a5413a1ce62e19ae1489df36095350ba53e4dad2d4784fb3b083fe542"
    )
    contract = ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_CONTRACT
    assert contract["scope"] == "DEVELOPMENT_ONLY"
    assert contract["primary_cost_bps"] == 50
    assert contract["stress_cost_bps"] == 100
    assert contract["restart_safe_group_artifacts"] is True
    for field in (
        "consumed_master_reads",
        "future_blind_reads",
        "provider_reads",
        "broker_reads",
        "broker_writes",
    ):
        assert contract[field] == 0
    for field in (
        "paper_authority",
        "live_authority",
        "promotion_authority",
        "confluence_authority",
        "option_trading_authority",
    ):
        assert contract[field] is False


def _daily_rows(*, current_volume: float = 2_000_000.0, current_high: float = 102.0) -> pd.DataFrame:
    start = date(2026, 3, 2)
    sessions = [start + timedelta(days=index) for index in range(15)]
    rows = []
    for index, session in enumerate(sessions):
        base = 100.0 + index * 0.2
        rows.append(
            {
                "instrument_id": "iid-1",
                "ticker": "XYZ",
                "session_date": session,
                "open": base,
                "high": current_high if index == 14 else base + 1.0,
                "low": base - 1.0,
                "close": base + 0.2,
                "volume": current_volume if index == 14 else 1_500_000.0 + index * 10_000.0,
                "unadjusted_close": base + 0.2,
            }
        )
    return pd.DataFrame(rows)


def test_daily_features_shift_both_volume_and_atr_before_current_session() -> None:
    baseline = build_prior_daily_features(_daily_rows(current_volume=2_000_000.0, current_high=102.0))
    changed = build_prior_daily_features(_daily_rows(current_volume=99_000_000.0, current_high=500.0))

    assert baseline["prior_average_daily_share_volume_14"].iloc[:14].isna().all()
    assert baseline["prior_atr_14_dollars"].iloc[:14].isna().all()
    expected_volume = np.mean([1_500_000.0 + index * 10_000.0 for index in range(14)])
    assert baseline.iloc[14]["prior_average_daily_share_volume_14"] == pytest.approx(expected_volume)
    assert baseline.iloc[14]["prior_atr_14_dollars"] > 0.0
    assert changed.iloc[14]["prior_average_daily_share_volume_14"] == pytest.approx(
        baseline.iloc[14]["prior_average_daily_share_volume_14"]
    )
    assert changed.iloc[14]["prior_atr_14_dollars"] == pytest.approx(
        baseline.iloc[14]["prior_atr_14_dollars"]
    )


def test_cross_section_rank_is_top20_and_doji_consumes_its_rank_slot(tmp_path) -> None:
    sessions = [date(2026, 3, 2) + timedelta(days=index) for index in range(15)]
    opening_rows = []
    daily_rows = []
    for ticker_index in range(21):
        ticker = f"T{ticker_index:02d}"
        group_token = _group_token((ticker,))
        for session_index, session in enumerate(sessions):
            current_volume = 300.0 - ticker_index * 5.0 if session_index == 14 else 100.0
            opening_rows.append(
                {
                    "group_token": group_token,
                    "unit_id": f"unit-{ticker_index:02d}",
                    "ticker": ticker,
                    "session_date": session,
                    "opening_price": 10.0,
                    "opening_close": (
                        10.0 if ticker_index == 0 and session_index == 14 else 10.2
                    ),
                    "opening_range_high": 10.4,
                    "opening_range_low": 9.8,
                    "opening_five_minute_volume": current_volume,
                    "opening_first_timestamp_utc": datetime(2026, 3, 16, 13, 30, tzinfo=UTC),
                    "opening_last_timestamp_utc": datetime(2026, 3, 16, 13, 34, tzinfo=UTC),
                    "opening_bar_count": 5,
                }
            )
            daily_rows.append(
                {
                    "instrument_id": f"iid-{ticker_index:02d}",
                    "ticker": ticker,
                    "session_date": session,
                    "prior_average_daily_share_volume_14": 2_000_000.0,
                    "prior_atr_14_dollars": 1.0,
                }
            )

    opening_path = tmp_path / "opening.parquet"
    daily_path = tmp_path / "daily.parquet"
    _write_parquet(opening_path, pd.DataFrame(opening_rows))
    _write_parquet(daily_path, pd.DataFrame(daily_rows))

    selected_path, counts = _rank_selected_candidates([opening_path], daily_path, tmp_path)
    conn = duckdb.connect(":memory:")
    try:
        selected = conn.execute(
            f"SELECT * FROM read_parquet('{selected_path.as_posix()}') ORDER BY daily_relvol_rank"
        ).fetchdf()
    finally:
        conn.close()
    assert counts["selected_top20_rows"] == 20
    assert counts["doji_abstentions"] == 1
    assert len(selected) == 20
    assert selected.iloc[0]["ticker"] == "T00"
    assert selected.iloc[0]["direction"] == "DOJI_ABSTAIN"
    assert "T20" not in set(selected["ticker"])
    assert list(selected["daily_relvol_rank"]) == list(range(1, 21))


def _candidate() -> pd.Series:
    return pd.Series(
        {
            "instrument_id": "iid-1",
            "ticker": "XYZ",
            "session_date": date(2026, 4, 1),
            "direction": "LONG",
            "daily_relvol_rank": 1,
            "opening_relvol_14": 2.0,
            "prior_average_daily_share_volume_14": 2_000_000.0,
            "prior_atr_14_dollars": 2.0,
            "opening_price": 100.0,
            "opening_close": 100.8,
            "opening_range_high": 101.0,
            "opening_range_low": 99.5,
            "opening_last_timestamp_utc": pd.Timestamp("2026-04-01T13:34:00Z"),
        }
    )


def _bars(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "XYZ",
                "session_date": date(2026, 4, 1),
                "timestamp_utc": pd.Timestamp(stamp),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000.0,
            }
            for stamp, open_price, high, low, close in rows
        ]
    )


def test_same_minute_entry_and_stop_is_noncomparable() -> None:
    candidate = _candidate()
    bars = _bars(
        [
            ("2026-04-01T13:35:00Z", 100.9, 101.2, 100.7, 101.0),
            ("2026-04-01T19:59:00Z", 101.0, 101.2, 100.9, 101.1),
        ]
    )
    outcome, thresholds = evaluate_selected_case(candidate, bars)
    assert outcome["status"] == "ENTRY_STOP_SAME_MINUTE_UNORDERED"
    assert outcome["comparable"] is False
    assert outcome["entry_price"] == pytest.approx(101.0)
    assert outcome["stop_loss_price"] == pytest.approx(100.8)
    assert thresholds == []


def test_comparable_case_excludes_entry_and_exit_extremes_but_includes_terminal_return() -> None:
    candidate = _candidate()
    bars = _bars(
        [
            ("2026-04-01T13:35:00Z", 100.9, 101.2, 100.9, 101.1),
            ("2026-04-01T13:36:00Z", 101.1, 102.5, 100.95, 102.0),
            ("2026-04-01T19:59:00Z", 102.0, 110.0, 90.0, 103.02),
        ]
    )
    outcome, thresholds = evaluate_selected_case(candidate, bars)
    assert outcome["status"] == "COMPARABLE"
    assert outcome["entry_price"] == pytest.approx(101.0)
    assert outcome["exit_price"] == pytest.approx(103.02)
    assert outcome["gross_return"] == pytest.approx(0.02)
    assert outcome["path_mfe"] == pytest.approx(0.02)
    assert outcome["path_adverse"] == pytest.approx(1.0 - 100.95 / 101.0)
    assert outcome["net_return_50"] < outcome["gross_return"]
    two_pct = next(row for row in thresholds if abs(float(row["move_threshold"]) - 0.02) < 1e-12)
    assert two_pct["first_favorable_minutes"] == pytest.approx(384.0)
    assert two_pct["first_touch_class"] == "FAVORABLE_ONLY"
