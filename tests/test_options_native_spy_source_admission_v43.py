from __future__ import annotations

from collections import Counter

import pytest

from packages.data import options_native_spy_source_admission_v43 as gate
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint


DAY = "2025-06-09"
EXPIRATION = "2025-07-18"
STRIKE = "600"


def original_case():
    return {
        "original_entry_date_et": DAY,
        "frozen_expiration_et": EXPIRATION,
        "frozen_strike": STRIKE,
        "source_spy_0959_spot": "600",
        "conditional_retrospective_dividend_volatility": "0.21",
    }


def exact_quote(right, *, timestamp=None, bid=1.8, ask=2., size=2, extra=()):
    row = {
        "symbol": "SPY", "expiration": EXPIRATION, "strike": "600",
        "right": right, "timestamp": timestamp or
            ("2025-06-09T10:00:50.000-04:00" if right == "call"
             else "2025-06-09T10:00:50.300-04:00"),
        "bid": bid, "ask": ask, "bid_size": size, "ask_size": size,
    }
    return (row, *extra)


def source(rows, right):
    return {
        "query_id": "source_" + right,
        "source_sha256": "a" * 64,
        "status": "CACHE_HIT",
        "source_rows": rows,
    }


def demand(right):
    return {
        "purpose": right + "_1001_quote",
        "kwargs": {"symbol": "SPY", "date_et": DAY, "expiration": EXPIRATION,
                   "strike": STRIKE, "right": right},
    }


def oi_row(right, value=250, timestamp="2025-06-09T06:30:00-04:00"):
    return {
        "symbol": "SPY", "expiration": EXPIRATION,
        "strike": STRIKE, "right": right,
        "timestamp": timestamp, "open_interest": value,
    }


def group(*, call=None, put=None, oi=None):
    return {
        "decision_date_prior_state_oi_surface": (
            {"purpose": "decision_date_prior_state_oi_surface"},
            source(oi if oi is not None else (
                oi_row("call"), oi_row("put"),
                oi_row("call", value=1, timestamp="2025-06-09T06:31:00-04:00")
                | {"strike": "605"},
            ), "oi"),
        ),
        "call_1001_quote": (demand("call"), source(
            call if call is not None else exact_quote("call"), "call",
        )),
        "put_1001_quote": (demand("put"), source(
            put if put is not None else exact_quote("put"), "put",
        )),
    }


def test_qualified_exact_quotes_and_oi_still_never_become_order_fills():
    case = gate.assess_case(original_case(), group())
    assert case["status"] == "SOURCE_MICROSTRUCTURE_OI_CHECKS_PASS"
    assert case["call_put_quote_time_skew_seconds"] == pytest.approx(.3)
    assert case["source_decision_morning_oi"]["call"]["open_interest"] == 250
    assert case["source_decision_morning_oi"]["put"]["open_interest"] == 250
    assert case["historical_entry_signal"] is None
    assert case["hypothetical_order_fill"] is None
    assert case["point_in_time_input_acceptance"] is False
    assert case["source_10_01_call"]["historically_executable_order_fill"] is False


def test_stale_and_wide_quote_filters_preserve_original_value():
    case = gate.assess_case(
        original_case(),
        group(call=exact_quote("call", timestamp="2025-06-09T09:58:00-04:00"),
              put=exact_quote("put", bid=.5, ask=2.0))
    )
    assert case["status"] == "SOURCE_QUALITY_UNQUALIFIED"
    assert "CALL_QUOTE_UNQUALIFIED" in case["reason_codes"]
    assert "PUT_QUOTE_UNQUALIFIED" in case["reason_codes"]
    assert "PAIR_QUOTE_CLOCK_UNQUALIFIED" not in case["reason_codes"]
    assert case["source_10_01_call"]["seconds_before_1001"] == 180.0
    assert "SPREAD_ABOVE_15_PERCENT_OR_UNKNOWN" in case["source_10_01_put"]["reason_codes"]


