from __future__ import annotations

import pandas as pd

from packages.regimes.ticker_history_probe import (
    AUTHORITATIVE_CURRENT_INTERVAL,
    CURRENT_ALIAS_NO_CONFLICT,
    TICKER_HISTORY_DEPTH_GRID,
    TICKER_HISTORY_PROBE_CONTRACT_VERSION,
    UNRESOLVED_MULTI_ALIAS,
    UNRESOLVED_TICKER_REUSE,
    _depth_summary,
    authoritative_history_depth,
    depth_grid_counts,
    history_status,
    operational_history_depth,
)


def test_ticker_history_contract_and_depth_grid() -> None:
    assert TICKER_HISTORY_PROBE_CONTRACT_VERSION == (
        "ticker-history-probe-v2-operational-current-alias-authoritative-interval-depth"
    )
    assert TICKER_HISTORY_DEPTH_GRID == (2, 5, 20, 60, 126, 252)


def test_authoritative_interval_takes_precedence_over_reuse() -> None:
    assert history_status(
        alias_count=3,
        reuse_identity_count=2,
        authoritative_current_interval_count=1,
    ) == AUTHORITATIVE_CURRENT_INTERVAL


def test_history_status_distinguishes_operational_and_unresolved_cases() -> None:
    assert history_status(
        alias_count=1,
        reuse_identity_count=1,
        authoritative_current_interval_count=0,
    ) == CURRENT_ALIAS_NO_CONFLICT
    assert history_status(
        alias_count=2,
        reuse_identity_count=1,
        authoritative_current_interval_count=0,
    ) == UNRESOLVED_MULTI_ALIAS
    assert history_status(
        alias_count=1,
        reuse_identity_count=2,
        authoritative_current_interval_count=0,
    ) == UNRESOLVED_TICKER_REUSE


def test_operational_depth_does_not_use_sparse_reference_bound() -> None:
    assert operational_history_depth(
        status=CURRENT_ALIAS_NO_CONFLICT,
        raw_current_alias_depth=252,
        authoritative_interval_depth=20,
    ) == 252
    assert operational_history_depth(
        status=AUTHORITATIVE_CURRENT_INTERVAL,
        raw_current_alias_depth=500,
        authoritative_interval_depth=60,
    ) == 60


def test_unresolved_history_is_not_spliced() -> None:
    assert operational_history_depth(
        status=UNRESOLVED_MULTI_ALIAS,
        raw_current_alias_depth=500,
        authoritative_interval_depth=500,
    ) == 0
    assert operational_history_depth(
        status=UNRESOLVED_TICKER_REUSE,
        raw_current_alias_depth=500,
        authoritative_interval_depth=500,
    ) == 0
    assert authoritative_history_depth(
        status=CURRENT_ALIAS_NO_CONFLICT,
        authoritative_interval_depth=500,
    ) == 0


def test_authoritative_depth_is_current_interval_only() -> None:
    assert authoritative_history_depth(
        status=AUTHORITATIVE_CURRENT_INTERVAL,
        authoritative_interval_depth=126,
    ) == 126
    assert authoritative_history_depth(
        status=UNRESOLVED_TICKER_REUSE,
        authoritative_interval_depth=126,
    ) == 0


def test_depth_grid_and_status_summary_are_deterministic() -> None:
    assert depth_grid_counts([0, 1, 2, 5, 20, 60, 126, 252, 400]) == {
        ">=2": 7,
        ">=5": 6,
        ">=20": 5,
        ">=60": 4,
        ">=126": 3,
        ">=252": 2,
    }
    frame = pd.DataFrame(
        {
            "history_status": [
                CURRENT_ALIAS_NO_CONFLICT,
                CURRENT_ALIAS_NO_CONFLICT,
                AUTHORITATIVE_CURRENT_INTERVAL,
                UNRESOLVED_MULTI_ALIAS,
            ],
            "operational_depth": [300, 20, 60, 0],
            "authoritative_depth": [0, 0, 60, 0],
        }
    )
    summary = _depth_summary(frame)
    assert summary[CURRENT_ALIAS_NO_CONFLICT]["instrument_count"] == 2
    assert summary[CURRENT_ALIAS_NO_CONFLICT]["operational"][">=20"] == 2
    assert summary[CURRENT_ALIAS_NO_CONFLICT]["authoritative"][">=2"] == 0
    assert summary[AUTHORITATIVE_CURRENT_INTERVAL]["operational"][">=60"] == 1
    assert summary[AUTHORITATIVE_CURRENT_INTERVAL]["authoritative"][">=60"] == 1
    assert summary[UNRESOLVED_MULTI_ALIAS]["operational"][">=2"] == 0
