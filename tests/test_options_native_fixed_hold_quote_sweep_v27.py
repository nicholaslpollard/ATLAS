from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_review_sessions, _exit_at_time_query,
)
from packages.simulation.options_native_fixed_hold_quote_sweep_v27 import (
    CONTRACT, HOLD_SESSIONS, evaluate_fixed_hold_quote_scenarios,
)

ET = ZoneInfo("America/New_York")
ENTRY = date(2025, 1, 6)
EXPIRY = date(2025, 2, 14)


def quote(session: date, right: str, *, strike: str = "590",
          bid: str = "2.0", ask: str = "2.10", seconds_ago: int = 10):
    cutoff = datetime.fromisoformat(f"{session.isoformat()}T10:00:00").replace(tzinfo=ET)
    return {
        "expiration": EXPIRY.isoformat(),
        "strike": strike, "right": right,
        "timestamp": (cutoff - timedelta(seconds=seconds_ago)).isoformat(),
        "bid": bid, "ask": ask, "bid_size": 1, "ask_size": 1,
    }


def pair(day: date, *, same_strike: bool = True):
    strike = "590" if same_strike else "595"
    return [
        quote(day, "call", strike=strike, bid="2.0", ask="2.10"),
        quote(day, "put", strike=strike, bid="1.9", ask="2.00"),
    ]


def _reader(*, missing_review: int | None = None,
            change_strike_review: int | None = None):
    review_dates = _exit_review_sessions(ENTRY)
    read_uses = []

    def read(qid, request):
        read_uses.append(qid)
        if qid == "entry":
            return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", pair(ENTRY)
        for hold, d in enumerate(review_dates, 1):
            if qid == _exit_at_time_query(d)["query_id"]:
                if hold == missing_review:
                    return "EXPLICIT_NO_DATA_SOURCE_ONLY", None
                return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", pair(
                    d, same_strike=hold != change_strike_review,
                )
        raise AssertionError("Unknown source")
    return read, read_uses


def test_all_fixed_horizons_share_unbiased_entry_denominator():
    reader, uses = _reader()
    result = evaluate_fixed_hold_quote_scenarios(
        [{"query_id": "entry", "date_et": ENTRY.isoformat()}], reader,
    )
    assert result["contract"] == CONTRACT
    assert result["fixed_holding_periods_in_XNYS_sessions"] == list(HOLD_SESSIONS)
    assert result["source_read_uses"] == 6
    assert len(uses) == 6
    assert result["provider_requests"] == 0
    assert not result["historical_alpha_authority"]
    assert result["combined_portfolio_equity"] is None
    for hold in HOLD_SESSIONS:
        case = result["scenarios"][str(hold)]
        assert case["eligible_entry_pair_count"] == 1
        assert case["source_observed_same_contract_pair"] == 1
        assert case["paired_observation_coverage_fraction"] == 1
        assert case["by_entry_year"]["2025"]["entry_pairs"] == 1
        fees = case[
            "hypothetical_10am_entry_ask_exit_bid_return_by_fee_per_contract_per_side"
        ]
        assert fees["0.00"]["mean_pct"] > fees["1.30"]["mean_pct"]
        assert fees["0.65"]["observations"] == 1


def test_absent_review_stays_unresolved_and_does_not_become_synthetic_loss():
    reader, _ = _reader(missing_review=2, change_strike_review=4)
    result = evaluate_fixed_hold_quote_scenarios(
        [{"query_id": "entry", "date_et": ENTRY.isoformat()}], reader,
    )
    second = result["scenarios"]["2"]
    fourth = result["scenarios"]["4"]
    assert second["eligible_entry_pair_count"] == fourth["eligible_entry_pair_count"] == 1
    assert second["unobserved_due_to_missing_review_source"] == 1
    assert second["source_observed_same_contract_pair"] == 0
    assert second["hypothetical_10am_entry_ask_exit_bid_return_by_fee_per_contract_per_side"]["0.65"]["mean_pct"] is None
    assert fourth["unobserved_due_to_contract_absence_or_quality"] == 1
    assert fourth["source_observed_same_contract_pair"] == 0
    assert result["scenarios"]["5"]["source_observed_same_contract_pair"] == 1


def test_unqualified_entry_still_in_original_week_denominator():
    reader, uses = _reader()

    def unavailable_entry(qid, request):
        if qid == "entry":
            return "RAW_ARCHIVED_INVALID_SCHEMA", None
        return reader(qid, request)

    result = evaluate_fixed_hold_quote_scenarios(
        [{"query_id": "entry", "date_et": ENTRY.isoformat()}], unavailable_entry,
    )
    assert result["planned_weekly_entry_clocks"] == 1
    assert result["entry_source_states_unavailable"]["RAW_ARCHIVED_INVALID_SCHEMA"] == 1
    assert result["source_read_uses"] == 1
    assert uses == []
    for hold in HOLD_SESSIONS:
        v = result["scenarios"][str(hold)]
        assert v["eligible_entry_pair_count"] == 0
        assert v["paired_observation_coverage_fraction"] is None


def test_no_future_outcome_changes_entry_candidate_and_report_determinism():
    reader1, _ = _reader(change_strike_review=2)
    reader2, _ = _reader(change_strike_review=2)
    entries = [{"query_id": "entry", "date_et": ENTRY.isoformat()}]
    first = evaluate_fixed_hold_quote_scenarios(entries, reader1)
    second = evaluate_fixed_hold_quote_scenarios(entries, reader2)
    assert first["fingerprint"] == second["fingerprint"]
    assert all(first["scenarios"][str(h)]["eligible_entry_pair_count"] == 1
               for h in HOLD_SESSIONS)
    assert first["scenarios"]["2"]["source_observed_same_contract_pair"] == 0
