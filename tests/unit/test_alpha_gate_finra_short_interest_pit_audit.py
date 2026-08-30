from __future__ import annotations

from datetime import date

from packages.backtesting.alpha_gate_finra_short_interest_pit_audit import (
    FINRA_SHORT_INTEREST_EXCHANGE_CODE_TO_MIC,
    FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT,
    _matching,
    _snapshot_index,
    decision_date,
    finra_short_interest_pit_audit_fingerprint,
    publication_date,
)


def test_fingerprint_is_frozen() -> None:
    assert finra_short_interest_pit_audit_fingerprint() == FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT


def test_publication_chronology_matches_finra_2026_anchors() -> None:
    assert publication_date(date(2026, 3, 31)) == date(2026, 4, 10)
    assert publication_date(date(2026, 6, 30)) == date(2026, 7, 10)
    assert publication_date(date(2026, 7, 31)) == date(2026, 8, 11)
    assert publication_date(date(2026, 12, 31)) == date(2027, 1, 12)
    assert decision_date(date(2026, 7, 31)) == date(2026, 8, 12)


def test_snapshot_identity_requires_active_common_stock_and_exact_exchange() -> None:
    rows = [
        {"ticker": "ABC", "active": True, "type": "CS", "primary_exchange": "XNAS", "composite_figi": "BBG000ABC001"},
        {"ticker": "PREF", "active": True, "type": "PFD", "primary_exchange": "XNYS", "composite_figi": "BBG000PREF01"},
        {"ticker": "OLD", "active": False, "type": "CS", "primary_exchange": "XNYS", "composite_figi": "BBG000OLD001"},
    ]
    index = _snapshot_index(rows, date(2026, 8, 12))
    assert len(_matching(index, "ABC", FINRA_SHORT_INTEREST_EXCHANGE_CODE_TO_MIC["R"])) == 1
    assert _matching(index, "ABC", "XNYS") == []
    assert "PREF" not in index
    assert "OLD" not in index


def test_identity_continuity_is_stable_with_same_figi() -> None:
    settlement = _snapshot_index(
        [{"ticker": "ABC", "active": True, "type": "CS", "primary_exchange": "XNYS", "composite_figi": "BBG000ABC001"}],
        date(2026, 7, 31),
    )
    decision = _snapshot_index(
        [{"ticker": "ABC", "active": True, "type": "CS", "primary_exchange": "XNYS", "composite_figi": "BBG000ABC001"}],
        date(2026, 8, 12),
    )
    left = _matching(settlement, "ABC", "XNYS")[0]
    right = _matching(decision, "ABC", "XNYS")[0]
    assert left["instrument_id"] == right["instrument_id"]
