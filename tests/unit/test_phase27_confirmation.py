from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from packages.backtesting.phase27_confirmation import (
    PHASE27_PROTECTED_READ_PLAN_CONTRACT_VERSION,
    _assign_fold,
    protected_checks,
)
from packages.backtesting.phase27_research import tranche_metrics


def _protected_fixture() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    start = date(2026, 5, 12)
    for session_index in range(30):
        session = start + timedelta(days=session_index)
        for row_index in range(3):
            rows.append(
                {
                    "as_of_date": session,
                    "instrument_id": f"p-{session_index:02d}-{row_index}",
                    "directional_return": 0.004,
                    "market_state": "NORMAL",
                    "effective_ticker_state": "NORMAL",
                }
            )
    return pd.DataFrame(rows)


def test_protected_checks_pass_positive_sufficient_evidence() -> None:
    signals = _assign_fold(
        _protected_fixture(), field="protected_fold", desired_folds=3
    )
    metrics = tranche_metrics(
        signals,
        predictions=pd.DataFrame(),
        confidence=0.80,
        fold_field="protected_fold",
        label="unit-protected",
        tuning_trial_count=0,
    )
    assert metrics.raw_rows == 90
    assert metrics.signal_sessions == 30
    assert metrics.positive_folds == 3
    assert all(protected_checks(metrics).values())


def test_protected_checks_fail_insufficient_session_evidence_without_error() -> None:
    signals = _protected_fixture().loc[
        lambda frame: frame["as_of_date"] < date(2026, 6, 1)
    ].copy()
    signals = _assign_fold(signals, field="protected_fold", desired_folds=3)
    metrics = tranche_metrics(
        signals,
        predictions=pd.DataFrame(),
        confidence=0.80,
        fold_field="protected_fold",
        label="unit-protected-short",
        tuning_trial_count=0,
    )
    assert protected_checks(metrics)["min_signal_sessions"] is False


def test_protected_read_plan_is_explicitly_immutable_and_resumable() -> None:
    assert "immutable-resumable-exact-signal-keys" in PHASE27_PROTECTED_READ_PLAN_CONTRACT_VERSION
