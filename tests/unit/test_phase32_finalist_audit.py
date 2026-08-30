from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from packages.backtesting.phase32_finalist_audit import (
    PHASE32_EXPECTED_FINALISTS,
    PHASE32_EXPECTED_SELECTION_SURVIVORS,
    PHASE32_EXPECTED_SELECTION_WINNERS,
    PHASE32_FINALIST_BLINDNESS_AUDIT_CONTRACT_VERSION,
    PHASE32_PROTECTED_PLAN_CONTRACT_VERSION,
    Phase32FinalistAuditError,
    _fold_mapping,
    independent_block_bootstrap,
    independent_holm_bonferroni,
    protected_source_sample_gate,
    resolve_protected_execution_tickers,
)


def _predictor(*, ticker: str = "ABC") -> dict[str, object]:
    return {
        "candidate_id": "solvency_distress_short",
        "direction": "SHORT",
        "instrument_id": "figi:ABC",
        "decision_session": "2026-06-01",
        "stage": "protected_predictor_only",
        "provider_tickers": [ticker],
    }


def _filing(*, ticker: str = "ABC") -> dict[str, object]:
    return {
        "eligibility": "eligible",
        "stage": "protected_predictor_only",
        "decision_session": "2026-06-01",
        "candidate_ids": ["solvency_distress_short"],
        "instrument": {"instrument_id": "figi:ABC", "ticker": ticker},
    }


def test_finalist_audit_contract_pins_observed_development_result() -> None:
    assert PHASE32_EXPECTED_SELECTION_SURVIVORS == (
        "equity_issuance_short",
        "financial_integrity_adverse_short",
        "listing_distress_short",
        "share_repurchase_long",
        "solvency_distress_short",
    )
    assert PHASE32_EXPECTED_SELECTION_WINNERS == (
        "share_repurchase_long",
        "solvency_distress_short",
    )
    assert PHASE32_EXPECTED_FINALISTS == ("solvency_distress_short",)
    assert PHASE32_FINALIST_BLINDNESS_AUDIT_CONTRACT_VERSION.startswith("phase32-")
    assert PHASE32_PROTECTED_PLAN_CONTRACT_VERSION.startswith("phase32-")


def test_protected_fold_mapping_is_complete_and_chronological() -> None:
    sessions = tuple(date(2026, 5, 12) + timedelta(days=index) for index in range(63))
    mapping = _fold_mapping(sessions, 3)
    assert len(mapping) == len(sessions)
    assert mapping[sessions[0]] == 0
    assert mapping[sessions[-1]] == 2
    assert set(mapping.values()) == {0, 1, 2}


def test_independent_bootstrap_is_deterministic() -> None:
    values = np.asarray([0.01, 0.02, -0.01, 0.03, 0.005, 0.015], dtype=float)
    first = independent_block_bootstrap(values, confidence=0.9, label="internal:solvency_distress_short")
    second = independent_block_bootstrap(values, confidence=0.9, label="internal:solvency_distress_short")
    assert first == second


def test_independent_holm_keeps_global_five_candidate_family() -> None:
    result = independent_holm_bonferroni(
        {
            "a": 0.001,
            "b": 0.004,
            "c": 0.01,
            "d": 0.02,
            "e": 0.04,
        }
    )
    assert set(result) == {"a", "b", "c", "d", "e"}
    assert result["a"]["threshold"] == pytest.approx(0.01)


def test_protected_execution_ticker_resolution_is_finalist_only_and_exact() -> None:
    mapping = resolve_protected_execution_tickers(
        [_predictor()],
        [_filing()],
        finalist_ids=PHASE32_EXPECTED_FINALISTS,
    )
    assert mapping[("figi:ABC", "2026-06-01", "solvency_distress_short")] == "ABC"


def test_protected_execution_ticker_ambiguity_fails_before_returns() -> None:
    with pytest.raises(Phase32FinalistAuditError, match="ambiguous before outcomes"):
        resolve_protected_execution_tickers(
            [_predictor(ticker="ABC")],
            [_filing(ticker="ABC"), _filing(ticker="XYZ")],
            finalist_ids=PHASE32_EXPECTED_FINALISTS,
        )


def test_source_only_protected_sample_gate_can_block_return_read() -> None:
    too_small = [
        {
            "instrument_id": f"figi:{index}",
            "decision_session": f"2026-06-{(index % 10) + 1:02d}",
        }
        for index in range(19)
    ]
    result = protected_source_sample_gate(too_small)
    assert result["possible"] is False
    assert result["checks"]["min_event_rows"] is False
    assert result["checks"]["min_signal_sessions"] is False
    assert result["checks"]["min_unique_instruments"] is False