def test_naive_timestamp_not_granted_historical_publication_authority():
    case = gate.assess_case(original_case(), group(
        oi=(oi_row("call", timestamp="2025-06-09T06:30:00"), oi_row("put")),
        call=exact_quote("call", timestamp="2025-06-09T10:00:58"),
    ))
    assert "CALL_QUOTE_UNQUALIFIED" in case["reason_codes"]
    assert "ORIGINAL_CALL_PUT_OI_UNQUALIFIED" in case["reason_codes"]
    assert "CALL_OI_PUBLICATION_TIME_UNQUALIFIED" in (
        case["source_decision_morning_oi"]["reason_codes"]
    )


def test_original_oi_below_100_and_duplicate_contract_are_rejected():
    case = gate.assess_case(original_case(), group(
        oi=(oi_row("call", 90), oi_row("call", 120), oi_row("put", 200)),
    ))
    assert case["status"] == "SOURCE_QUALITY_UNQUALIFIED"
    assert "CALL_OI_NOT_UNIQUE" in case["source_decision_morning_oi"]["reason_codes"]
    low = gate.assess_case(original_case(), group(
        oi=(oi_row("call", 90), oi_row("put", 100)),
    ))
    assert "CALL_OI_BELOW_100" in low["source_decision_morning_oi"]["reason_codes"]


def test_late_oi_future_quote_and_skew_are_caught():
    case = gate.assess_case(original_case(), group(
        oi=(oi_row("call", timestamp="2025-06-09T10:01:01-04:00"),
            oi_row("put")),
        call=exact_quote("call", timestamp="2025-06-09T10:01:02-04:00"),
        put=exact_quote("put", timestamp="2025-06-09T10:00:45-04:00"),
    ))
    assert case["status"] == "SOURCE_QUALITY_UNQUALIFIED"
    assert "CALL_PUT_QUOTE_SKEW_ABOVE_1_SECOND" in case["reason_codes"]
    assert "CALL_OI_PUBLICATION_TIME_UNQUALIFIED" in (
        case["source_decision_morning_oi"]["reason_codes"]
    )


def test_missing_source_never_assumed_zero_or_loss():
    sources = group()
    del sources["put_1001_quote"]
    case = gate.assess_case(original_case(), sources)
    assert case["status"] == "SOURCE_INCOMPLETE"
    assert case["missing_source_purposes"] == ["put_1001_quote"]
    assert case["entry_signal"] is None
    assert case["execution_fill"] is None


def test_v40_pin_and_source_counts_must_be_valid_before_acquisition(monkeypatch):
    v37 = {"fingerprint": "v37_fp"}
    v40 = {
        "contract": gate.V40_CONTRACT, "source_v37_fingerprint": "v37_fp",
        "original_candidate_pairs": 361, "original_decision_clocks": 411,
        "original_weekly_abstentions": 50,
        "source_demand_status": "ALL_REQUESTED_SOURCES_PRESENT",
        "actual_strategy_entries": None,
        "historical_option_fill_evidence": None,
        "source_demand_counts": {
            "source_uses_requested": 1083,
            "source_uses_resolved": 1083,
            "source_uses_failed_or_unresolved": 0,
        },
    }
    v40["fingerprint"] = _fingerprint(v40)
    monkeypatch.setattr(gate, "validate_v37_source_packet",
                        lambda report: [original_case()] * 361)
    monkeypatch.setattr(gate, "PINNED_V40_REPORT_SHA", v40["fingerprint"])
    assert len(gate.validate_source_pair_reports(v37, v40)) == 361
    v40["source_demand_counts"]["source_uses_resolved"] = 1082
    v40["fingerprint"] = _fingerprint({k: v for k,v in v40.items() if k != "fingerprint"})
    monkeypatch.setattr(gate, "PINNED_V40_REPORT_SHA", v40["fingerprint"])
    with pytest.raises(gate.SourceAdmissionError, match="INCOMPLETE"):
        gate.validate_source_pair_reports(v37, v40)
