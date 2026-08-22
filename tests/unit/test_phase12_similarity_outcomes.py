from __future__ import annotations

from datetime import date

import pandas as pd

from packages.analogues.outcomes import (
    attach_direction_adjusted_returns,
    extract_directional_paths,
)
from packages.analogues.policy import PHASE12_PER_INSTRUMENT_CAP, PHASE12_SIMILARITY_FEATURES
from packages.analogues.similarity import select_analogues
from packages.data.duckdb_connection import connect_utc
from packages.schemas.discovery_score import DiscoveryDirection


def _history_row(
    key: str,
    instrument: str,
    session: str,
    future: str,
    value: float,
    *,
    market: str = "BULL",
) -> dict[str, object]:
    row: dict[str, object] = {
        "observation_key": key,
        "session_date": session,
        "symbol": key,
        "instrument_id": instrument,
        "observation_close": 100.0,
        "future_date": future,
        "future_close": 100.0 * (1.0 + value / 100.0),
        "forward_return": value / 100.0,
        "market_regime_available": True,
        "market_regime_composite": market,
    }
    for name in PHASE12_SIMILARITY_FEATURES:
        row[name] = value
    return row


def test_similarity_selection_is_regime_matched_strictly_prior_and_instrument_capped() -> None:
    rows = [
        _history_row(f"k{x}", "i1", f"2026-01-0{x + 1}", "2026-01-08", float(x + 1))
        for x in range(5)
    ]
    rows.extend(
        [
            _history_row("k5", "i2", "2026-01-02", "2026-01-08", 6.0),
            _history_row("k6", "i3", "2026-01-03", "2026-01-08", 7.0),
            _history_row("wrong-regime", "i4", "2026-01-04", "2026-01-08", 0.001, market="BEAR"),
            _history_row("same-day-outcome", "i5", "2026-01-04", "2026-01-10", 0.001),
        ]
    )
    history = pd.DataFrame(rows)
    current = {name: 0.0 for name in PHASE12_SIMILARITY_FEATURES}
    con = connect_utc(":memory:")
    try:
        con.register("hist", history)
        selected, pool_rows = select_analogues(
            con,
            source_sql="hist",
            as_of_date=date(2026, 1, 10),
            market_state="BULL",
            current_features=current,
        )
    finally:
        con.close()
    assert pool_rows == 7
    assert "wrong-regime" not in selected["observation_key"].tolist()
    assert "same-day-outcome" not in selected["observation_key"].tolist()
    assert int(selected.groupby("instrument_id").size().max()) <= PHASE12_PER_INSTRUMENT_CAP
    assert selected[selected["instrument_id"] == "i1"].shape[0] == 3


def test_direction_adjustment_flips_bearish_outcomes() -> None:
    frame = pd.DataFrame({"forward_return": [0.10, -0.02]})
    bullish = attach_direction_adjusted_returns(frame, direction=DiscoveryDirection.BULLISH)
    bearish = attach_direction_adjusted_returns(frame, direction=DiscoveryDirection.BEARISH)
    assert bullish["direction_adjusted_return"].tolist() == [0.10, -0.02]
    assert bearish["direction_adjusted_return"].tolist() == [-0.10, 0.02]


def test_path_extraction_reproduces_three_session_endpoint_exactly() -> None:
    history = pd.DataFrame(
        {
            "observation_key": ["k1", "k2", "k3", "k4", "k5"],
            "instrument_id": ["i1"] * 5,
            "session_date": pd.to_datetime(
                ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
            ).date,
            "observation_close": [100.0, 101.0, 102.0, 103.0, 104.0],
        }
    )
    analogue = pd.DataFrame(
        {
            "observation_key": ["k1"],
            "instrument_id": ["i1"],
            "session_date": pd.to_datetime(["2026-01-02"]).date,
            "future_date": pd.to_datetime(["2026-01-07"]).date,
            "observation_close": [100.0],
            "future_close": [103.0],
            "forward_return": [0.03],
        }
    )
    con = connect_utc(":memory:")
    try:
        con.register("hist", history)
        path = extract_directional_paths(
            con,
            source_sql="hist",
            analogue_frame=analogue,
            direction=DiscoveryDirection.BULLISH,
        )
    finally:
        con.close()
    assert len(path) == 1
    assert abs(float(path.iloc[0]["direction_return_1"]) - 0.01) < 1e-12
    assert abs(float(path.iloc[0]["direction_return_2"]) - 0.02) < 1e-12
    assert abs(float(path.iloc[0]["direction_return_3"]) - 0.03) < 1e-12
