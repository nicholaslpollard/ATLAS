from __future__ import annotations

from datetime import date
from pathlib import Path, PureWindowsPath

import duckdb
import pandas as pd
import pytest

import packages.backtesting.successor_selected_daily_path_analysis as path_analysis
from packages.backtesting.successor_selected_daily_path_analysis import (
    _copy_query_atomic,
    _path_query,
    _prepare_path_relations,
    _threshold_query,
    selected_daily_path_root,
)
from packages.backtesting.successor_optionworthiness_analysis import conditioning_root
from packages.strategies.successor_selected_daily_path_contract import (
    AUTHORITY,
    MOVE_THRESHOLDS,
    PATH_HORIZON_SESSIONS,
    successor_selected_daily_path_manifest,
)


def _bars() -> pd.DataFrame:
    rows = [
        (date(2026, 1, 2), 100.0, 100.0, 100.0, 100.0),
        (date(2026, 1, 5), 100.0, 101.0, 99.5, 100.5),
        (date(2026, 1, 6), 100.5, 102.5, 99.0, 102.0),
        (date(2026, 1, 7), 102.0, 103.0, 97.5, 101.0),
        (date(2026, 1, 8), 101.0, 105.5, 98.0, 104.0),
        (date(2026, 1, 9), 104.0, 104.0, 99.0, 103.0),
    ]
    return pd.DataFrame(
        [
            {
                "instrument_id": "I1",
                "ticker": "TEST",
                "session_date": session,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
            for session, open_, high, low, close in rows
        ]
    )


def _selected() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "fold_id": 1,
                "policy_id": "test_policy",
                "economic_family_id": "test_family",
                "native_timeframe": "1d",
                "instrument_key": "I1",
                "ticker": "TEST",
                "session_date": date(2026, 1, 2),
                "direction": "LONG",
                "primary_net_return": 0.02,
                "stress_net_return": 0.018,
            }
        ]
    )


def _prepare(con: duckdb.DuckDBPyConnection, bars: pd.DataFrame | None = None) -> dict[str, int]:
    con.register("daily_bars", _bars() if bars is None else bars)
    con.register("selected", _selected())
    original = path_analysis.EXPECTED_SELECTED_DAILY_COMPARABLE
    path_analysis.EXPECTED_SELECTED_DAILY_COMPARABLE = 1
    try:
        return _prepare_path_relations(con, "daily_bars")
    finally:
        path_analysis.EXPECTED_SELECTED_DAILY_COMPARABLE = original


def test_contract_is_descriptive_and_authority_closed() -> None:
    manifest = successor_selected_daily_path_manifest()
    assert PATH_HORIZON_SESSIONS == 5
    assert MOVE_THRESHOLDS == (0.01, 0.02, 0.03, 0.05)
    assert manifest["population"] == "WALK_FORWARD_SELECTED_COMPARABLE_DAILY_ONLY"
    assert manifest["daily_bar_first_touch_semantics"]["same_session_both_sides"] == (
        "SAME_SESSION_COLLISION_UNORDERED"
    )
    assert manifest["intraday_routes"] == "DEFERRED_TO_SEPARATE_MINUTE_PATH_DIAGNOSTIC"
    assert AUTHORITY["consumed_master_rows_permitted"] == 0
    assert AUTHORITY["future_blind_rows_permitted"] == 0
    assert AUTHORITY["paper_authority"] is False
    assert AUTHORITY["live_authority"] is False
    assert AUTHORITY["strategy_promotion_authority"] is False
    assert AUTHORITY["option_trading_authority"] is False


def test_long_five_session_path_and_first_touch(tmp_path: Path) -> None:
    con = duckdb.connect()
    try:
        prep = _prepare(con)
        assert prep["selected_instruments"] == 1
        assert prep["ordered_daily_rows"] == 6
        assert prep["selected_positions"] == 1
        assert prep["targeted_daily_rows"] == 6

        path = tmp_path / "path.parquet"
        assert _copy_query_atomic(con, _path_query(), path) == 1
        row = con.execute(f"SELECT * FROM read_parquet('{path.as_posix()}')").fetchdf().iloc[0]
        assert float(row["gross_return_5"]) == pytest.approx(0.03)
        assert float(row["mfe_5"]) == pytest.approx(0.055)
        assert float(row["adverse_excursion_5"]) == pytest.approx(0.025)
        assert float(row["peak_giveback"]) == pytest.approx(0.025)
        assert float(row["exit_capture_ratio"]) == pytest.approx(0.03 / 0.055)

        threshold = tmp_path / "threshold.parquet"
        assert _copy_query_atomic(con, _threshold_query(path), threshold) == 4
        two = con.execute(
            f"SELECT * FROM read_parquet('{threshold.as_posix()}') WHERE move_threshold=0.02"
        ).fetchdf().iloc[0]
        assert int(two["first_favorable_session"]) == 2
        assert int(two["first_adverse_session"]) == 3
        assert two["first_touch_class"] == "FAVORABLE_FIRST"

        five = con.execute(
            f"SELECT * FROM read_parquet('{threshold.as_posix()}') WHERE move_threshold=0.05"
        ).fetchdf().iloc[0]
        assert int(five["first_favorable_session"]) == 4
        assert pd.isna(five["first_adverse_session"])
        assert five["first_touch_class"] == "FAVORABLE_ONLY"
    finally:
        con.close()


def test_same_session_collision_is_not_ordered(tmp_path: Path) -> None:
    bars = _bars()
    bars.loc[bars["session_date"] == date(2026, 1, 6), "low"] = 97.5
    con = duckdb.connect()
    try:
        _prepare(con, bars)
        path = tmp_path / "path.parquet"
        _copy_query_atomic(con, _path_query(), path)
        threshold = tmp_path / "threshold.parquet"
        _copy_query_atomic(con, _threshold_query(path), threshold)
        two = con.execute(
            f"SELECT * FROM read_parquet('{threshold.as_posix()}') WHERE move_threshold=0.02"
        ).fetchdf().iloc[0]
        assert int(two["first_favorable_session"]) == 2
        assert int(two["first_adverse_session"]) == 2
        assert two["first_touch_class"] == "SAME_SESSION_COLLISION_UNORDERED"
    finally:
        con.close()


def test_projection_excludes_unselected_instruments() -> None:
    bars = _bars()
    other = _bars().copy()
    other["instrument_id"] = "I2"
    other["ticker"] = "OTHER"
    bars = pd.concat([bars, other], ignore_index=True)
    con = duckdb.connect()
    try:
        prep = _prepare(con, bars)
        assert prep["selected_instruments"] == 1
        assert prep["ordered_daily_rows"] == 6
        assert prep["targeted_daily_rows"] == 6
        instruments = con.execute(
            "SELECT DISTINCT instrument_id FROM targeted_daily_bars"
        ).fetchall()
        assert instruments == [("I1",)]
    finally:
        con.close()


def test_output_root_stays_windows_legacy_safe(tmp_path: Path) -> None:
    root = selected_daily_path_root(tmp_path)
    conditioning = conditioning_root(tmp_path)
    assert root.parent.parent == conditioning
    assert "optionworthiness_v1" not in root.parts

    relative = root.relative_to(tmp_path.resolve())
    representative = PureWindowsPath(
        r"C:\Users\cyberdyne\Desktop\ATLAS",
        *relative.parts,
        "selected_daily_path_contract.json",
    )
    assert len(str(representative)) <= 248
