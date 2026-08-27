from __future__ import annotations

from packages.backtesting.phase27_blindness import (
    PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION,
    unexpected_protected_performance_keys,
)


def test_blindness_allows_only_explicit_unread_counters() -> None:
    payload = {
        "protected_returns_read": 0,
        "nested": {
            "protected_return_reads": 0,
            "protected_candidate_rows_read": 0,
        },
    }
    assert unexpected_protected_performance_keys(payload) == ()


def test_blindness_rejects_protected_performance_fields_recursively() -> None:
    payload = {
        "protected_returns_read": 0,
        "metrics": {
            "protected_mean_return": 0.01,
            "deeper": [{"protected_sharpe": 1.5}],
        },
    }
    assert unexpected_protected_performance_keys(payload) == (
        "metrics.deeper[0].protected_sharpe",
        "metrics.protected_mean_return",
    )


def test_blindness_contract_is_one_time_phase26_holdout_reuse() -> None:
    assert "phase26-holdout-one-time-reuse" in PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION
