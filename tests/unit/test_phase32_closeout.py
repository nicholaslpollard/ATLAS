from __future__ import annotations

from packages.backtesting.phase32_closeout import (
    PHASE32_ACCEPTED_AUDIT_FINGERPRINT,
    PHASE32_ACCEPTED_PROTECTED_EVENT_ROWS,
    PHASE32_ACCEPTED_PROTECTED_PLAN_FINGERPRINT,
    PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256,
    PHASE32_ACCEPTED_PROTECTED_SIGNAL_SESSIONS,
    PHASE32_ACCEPTED_PROTECTED_UNIQUE_INSTRUMENTS,
    phase32_disposition_from_source_gate,
)


def test_phase32_accepted_negative_source_gate_is_frozen() -> None:
    assert PHASE32_ACCEPTED_PROTECTED_EVENT_ROWS == 46
    assert PHASE32_ACCEPTED_PROTECTED_SIGNAL_SESSIONS == 33
    assert PHASE32_ACCEPTED_PROTECTED_UNIQUE_INSTRUMENTS == 40
    assert PHASE32_ACCEPTED_AUDIT_FINGERPRINT == (
        "c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e"
    )
    assert PHASE32_ACCEPTED_PROTECTED_PLAN_FINGERPRINT == (
        "2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344"
    )
    assert PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256 == (
        "b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703"
    )
    assert phase32_disposition_from_source_gate(
        event_rows=46,
        signal_sessions=33,
        unique_instruments=40,
    ) == ("ACCEPTED_NEGATIVE", False)


def test_phase32_closeout_does_not_convert_eligible_population_to_negative() -> None:
    assert phase32_disposition_from_source_gate(
        event_rows=50,
        signal_sessions=20,
        unique_instruments=20,
    ) == ("PENDING_PROTECTED_CONFIRMATION", False)


def test_phase32_each_frozen_source_minimum_is_mandatory() -> None:
    assert phase32_disposition_from_source_gate(event_rows=49, signal_sessions=20, unique_instruments=20)[0] == "ACCEPTED_NEGATIVE"
    assert phase32_disposition_from_source_gate(event_rows=50, signal_sessions=19, unique_instruments=20)[0] == "ACCEPTED_NEGATIVE"
    assert phase32_disposition_from_source_gate(event_rows=50, signal_sessions=20, unique_instruments=19)[0] == "ACCEPTED_NEGATIVE"
