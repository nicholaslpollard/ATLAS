from __future__ import annotations

from datetime import datetime, timezone

from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_audit import (
    EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
    _first_xnys_open_strictly_after,
    _parse_acceptance,
    _select_original_period_rows,
    earnings_innovation_pit_audit_fingerprint,
)


def _row(*, filed: str, accn: str, value: float, start: str = "2024-01-01", end: str = "2024-03-31") -> dict[str, object]:
    return {
        "unit": "USD/shares",
        "start": start,
        "end": end,
        "filed": filed,
        "form": "10-Q",
        "accn": accn,
        "fy": 2024,
        "fp": "Q1",
        "frame": None,
        "val": value,
    }


def test_pit_audit_fingerprint_is_frozen() -> None:
    assert earnings_innovation_pit_audit_fingerprint() == EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT


def test_original_period_selection_uses_earliest_non_amendment_accession() -> None:
    rows = (
        _row(filed="2024-05-01", accn="0000000001-24-000001", value=1.0),
        _row(filed="2025-05-01", accn="0000000001-25-000001", value=1.2),
    )
    selected, ambiguities = _select_original_period_rows(rows)
    assert ambiguities == 0
    assert len(selected) == 1
    assert selected[0]["accn"] == "0000000001-24-000001"
    assert selected[0]["val"] == 1.0


def test_ambiguous_original_context_fails_closed() -> None:
    rows = (
        _row(filed="2024-05-01", accn="0000000001-24-000001", value=1.0),
        _row(filed="2024-05-01", accn="0000000001-24-000001", value=1.1),
    )
    selected, ambiguities = _select_original_period_rows(rows)
    assert selected == ()
    assert ambiguities == 1


def test_acceptance_parser_accepts_official_iso_timestamp() -> None:
    parsed = _parse_acceptance("2024-05-01T16:05:00.000Z")
    assert parsed is not None
    assert parsed.tzinfo is not None


def test_decision_session_is_same_day_if_open_is_strictly_after_acceptance() -> None:
    session, open_time = _first_xnys_open_strictly_after(
        datetime(2024, 1, 3, 13, 0, tzinfo=timezone.utc)
    )
    assert session == "2024-01-03"
    assert open_time.startswith("2024-01-03T14:30:00")


def test_decision_session_moves_to_next_session_after_market_open() -> None:
    session, _ = _first_xnys_open_strictly_after(
        datetime(2024, 1, 3, 16, 0, tzinfo=timezone.utc)
    )
    assert session == "2024-01-04"
