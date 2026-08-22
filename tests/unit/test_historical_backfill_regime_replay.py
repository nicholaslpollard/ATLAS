from __future__ import annotations

from datetime import date

import pandas as pd

from packages.regimes.historical_backfill_regime_replay import (
    GATE10_INTRADAY_POLICY,
    GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN,
    GATE10_REGIME_REPLAY_PREFLIGHT_CONTRACT_VERSION,
    GATE10_TICKER_ORIGIN,
    _frame_date_range,
    _latest_manifest_status,
    sector_first_dates,
    state_overlap_diagnostics,
)


def test_gate10_split_origins_preserve_no_synthetic_intraday_boundary() -> None:
    assert GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN == date(2016, 1, 4)
    assert GATE10_TICKER_ORIGIN == date(2021, 8, 16)
    assert GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN < GATE10_TICKER_ORIGIN
    assert GATE10_INTRADAY_POLICY == "NO_SYNTHETIC_PRE2021_4H_OR_1H_FROM_DAILY_BACKFILL"


def test_gate10_contract_explicitly_versions_split_origin_policy() -> None:
    assert GATE10_REGIME_REPLAY_PREFLIGHT_CONTRACT_VERSION == (
        "historical-backfill-regime-replay-preflight-v1-"
        "split-market-sector-daily-origin-ticker-intraday-origin"
    )


def test_state_overlap_diagnostics_counts_row_and_dimension_changes() -> None:
    candidate = pd.DataFrame(
        [
            {"trading_date": "2024-01-02", "composite": "A", "structure": "UP"},
            {"trading_date": "2024-01-03", "composite": "B", "structure": "UP"},
            {"trading_date": "2024-01-04", "composite": "C", "structure": "DOWN"},
        ]
    )
    baseline = pd.DataFrame(
        [
            {"trading_date": date(2024, 1, 2), "composite": "A", "structure": "UP"},
            {"trading_date": date(2024, 1, 3), "composite": "X", "structure": "UP"},
            {"trading_date": date(2024, 1, 4), "composite": "C", "structure": "UP"},
        ]
    )
    result = state_overlap_diagnostics(
        candidate,
        baseline,
        key_columns=("trading_date",),
        state_columns=("composite", "structure"),
    )
    assert result["overlap_rows"] == 3
    assert result["changed_rows"] == 2
    assert result["unchanged_rows"] == 1
    assert result["dimension_change_counts"] == {"composite": 1, "structure": 1}


def test_state_overlap_diagnostics_handles_no_overlap() -> None:
    candidate = pd.DataFrame([{"trading_date": "2024-01-02", "composite": "A"}])
    baseline = pd.DataFrame([{"trading_date": "2024-02-02", "composite": "A"}])
    result = state_overlap_diagnostics(
        candidate,
        baseline,
        key_columns=("trading_date",),
        state_columns=("composite",),
    )
    assert result["overlap_rows"] == 0
    assert result["changed_rows"] == 0
    assert result["change_rate"] is None


def test_sector_first_dates_allows_late_proxy_history() -> None:
    frame = pd.DataFrame(
        [
            {"symbol": "XLB", "trading_date": "2017-01-03"},
            {"symbol": "XLB", "trading_date": "2017-01-04"},
            {"symbol": "XLC", "trading_date": "2019-06-20"},
            {"symbol": "XLC", "trading_date": "2019-06-21"},
        ]
    )
    result = sector_first_dates(frame)
    assert result["XLB"] == "2017-01-03"
    assert result["XLC"] == "2019-06-20"
    assert result["XLK"] is None


def test_frame_date_range_normalizes_timestamp_types() -> None:
    frame = pd.DataFrame(
        {"trading_date": [pd.Timestamp("2021-08-16", tz="UTC"), date(2021, 8, 18)]}
    )
    assert _frame_date_range(frame) == ("2021-08-16", "2021-08-18")


def test_latest_manifest_status_compares_dependency_fingerprint(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{"dependency_fingerprint":"new"}\n', encoding="utf-8")
    current = _latest_manifest_status(manifest_path=path, expected_dependency="new")
    stale = _latest_manifest_status(manifest_path=path, expected_dependency="different")
    missing = _latest_manifest_status(
        manifest_path=tmp_path / "missing.json",
        expected_dependency="new",
    )
    assert current["current"] is True
    assert stale["current"] is False
    assert missing["present"] is False
