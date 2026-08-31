from __future__ import annotations

import pytest

from packages.backtesting.alpha_gate_finra_short_interest_source_closeout_probe import (
    FINRA_SHORT_INTEREST_EXPECTED_SOURCE_GATES,
    FINRAShortInterestSourceCloseoutProbeError,
    finra_source_only_disposition,
)


def test_exact_frozen_source_failure_closes_negative() -> None:
    assert (
        finra_source_only_disposition(
            FINRA_SHORT_INTEREST_EXPECTED_SOURCE_GATES,
            target_outcome_rows_read=0,
            protected_return_rows_read=0,
            protected_holdout_consumed=False,
        )
        == "ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT"
    )


def test_outcome_read_forbids_source_only_closeout() -> None:
    with pytest.raises(FINRAShortInterestSourceCloseoutProbeError):
        finra_source_only_disposition(
            FINRA_SHORT_INTEREST_EXPECTED_SOURCE_GATES,
            target_outcome_rows_read=1,
            protected_return_rows_read=0,
            protected_holdout_consumed=False,
        )


def test_protected_consumption_forbids_source_only_closeout() -> None:
    with pytest.raises(FINRAShortInterestSourceCloseoutProbeError):
        finra_source_only_disposition(
            FINRA_SHORT_INTEREST_EXPECTED_SOURCE_GATES,
            target_outcome_rows_read=0,
            protected_return_rows_read=1,
            protected_holdout_consumed=True,
        )


def test_dropping_underpowered_hypothesis_is_not_an_allowed_closeout_repair() -> None:
    repaired = {
        candidate_id: dict(gates)
        for candidate_id, gates in FINRA_SHORT_INTEREST_EXPECTED_SOURCE_GATES.items()
        if candidate_id != "rapid_short_cover_crowded_long"
    }
    assert (
        finra_source_only_disposition(
            repaired,
            target_outcome_rows_read=0,
            protected_return_rows_read=0,
            protected_holdout_consumed=False,
        )
        == "SOURCE_ONLY_PASS_NOT_CLOSEABLE"
    )


def test_additional_source_gate_failure_is_not_silently_accepted() -> None:
    altered = {
        candidate_id: dict(gates)
        for candidate_id, gates in FINRA_SHORT_INTEREST_EXPECTED_SOURCE_GATES.items()
    }
    altered["rapid_short_build_crowded_short"]["protected_min_rows"] = False
    with pytest.raises(FINRAShortInterestSourceCloseoutProbeError):
        finra_source_only_disposition(
            altered,
            target_outcome_rows_read=0,
            protected_return_rows_read=0,
            protected_holdout_consumed=False,
        )
