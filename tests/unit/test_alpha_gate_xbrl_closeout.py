from __future__ import annotations

import pytest

from packages.backtesting.alpha_gate_xbrl_closeout import (
    XBRL_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256,
    XBRL_ACCEPTED_DEVELOPMENT_REPORT_SHA256,
    XBRL_ACCEPTED_EVIDENCE_FINGERPRINT,
    XBRL_ACCEPTED_FINALISTS_SHA256,
    XBRL_ACCEPTED_PREDICTOR_REPORT_SHA256,
    XBRL_ACCEPTED_PREDICTOR_ROWS_SHA256,
    XBRLCloseoutError,
    xbrl_closeout_disposition,
)


def test_accepted_closeout_hashes_are_pinned() -> None:
    assert XBRL_ACCEPTED_EVIDENCE_FINGERPRINT == (
        "291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91"
    )
    assert XBRL_ACCEPTED_DEVELOPMENT_REPORT_SHA256 == (
        "50bf99956ca95d725764b16bc5ae622b5ffe9dbfbadb4e63afa591a4aef998c6"
    )
    assert XBRL_ACCEPTED_PREDICTOR_REPORT_SHA256 == (
        "246bc1df65ce923b83167ea65f7e25b266657dec30fdcfd841e4bae260fbdb16"
    )
    assert XBRL_ACCEPTED_PREDICTOR_ROWS_SHA256 == (
        "9b3526527d2d45433f5970d768155c9763c16bc8d0772fdc526659ec1aabd14a"
    )
    assert XBRL_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256 == (
        "17be9dd103902ea0e9f39c172b7dfb0cf3d552b6f743bd8101c7f836b8500b55"
    )
    assert XBRL_ACCEPTED_FINALISTS_SHA256 == (
        "c5cfddbe30b597d115560a9611e8bf3bef5bcb76f7c59f5d5f5a071db458945f"
    )


def test_development_negative_closes_without_protected_read() -> None:
    assert xbrl_closeout_disposition(
        status="ACCEPTED_NEGATIVE_DEVELOPMENT",
        protected_return_eligible_finalists=[],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) == ("ACCEPTED_NEGATIVE", True)


def test_protected_source_insufficient_closes_without_protected_read() -> None:
    assert xbrl_closeout_disposition(
        status="ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT",
        protected_return_eligible_finalists=[],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) == ("ACCEPTED_NEGATIVE", True)


def test_protected_eligible_finalist_must_not_be_closed_negative() -> None:
    assert xbrl_closeout_disposition(
        status="DEVELOPMENT_PASS_FINALISTS_READY_PROTECTED",
        protected_return_eligible_finalists=["candidate"],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) == ("PENDING_PROTECTED_CONFIRMATION", False)


def test_consumed_protected_evidence_fails_negative_closeout() -> None:
    with pytest.raises(XBRLCloseoutError, match="protected-return read"):
        xbrl_closeout_disposition(
            status="ACCEPTED_NEGATIVE_DEVELOPMENT",
            protected_return_eligible_finalists=[],
            protected_return_rows_read=1,
            protected_holdout_consumed=True,
        )


def test_unknown_status_fails_closed() -> None:
    with pytest.raises(XBRLCloseoutError, match="not a negative-closeout state"):
        xbrl_closeout_disposition(
            status="UNKNOWN",
            protected_return_eligible_finalists=[],
            protected_return_rows_read=0,
            protected_holdout_consumed=False,
        )
