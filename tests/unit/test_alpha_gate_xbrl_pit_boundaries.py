from __future__ import annotations

from datetime import date

from packages.backtesting.alpha_gate_xbrl_pit_audit import _decision_session, _resolve_identity


def test_decision_session_is_first_xnys_open_strictly_after_acceptance() -> None:
    # Friday 2025-05-02. Before the 09:30 New York open, the same session is eligible.
    assert _decision_session("2025-05-02T08:00:00-04:00") == date(2025, 5, 2)
    # Acceptance exactly at the open is not strictly before it, so Monday is first eligible.
    assert _decision_session("2025-05-02T09:30:00-04:00") == date(2025, 5, 5)
    # A regular-session filing is also first actionable at the next session open.
    assert _decision_session("2025-05-02T12:00:00-04:00") == date(2025, 5, 5)


def test_multiple_security_level_instruments_for_one_cik_fail_closed_as_ambiguous() -> None:
    rows = [
        {
            "ticker": "ABC",
            "cik": "0000000001",
            "composite_figi": "BBG000000001",
            "primary_exchange": "XNYS",
            "type": "CS",
        },
        {
            "ticker": "ABCpA",
            "cik": "0000000001",
            "composite_figi": "BBG000000002",
            "primary_exchange": "XNYS",
            "type": "PFD",
        },
    ]
    result = _resolve_identity(rows, issuer_cik="0000000001", as_of_date=date(2025, 5, 5))
    assert result["status"] == "AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS"
    assert result["unique_instrument_count"] == 2


def test_fallback_identity_is_not_eligible_for_xbrl_pit_mapping() -> None:
    rows = [{"ticker": "ABC", "cik": "0000000001"}]
    result = _resolve_identity(rows, issuer_cik="0000000001", as_of_date=date(2025, 5, 5))
    assert result["status"] == "NO_ELIGIBLE_PIT_INSTRUMENT"
    assert result["unique_instrument_count"] == 0
    assert result["mapping_evidence"][0]["status"] == "fallback_identity"
