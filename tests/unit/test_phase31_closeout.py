from __future__ import annotations

from packages.backtesting.phase31_closeout import phase31_disposition


def test_phase31_zero_finalists_is_accepted_negative_and_blocks_phase32() -> None:
    disposition, phase32_entry = phase31_disposition(())
    assert disposition == "ACCEPTED_NEGATIVE"
    assert phase32_entry is False


def test_phase31_nonempty_finalists_cannot_close_without_protected_confirmation() -> None:
    disposition, phase32_entry = phase31_disposition(("candidate",))
    assert disposition == "PENDING_PROTECTED_CONFIRMATION"
    assert phase32_entry is False
