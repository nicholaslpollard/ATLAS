from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from packages.backtesting.successor_conditioning_analysis import (
    _materialize_condition_cells,
    _sql_path,
)


def test_condition_cell_materialization_includes_direction_and_interactions(
    tmp_path: Path,
) -> None:
    rows = []
    for index in range(80):
        rows.append(
            {
                "policy_id": "p1",
                "economic_family_id": "family1",
                "native_timeframe": "1m",
                "instrument_key": f"iid-{index % 25:02d}",
                "ticker": f"T{index % 25:02d}",
                "session_date": date(2020, 1, 2 + (index % 30)),
                "calendar_year": 2020,
                "direction": "LONG",
                "eligible_opportunity": True,
                "status": "EXITED",
                "comparable": True,
                "gross_return": 0.02,
                "net_return_0": 0.02,
                "net_return_10": 0.019,
                "net_return_25": 0.0175,
                "net_return_50": 0.015,
                "net_return_100": 0.01,
                "primary_net_return": 0.015,
                "stress_net_return": 0.01,
                "daily_h1_primary": None,
                "daily_h20_primary": None,
                "net_r_primary": 0.3,
                "mfe": 0.04,
                "mae": -0.01,
                "entry_time_utc": None,
                "exit_time_utc": None,
                "holding_minutes": 30,
                "market_direction_alignment": "BULL",
                "market_volatility_state": "NORMAL",
                "relative_strength_20_raw": 0.05,
                "relative_strength_63_raw": 0.08,
                "higher_timeframe_ticker_trend": "BULL",
                "trend_extension_raw": 0.5,
                "opening_participation_raw": 2.0,
                "premarket_participation_raw": 1.5,
                "prior_dollar_volume_raw": 75_000_000.0,
                "overnight_gap_raw": 0.03,
                "price_band": "25_50",
                "signal_time_raw": "09:50:00",
                "realized_volatility_raw": 0.35,
                "execution_liquidity_quality": "HIGH",
                "context_provenance": "SUCCESSOR_SHARED",
                "legacy_prior_close_bucket": None,
                "relative_strength_20_bucket": "P3_TO_P10PCT",
                "relative_strength_63_bucket": "P3_TO_P10PCT",
                "trend_extension_bucket": "M1_TO_P1ATR",
                "opening_participation_bucket": "2_TO_4",
                "premarket_participation_bucket": "1_5_TO_2",
                "liquidity_bucket": "50M_TO_250M",
                "overnight_gap_magnitude_bucket": "2_TO_5PCT",
                "signal_time_bucket": "0945_TO_1000",
                "realized_volatility_bucket": "25_TO_50PCT",
                "selector_key_1": "k1",
                "selector_key_2": "k2",
                "selector_key_3": "k3",
                "selector_key_4": "k4",
                "selector_key_5": "k5",
            }
        )

    conn = duckdb.connect()
    target = tmp_path / "condition_cells.parquet"
    try:
        conn.register("opportunities", pd.DataFrame(rows))
        _materialize_condition_cells(conn, target)
        cells = conn.execute(
            f"SELECT * FROM read_parquet('{_sql_path(target)}')"
        ).fetchdf()
    finally:
        conn.close()

    assert not cells.empty
    direction = cells[
        (cells["policy_id"] == "p1")
        & (cells["direction"] == "LONG")
        & (cells["condition_name"] == "direction")
        & (cells["condition_value"] == "LONG")
    ]
    assert len(direction) == 1
    assert int(direction.iloc[0]["eligible_opportunities"]) == 80
    assert bool(direction.iloc[0]["minimum_support"]) is True

    interaction = cells[
        (cells["condition_name"] == "market_direction_alignment__x__market_volatility_state")
        & (cells["condition_value"] == "BULL|NORMAL")
    ]
    assert len(interaction) == 1
    assert bool(interaction.iloc[0]["minimum_support"]) is True
