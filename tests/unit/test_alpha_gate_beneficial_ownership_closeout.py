from __future__ import annotations

import pytest

from packages.backtesting.alpha_gate_beneficial_ownership_closeout import (
    BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256,
    BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_REPORT_SHA256,
    BENEFICIAL_OWNERSHIP_ACCEPTED_EVIDENCE_FINGERPRINT,
    BENEFICIAL_OWNERSHIP_ACCEPTED_FINALISTS_SHA256,
    BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_REPORT_SHA256,
    BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_ROWS_SHA256,
    BeneficialOwnershipCloseoutError,
    beneficial_ownership_closeout_disposition,
)


def test_accepted_closeout_evidence_is_pinned() -> None:
    assert BENEFICIAL_OWNERSHIP_ACCEPTED_EVIDENCE_FINGERPRINT == (
        "c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8"
    )
    assert BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_REPORT_SHA256 == (
        "3cfecc2841e71172d2f4575ec6e0ef4dfe3d08d36fd3a95c6237bffb33601e30"
    )
    assert BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_REPORT_SHA256 == (
        "28997b63b978d4ce44f9719b909075b6be38d50109633547db96881f84b2850b"
    )
    assert BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_ROWS_SHA256 == (
        "310c7b8edfd5324e57b888734febe9407decc4fb1f042c67a6de07d3a468a466"
    )
    assert BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256 == (
        "4c038c5f6578dc9ef946a3485b1584514dbc893b9da976522ed0373c0715b679"
    )
    assert BENEFICIAL_OWNERSHIP_ACCEPTED_FINALISTS_SHA256 == (
        "d0cca3cbe1be332d010b7689b735244d40e760fa2f067e8c9fe1c47ce7b4fbca"
    )


def test_development_negative_closes_without_protected_read() -> None:
    assert beneficial_ownership_closeout_disposition(
        status="ACCEPTED_NEGATIVE_DEVELOPMENT",
        protected_return_eligible_finalists=[],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) == ("ACCEPTED_NEGATIVE", True)


def test_protected_source_insufficient_closes_without_protected_read() -> None:
    assert beneficial_ownership_closeout_disposition(
        status="ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT",
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
    with pytest.raises(BeneficialOwnershipCloseoutError, match="protected-return read"):
        beneficial_ownership_closeout_disposition(
            status="ACCEPTED_NEGATIVE_DEVELOPMENT",
            protected_return_eligible_finalists=[],
            protected_return_rows_read=1,
            protected_holdout_consumed=True,
        )


def test_unknown_status_fails_closed() -> None:
    with pytest.raises(BeneficialOwnershipCloseoutError, match="not a negative-closeout state"):
        beneficial_ownership_closeout_disposition(
            status="UNKNOWN",
            protected_return_eligible_finalists=[],
            protected_return_rows_read=0,
            protected_holdout_consumed=False,
        )
