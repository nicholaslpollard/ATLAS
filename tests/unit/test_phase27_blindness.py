from __future__ import annotations

from packages.backtesting.phase27_blindness import (
    PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION,
    unexpected_protected_performance_keys,
)


def test_blindness_allows_explicit_unread_counters_and_true_assertions() -> None:
    payload = {
        "protected_returns_read": 0,
        "nested": {
            "protected_return_reads": 0,
            "protected_candidate_rows_read": 0,
            "protected_returns_unread": True,
            "finalist_artifact_protected_returns_unread": True,
        },
    }
    assert unexpected_protected_performance_keys(payload) == ()


def test_blindness_rejects_false_unread_assertion_or_performance_fields() -> None:
    payload = {
        "protected_returns_unread": False,
        "metrics": {
            "protected_mean_return": 0.01,
            "deeper": [{"protected_sharpe": 1.5}],
        },
    }
    assert unexpected_protected_performance_keys(payload) == (
        "metrics.deeper[0].protected_sharpe",
        "metrics.protected_mean_return",
        "protected_returns_unread",
    )


def test_blindness_contract_is_one_time_phase26_holdout_reuse() -> None:
    assert "phase26-holdout-one-time-reuse" in PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION
