from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from packages.data.options_native_exit_coverage_attribution_v28 import (
    CONTRACT, REASONS, _full_reason_counts, _quality_reason,
    evaluate_exit_coverage_root_causes,
)
from packages.data.options_native_original_pair_diagnostic_v26 import (
    _pair_observations, PairDiagnosticError,
)
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_review_sessions, _exit_at_time_query,
)

ET = ZoneInfo("America/New_York")
ENTRY = date(2025, 1, 6)
EXPIRY = date(2025, 2, 14)


def quote(day: date, right: str, *,
          bid: str = "2.00", ask: str = "2.10",
          seconds_ago: int = 10, strike: str = "590",
          bid_size: int = 1, ask_size: int = 1):
    ts = datetime.combine(day, datetime.strptime("10:00", "%H:%M").time(), ET)
    return {
        "expiration": EXPIRY.isoformat(), "strike": strike, "right": right,
        "timestamp": (ts - timedelta(seconds=seconds_ago)).isoformat(),
        "bid": bid, "ask": ask, "bid_size": bid_size, "ask_size": ask_size,
    }


def pair(day: date, *, call_age: int = 10, put_age: int = 10):
    return [
        quote(day, "call", seconds_ago=call_age),
        quote(day, "put", seconds_ago=put_age),
    ]


def evaluate_fixture(*, absent_hold: int | None = None):
    days = _exit_review_sessions(ENTRY)
    def reader(qid, row):
        if qid == "entry":
            return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", pair(ENTRY)
        for i, d in enumerate(days, 1):
            if qid != _exit_at_time_query(d)["query_id"]:
                continue
            if absent_hold == i:
                return "EXPLICIT_NO_DATA_SOURCE_ONLY", None
            if i == 2:
                return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", [quote(d, "call")]
            if i == 3:
                return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", pair(d, call_age=31)
            if i == 4:
                return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", pair(d, call_age=10, put_age=12)
            if i == 5:
                return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", []
            return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", pair(d)
        raise AssertionError(f"Unexpected request {row}")

    return evaluate_exit_coverage_root_causes(
        [{"query_id": "entry", "date_et": ENTRY.isoformat()}], reader,
    )


def test_one_pass_distinguishes_exact_contract_missing_vs_quote_age_vs_clock():
    report = evaluate_fixture()
    assert report["contract"] == CONTRACT
    assert report["source_read_uses"] == 6
    assert report["original_weekly_entry_requests"] == 1
    assert report["eligible_entry_pair_denominator_each_horizon"] == 1
    assert report["provider_requests"] == report["broker_requests"] == 0
    assert report["historical_pnl"] is None
    expected = {
        "1": "MATCHED", "2": "PUT_ABSENT", "3": "CALL_QUOTE_REJECTED",
        "4": "PAIR_CLOCK_SKEW", "5": "BOTH_RIGHTS_ABSENT",
    }
    for hold, reason in expected.items():
        data = report["scenarios"][hold]
        assert set(data["reasons"]) == set(REASONS)
        assert data["reasons"][reason] == 1
        assert sum(data["reasons"].values()) == 1
        assert data["by_entry_year"]["2025"][reason] == 1
    assert report["scenarios"]["3"]["quote_quality_rejection_reasons_individual_legs"] == {"STALE": 1}
    assert report["distinct_absent_original_contract_rights_across_all_exit_dates"] == 3


def test_source_error_is_a_distinct_non_fill_reason():
    result = evaluate_fixture(absent_hold=5)
    assert result["scenarios"]["5"]["reasons"]["NO_REVIEW_SOURCE"] == 1
    assert result["scenarios"]["5"]["reasons"]["BOTH_RIGHTS_ABSENT"] == 0
    assert result["scenarios"]["5"]["review_original_source_states"]["EXPLICIT_NO_DATA_SOURCE_ONLY"] == 1


def test_quality_categories_are_exact_to_v26_instead_of_relaxed():
    sample = quote(ENTRY, "call")
    cases = [
        (dict(sample, bid="0.00"), "NO_TWO_SIDED_PRICE"),
        (dict(sample, bid_size=0), "NO_DISPLAY_SIZE"),
        (dict(sample, ask="2.60"), "WIDE_SPREAD"),
        (quote(ENTRY, "call", seconds_ago=31), "STALE"),
        (dict(sample), "PASS"),
    ]
    for q, expected in cases:
        assert _quality_reason(q, ENTRY) == expected
    with pytest.raises(PairDiagnosticError, match="QUOTE_CROSSED"):
        _quality_reason(dict(sample, bid="5.00", ask="2.00"), ENTRY)


def test_never_fabricate_valid_pair_when_original_expiry_passed():
    # A source can still be examined but an expired contract is not considered
    # a tradable exit by this diagnostic.
    entered = _pair_observations(pair(ENTRY), ENTRY, entry=True)
    later = EXPIRY + timedelta(days=1)
    reasons, quality = _full_reason_counts(entered, pair(later), later)
    assert reasons == {"EXPIRED_AT_REVIEW": 1}
    assert quality == {}


def test_no_retained_response_is_not_proof_contract_was_unlisted():
    report = evaluate_fixture()
    assert report["missing_rights_are_absent_from_retained_response_not_proven_absent_from_market"] is True
    assert report["strategy_promotion"] is False
    # No preview authorizes a new provider request; only explains absences.
    assert "provider_requests" in report and report["provider_requests"] == 0
