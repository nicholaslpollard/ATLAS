from __future__ import annotations

from packages.backtesting.phase28_closeout import phase28_disposition


def test_phase28_negative_disposition_blocks_phase29_entry() -> None:
    disposition, phase29_entry = phase28_disposition(())
    assert disposition == "ACCEPTED_NEGATIVE"
    assert phase29_entry is False


def test_phase28_supported_disposition_can_satisfy_phase29_entry() -> None:
    disposition, phase29_entry = phase28_disposition(("supported-alpha",))
    assert disposition == "ACCEPTED_POSITIVE"
    assert phase29_entry is True
