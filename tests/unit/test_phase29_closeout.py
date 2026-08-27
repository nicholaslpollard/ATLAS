from __future__ import annotations

from packages.backtesting.phase29_closeout import phase29_disposition


def test_phase29_negative_disposition_blocks_phase30_entry() -> None:
    disposition, phase30_entry = phase29_disposition(())
    assert disposition == "ACCEPTED_NEGATIVE"
    assert phase30_entry is False


def test_phase29_supported_disposition_can_satisfy_phase30_entry() -> None:
    disposition, phase30_entry = phase29_disposition(("supported-alpha",))
    assert disposition == "ACCEPTED_POSITIVE"
    assert phase30_entry is True
