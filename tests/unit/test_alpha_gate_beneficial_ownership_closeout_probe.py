from __future__ import annotations

import pytest

from packages.backtesting.alpha_gate_beneficial_ownership_closeout_probe import (
    BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
    BENEFICIAL_OWNERSHIP_EXPECTED_DEVELOPMENT_OUTCOME_ROWS,
    BENEFICIAL_OWNERSHIP_EXPECTED_PREDICTOR_ROWS,
    BENEFICIAL_OWNERSHIP_EXPECTED_PROTECTED_PREDICTOR_ROWS,
    BeneficialOwnershipCloseoutProbeError,
    beneficial_ownership_closeout_disposition,
)


def test_target_development_evidence_counts_are_frozen() -> None:
    assert BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD == (
        "067dc13429c22dc4e789959f56644423f0947946"
    )
    assert BENEFICIAL_OWNERSHIP_EXPECTED_PREDICTOR_ROWS == 3652
    assert BENEFICIAL_OWNERSHIP_EXPECTED_PROTECTED_PREDICTOR_ROWS == 889
    assert BENEFICIAL_OWNERSHIP_EXPECTED_DEVELOPMENT_OUTCOME_ROWS == 2412


def test_development_negative_is_closeout_candidate_without_protected_read() -> None:
    assert beneficial_ownership_closeout_disposition(
        status="ACCEPTED_NEGATIVE_DEVELOPMENT",
        protected_return_eligible_finalists=[],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) == ("ACCEPTED_NEGATIVE", True)


def test_protected_eligible_finalist_cannot_close_negative() -> None:
    assert beneficial_ownership_closeout_disposition(
        status="DEVELOPMENT_PASS_FINALIST_READY_PROTECTED",
        protected_return_eligible_finalists=["candidate"],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) == ("PENDING_PROTECTED_CONFIRMATION", False)


def test_consumed_protected_evidence_fails_closed() -> None:
    with pytest.raises(BeneficialOwnershipCloseoutProbeError, match="protected-return read"):
        beneficial_ownership_closeout_disposition(
            status="ACCEPTED_NEGATIVE_DEVELOPMENT",
            protected_return_eligible_finalists=[],
            protected_return_rows_read=1,
            protected_holdout_consumed=True,
        )
