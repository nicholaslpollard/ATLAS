from __future__ import annotations

from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_diagnostics import (
    EARNINGS_INNOVATION_PIT_DIAGNOSTIC_FINGERPRINT,
    _select_with_diagnostics,
    earnings_innovation_pit_diagnostic_fingerprint,
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


def test_diagnostic_fingerprint_is_frozen() -> None:
    assert earnings_innovation_pit_diagnostic_fingerprint() == EARNINGS_INNOVATION_PIT_DIAGNOSTIC_FINGERPRINT


def test_select_with_diagnostics_preserves_unambiguous_original() -> None:
    rows = (
        _row(filed="2024-05-01", accn="0000000001-24-000001", value=1.0),
        _row(filed="2025-05-01", accn="0000000001-25-000001", value=1.2),
    )
    selected, diagnostics = _select_with_diagnostics("0000000001", rows)
    assert diagnostics == ()
    assert len(selected) == 1
    assert selected[0]["accn"] == "0000000001-24-000001"


def test_select_with_diagnostics_exposes_ambiguous_original_rows() -> None:
    rows = (
        _row(filed="2024-05-01", accn="0000000001-24-000001", value=1.0),
        _row(filed="2024-05-01", accn="0000000001-24-000001", value=1.1),
    )
    selected, diagnostics = _select_with_diagnostics("0000000001", rows)
    assert selected == ()
    assert len(diagnostics) == 1
    assert diagnostics[0]["reason"] == "AMBIGUOUS_EARLIEST_PERIOD_CONTEXT"
    assert diagnostics[0]["issuer_cik"] == "0000000001"
    assert len(diagnostics[0]["earliest_rows"]) == 2
