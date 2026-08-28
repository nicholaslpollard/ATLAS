from __future__ import annotations

from packages.backtesting.phase30_closeout import phase30_disposition


def test_phase30_zero_finalists_is_accepted_negative_and_blocks_phase31() -> None:
    disposition, phase31_entry = phase30_disposition(())
    assert disposition == "ACCEPTED_NEGATIVE"
    assert phase31_entry is False


def test_phase30_nonempty_finalists_cannot_close_without_protected_confirmation() -> None:
    disposition, phase31_entry = phase30_disposition(("candidate",))
    assert disposition == "PENDING_PROTECTED_CONFIRMATION"
    assert phase31_entry is False
