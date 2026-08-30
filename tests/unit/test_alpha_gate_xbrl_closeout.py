from __future__ import annotations

import pytest

from packages.backtesting.alpha_gate_xbrl_closeout import (
    XBRLCloseoutError,
    xbrl_closeout_disposition,
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
