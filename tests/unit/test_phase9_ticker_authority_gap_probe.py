from __future__ import annotations

from datetime import date

from packages.regimes.ticker_authority_gap_probe import (
    CONFLICTED_EVENT_DATE,
    CURRENT_EVENT_AFTER_AS_OF,
    CURRENT_TICKER_ABSENT,
    CURRENT_TICKER_NOT_ACTIVE_AT_AS_OF,
    NO_AUTHORITATIVE_EVENTS,
    UNCLASSIFIED,
    classify_gap,
)


AS_OF = date(2026, 8, 14)


def test_gap_classifier_handles_no_authoritative_events() -> None:
    assert classify_gap(current_ticker="ABC", as_of_date=AS_OF, events=[]) == NO_AUTHORITATIVE_EVENTS


def test_gap_classifier_detects_conflicted_event_date() -> None:
    events = [(date(2024, 1, 1), "ABC"), (date(2024, 1, 1), "XYZ")]
    assert classify_gap(current_ticker="ABC", as_of_date=AS_OF, events=events) == CONFLICTED_EVENT_DATE


def test_gap_classifier_detects_current_ticker_absent() -> None:
    events = [(date(2024, 1, 1), "OLD")]
    assert classify_gap(current_ticker="ABC", as_of_date=AS_OF, events=events) == CURRENT_TICKER_ABSENT


def test_gap_classifier_detects_current_event_after_as_of() -> None:
    events = [(date(2026, 8, 15), "ABC")]
    assert classify_gap(current_ticker="ABC", as_of_date=AS_OF, events=events) == CURRENT_EVENT_AFTER_AS_OF


def test_gap_classifier_distinguishes_inactive_current_from_consistent_current() -> None:
    inactive = [(date(2024, 1, 1), "ABC"), (date(2025, 1, 1), "XYZ")]
    assert classify_gap(current_ticker="ABC", as_of_date=AS_OF, events=inactive) == CURRENT_TICKER_NOT_ACTIVE_AT_AS_OF
    consistent = [(date(2024, 1, 1), "OLD"), (date(2025, 1, 1), "ABC")]
    assert classify_gap(current_ticker="ABC", as_of_date=AS_OF, events=consistent) == UNCLASSIFIED
