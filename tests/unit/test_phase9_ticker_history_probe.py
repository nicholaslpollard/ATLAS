from __future__ import annotations

import pandas as pd

from packages.regimes.ticker_history_probe import (
    AUTHORITATIVE_CURRENT_INTERVAL,
    SINGLE_ALIAS_UNREUSED,
    TICKER_HISTORY_DEPTH_GRID,
    TICKER_HISTORY_PROBE_CONTRACT_VERSION,
    UNRESOLVED_MULTI_ALIAS,
    UNRESOLVED_TICKER_REUSE,
    _safe_depth_summary,
    depth_grid_counts,
    history_safety_status,
    identity_safe_depth,
)


def test_ticker_history_contract_and_depth_grid() -> None:
    assert TICKER_HISTORY_PROBE_CONTRACT_VERSION == (
        "ticker-history-probe-v1-current-alias-depth-reuse-continuity"
    )
    assert TICKER_HISTORY_DEPTH_GRID == (2, 5, 20, 60, 126, 252)


def test_ticker_history_safety_status_prefers_reuse_block() -> None:
    assert history_safety_status(
        alias_count=1,
        reuse_identity_count=2,
        authoritative_current_interval_count=0,
    ) == UNRESOLVED_TICKER_REUSE
    assert history_safety_status(
        alias_count=3,
        reuse_identity_count=2,
        authoritative_current_interval_count=1,
    ) == UNRESOLVED_TICKER_REUSE


def test_ticker_history_safety_status_distinguishes_single_and_authoritative_aliases() -> None:
    assert history_safety_status(
        alias_count=1,
        reuse_identity_count=1,
        authoritative_current_interval_count=0,
    ) == SINGLE_ALIAS_UNREUSED
    assert history_safety_status(
        alias_count=2,
        reuse_identity_count=1,
        authoritative_current_interval_count=1,
    ) == AUTHORITATIVE_CURRENT_INTERVAL
    assert history_safety_status(
        alias_count=2,
        reuse_identity_count=1,
        authoritative_current_interval_count=0,
    ) == UNRESOLVED_MULTI_ALIAS


def test_identity_safe_depth_uses_only_status_approved_lower_bound() -> None:
    assert identity_safe_depth(
        status=SINGLE_ALIAS_UNREUSED,
        observation_bounded_depth=126,
        authoritative_interval_depth=20,
    ) == 126
    assert identity_safe_depth(
        status=AUTHORITATIVE_CURRENT_INTERVAL,
        observation_bounded_depth=252,
        authoritative_interval_depth=60,
    ) == 60
    assert identity_safe_depth(
        status=UNRESOLVED_MULTI_ALIAS,
        observation_bounded_depth=252,
        authoritative_interval_depth=252,
    ) == 0
    assert identity_safe_depth(
        status=UNRESOLVED_TICKER_REUSE,
        observation_bounded_depth=252,
        authoritative_interval_depth=252,
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
            "safety_status": [
                SINGLE_ALIAS_UNREUSED,
                SINGLE_ALIAS_UNREUSED,
                AUTHORITATIVE_CURRENT_INTERVAL,
                UNRESOLVED_MULTI_ALIAS,
            ],
            "safe_depth": [300, 20, 60, 0],
        }
    )
    summary = _safe_depth_summary(frame)
    assert summary[SINGLE_ALIAS_UNREUSED]["instrument_count"] == 2
    assert summary[SINGLE_ALIAS_UNREUSED][">=20"] == 2
    assert summary[SINGLE_ALIAS_UNREUSED][">=252"] == 1
    assert summary[AUTHORITATIVE_CURRENT_INTERVAL][">=60"] == 1
    assert summary[UNRESOLVED_MULTI_ALIAS][">=2"] == 0
