from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from packages.backtesting.phase32_development import (
    PHASE32_DEVELOPMENT_BOUNDARY_EXIT,
    PHASE32_DEVELOPMENT_OUTCOME_CONTRACT_VERSION,
    PHASE32_DEVELOPMENT_SIGNAL_CONTRACT_VERSION,
    PHASE32_DEVELOPMENT_STUDY_CONTRACT_VERSION,
    PHASE32_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT,
    Phase32DevelopmentError,
    _fold_economic_means,
    apply_return_geometry,
    chronological_boundaries,
    holm_bonferroni,
    resolve_execution_tickers,
)


def _predictor(*, candidate_id: str = "share_repurchase_long") -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "direction": "LONG" if candidate_id == "share_repurchase_long" else "SHORT",
        "instrument_id": "figi:ABC",
        "decision_session": "2024-01-03",
        "stage": "development",
        "provider_tickers": ["ABC"],
    }


def _filing(*, ticker: str = "ABC", candidate_id: str = "share_repurchase_long") -> dict[str, object]:
    return {
        "eligibility": "eligible",
        "stage": "development",
        "decision_session": "2024-01-03",
        "candidate_ids": [candidate_id],
        "instrument": {"instrument_id": "figi:ABC", "ticker": ticker},
    }


def test_development_contract_pins_independent_acceptance() -> None:
    assert PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT == (
        "531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde"
    )
    assert PHASE32_DEVELOPMENT_BOUNDARY_EXIT == date(2026, 5, 11)
    assert all(
        value.startswith("phase32-")
        for value in (
            PHASE32_DEVELOPMENT_STUDY_CONTRACT_VERSION,
            PHASE32_DEVELOPMENT_OUTCOME_CONTRACT_VERSION,
            PHASE32_DEVELOPMENT_SIGNAL_CONTRACT_VERSION,
            PHASE32_FINALIST_ARTIFACT_CONTRACT_VERSION,
        )
    )


def test_chronological_split_uses_first_75_percent_then_five_session_purge() -> None:
    sessions = tuple(date(2024, 1, 1) + timedelta(days=index) for index in range(100))
    boundaries = chronological_boundaries(sessions)
    assert boundaries.selection_session_count == 75
    assert boundaries.selection_end == sessions[74]
    assert boundaries.purge_sessions == sessions[75:80]
    assert boundaries.internal_start == sessions[80]
    assert boundaries.internal_session_count == 20


def test_execution_ticker_resolution_is_source_only_and_exact() -> None:
    mapping = resolve_execution_tickers([_predictor()], [_filing()])
    assert mapping[("figi:ABC", "2024-01-03", "share_repurchase_long")] == "ABC"


def test_execution_ticker_ambiguity_fails_before_outcomes() -> None:
    with pytest.raises(Phase32DevelopmentError, match="execution ticker is ambiguous before outcomes"):
        resolve_execution_tickers([_predictor()], [_filing(ticker="ABC"), _filing(ticker="XYZ")])


def test_return_geometry_uses_open_to_t5_close_spy_relative_direction() -> None:
    frame = pd.DataFrame(
        [
            {"direction": "LONG", "entry_open": 100.0, "exit_close": 110.0, "spy_entry_open": 100.0, "spy_exit_close": 105.0},
            {"direction": "SHORT", "entry_open": 100.0, "exit_close": 90.0, "spy_entry_open": 100.0, "spy_exit_close": 95.0},
        ]
    )
    result = apply_return_geometry(frame)
    assert result.loc[0, "primary_gross_return"] == pytest.approx(0.05)
    assert result.loc[0, "unhedged_gross_return"] == pytest.approx(0.10)
    assert result.loc[1, "primary_gross_return"] == pytest.approx(0.05)
    assert result.loc[1, "unhedged_gross_return"] == pytest.approx(0.10)


def test_holm_bonferroni_keeps_full_five_hypothesis_family() -> None:
    result = holm_bonferroni({"a": 0.001, "b": 0.005, "c": 0.02, "d": 0.03, "e": 0.04})
    assert set(result) == {"a", "b", "c", "d", "e"}
    assert result["a"]["threshold"] == pytest.approx(0.01)
    assert result["a"]["rejected_null"] is True
    assert result["b"]["threshold"] == pytest.approx(0.0125)


def test_empty_frozen_fold_is_not_silently_dropped() -> None:
    session = pd.DataFrame(
        {
            "decision_session": [date(2024, 1, 2), date(2024, 1, 4)],
            "primary_gross_return": [0.01, 0.02],
        }
    )
    signals = pd.DataFrame(
        {
            "decision_session": [date(2024, 1, 2), date(2024, 1, 4)],
            "selection_fold": [0, 2],
        }
    )
    values = _fold_economic_means(
        session,
        signals,
        fold_field="selection_fold",
        fold_count=3,
        primary_cost=0.001,
    )
    assert values[0] == pytest.approx(0.009)
    assert values[1] is None
    assert values[2] == pytest.approx(0.019)
