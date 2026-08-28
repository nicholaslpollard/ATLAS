from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from packages.backtesting.phase31_development import (
    apply_return_geometry,
    candidate_view,
    chronological_boundaries,
    holm_bonferroni,
)
from packages.backtesting.phase31_policy import PHASE31_CANDIDATES


def _candidate(candidate_id: str):
    return next(
        item for item in PHASE31_CANDIDATES if item.candidate_id == candidate_id
    )


def test_phase31_chronology_uses_75_percent_then_20_session_purge() -> None:
    start = date(2022, 1, 3)
    sessions = tuple(start + timedelta(days=index) for index in range(100))
    split = chronological_boundaries(sessions)
    assert split.selection_session_count == 75
    assert split.selection_start == sessions[0]
    assert split.selection_end == sessions[74]
    assert split.purge_sessions == sessions[75:95]
    assert split.internal_session_count == 5
    assert split.internal_start == sessions[95]
    assert split.internal_end == sessions[-1]


def test_phase31_candidate_membership_uses_frozen_broad_and_cluster_ids() -> None:
    frame = pd.DataFrame(
        {
            "ticker": ["A", "B", "C"],
            "direction": ["LONG", "LONG", "SHORT"],
            "broad_candidate_id": [
                "open_market_purchase_long",
                "open_market_purchase_long",
                "open_market_sale_short",
            ],
            "cluster_candidate_id": [
                None,
                "clustered_open_market_purchase_long",
                "clustered_open_market_sale_short",
            ],
        }
    )
    broad = candidate_view(frame, _candidate("open_market_purchase_long"))
    clustered = candidate_view(
        frame, _candidate("clustered_open_market_purchase_long")
    )
    sale_cluster = candidate_view(
        frame, _candidate("clustered_open_market_sale_short")
    )
    assert broad["ticker"].tolist() == ["A", "B"]
    assert clustered["ticker"].tolist() == ["B"]
    assert sale_cluster["ticker"].tolist() == ["C"]


def test_phase31_return_geometry_is_exact_open_to_t20_close_and_spy_relative() -> None:
    frame = pd.DataFrame(
        {
            "direction": ["LONG", "SHORT"],
            "entry_open": [100.0, 100.0],
            "exit_close": [110.0, 90.0],
            "spy_entry_open": [100.0, 100.0],
            "spy_exit_close": [105.0, 105.0],
        }
    )
    result = apply_return_geometry(frame)
    assert abs(result.loc[0, "stock_return"] - 0.10) < 1e-12
    assert abs(result.loc[0, "spy_return"] - 0.05) < 1e-12
    assert abs(result.loc[0, "primary_gross_return"] - 0.05) < 1e-12
    assert abs(result.loc[0, "unhedged_gross_return"] - 0.10) < 1e-12
    assert abs(result.loc[1, "stock_return"] - (-0.10)) < 1e-12
    assert abs(result.loc[1, "primary_gross_return"] - 0.15) < 1e-12
    assert abs(result.loc[1, "unhedged_gross_return"] - 0.10) < 1e-12


def test_phase31_holm_is_global_and_step_down() -> None:
    result = holm_bonferroni(
        {"a": 0.005, "b": 0.010, "c": 0.030, "d": 0.040},
        alpha=0.05,
    )
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is True
    assert result["c"]["rejected_null"] is False
    assert result["d"]["rejected_null"] is False
