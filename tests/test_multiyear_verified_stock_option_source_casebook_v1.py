from __future__ import annotations

from copy import deepcopy

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_native_eod_close_source_v1 import CONTRACT as CLOSE_CONTRACT
from packages.data.multiyear_observed_option_quote_timeline_v1 import CONTRACT as TIMELINE_CONTRACT
from packages.data.multiyear_option_quote_reuse_handoff_v1 import CONTRACT as HANDOFF_CONTRACT
from packages.data.multiyear_option_stock_eod_preflight_v1 import CONTRACT as NEEDS_CONTRACT
from packages.data.multiyear_verified_stock_option_source_casebook_v1 import (
    NO_PAIR, SOURCE_PAIR, STOCK_GAP, SourceCasebookError,
    build_verified_source_casebook,
)


def signed(row: dict, key: str) -> dict:
    row[key] = _fingerprint(row)
    return row


def fixture_reports() -> tuple[dict, dict, dict, dict]:
    q1 = {
        "session_et": "2022-01-04", "provider_updated_at_utc": "2022-01-04T21:00:00+00:00",
        "observed_bid_per_share": "2.0", "observed_ask_per_share": "2.2",
        "two_sided_source": True,
        "provider_update_not_proven_publication_or_1600_et_mark": True,
    }
    q2 = {
        **q1, "session_et": "2022-01-05",
        "provider_updated_at_utc": "2022-01-05T21:00:00+00:00",
        "observed_bid_per_share": "2.7", "observed_ask_per_share": "3.0",
    }
    handoff = signed({
        "contract": HANDOFF_CONTRACT, "original_case_denominator": 1,
        "original_right_memberships": 2, "selected_case_right_memberships": 1,
        "provider_requests": 0, "protected_2026_outcomes_read": 0,
        "portfolio_pnl_authority": False,
        "rows": [
            {"case_right_id": "case1:C", "original_case_id": "case1", "year": "2022",
             "right": "call", "option_symbol": "O:ABC220121C00100000",
             "quote_request_identity": "q", "quote_body_sha256": "a" * 64,
             "quote_history_status": "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY"},
            {"case_right_id": "case1:P", "original_case_id": "case1", "year": "2022",
             "right": "put", "option_symbol": None, "quote_request_identity": None,
             "quote_body_sha256": None, "quote_history_status": "NO_PIT_SELECTED_CONTRACT"},
        ],
    }, "handoff_fingerprint")
    timeline = signed({
        "contract": TIMELINE_CONTRACT, "source_handoff_fingerprint": handoff["handoff_fingerprint"],
        "original_case_denominator": 1, "original_right_memberships": 2,
        "provider_requests": 0, "protected_2026_outcomes_read": 0,
        "account_pnl_authority": False,
        "rows": [
            {"case_right_id": "case1:C", "original_case_id": "case1", "year": "2022",
             "right": "call", "option_symbol": "O:ABC220121C00100000",
             "quote_request_identity": "q",
             "original_quote_history_status": "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY",
             "timeline_status": "TWO_OR_MORE_LATER_TWO_SIDED_SOURCE_DATES",
             "actual_execution_or_portfolio_pnl_authority": False,
             "first_later_observed_quote": q1, "next_later_observed_quote": q2},
            {"case_right_id": "case1:P", "original_case_id": "case1", "year": "2022",
             "right": "put", "option_symbol": None, "quote_request_identity": None,
             "original_quote_history_status": "NO_PIT_SELECTED_CONTRACT",
             "timeline_status": "NO_PIT_SELECTED_CONTRACT",
             "actual_execution_or_portfolio_pnl_authority": False,
             "first_later_observed_quote": None, "next_later_observed_quote": None},
        ],
    }, "timeline_fingerprint")
    requests = [
        {"request_identity": n, "instrument_id": "abc-id", "ticker": "ABC",
         "session_et": day}
        for n, day in (("e", "2022-01-04"), ("x", "2022-01-05"))
    ]
    needs = signed({
        "contract": NEEDS_CONTRACT, "original_case_denominator": 1,
        "original_right_memberships": 2, "provider_requests": 0,
        "protected_2026_outcomes_read": 0, "portfolio_pnl_authority": False,
        "accepted_native_fingerprint": "n" * 64,
        "accepted_option_timeline_fingerprint": timeline["timeline_fingerprint"],
        "requests": requests, "rows": [
            {"case_right_id": "case1:C", "original_case_id": "case1",
             "year": "2022", "ticker": "ABC", "instrument_id": "abc-id",
             "option_symbol": "O:ABC220121C00100000",
             "status": "QUOTE_SOURCE_AVAILABLE_NATIVE_RAW_EOD_CLOSE_NOT_YET_VERIFIED",
             "native_entry_close_request_identity": "e",
             "native_next_close_request_identity": "x",
             "native_close_verified": False, "matched_option_stock_clock_verified": False,
             "hypothetical_fill_or_option_pnl_authority": False},
            {"case_right_id": "case1:P", "original_case_id": "case1",
             "year": "2022", "ticker": "ABC", "instrument_id": "abc-id",
             "option_symbol": None, "status": "NO_LATER_TWO_SIDED_SOURCE_PAIR",
             "native_entry_close_request_identity": None,
             "native_next_close_request_identity": None,
             "native_close_verified": False, "matched_option_stock_clock_verified": False,
             "hypothetical_fill_or_option_pnl_authority": False},
        ],
    }, "demand_fingerprint")
    closes = signed({
        "contract": CLOSE_CONTRACT,
        "original_stock_close_demand_fingerprint": needs["demand_fingerprint"],
        "original_native_fingerprint": needs["accepted_native_fingerprint"],
        "unique_requested_native_closes": 2, "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "option_fill_or_portfolio_pnl_authority": False,
        "provider_option_update_is_not_verified_stock_close_clock": True,
        "rows": [{
            **x, "status": "VERIFIED_NATIVE_RAW_EOD_CLOSE",
            "raw_as_traded_open": "99.0", "raw_as_traded_close": "101.0",
            "native_unit_id": "native-v2-unit", "native_canonical_sha256": "b" * 64,
            "option_clock_match_proven": False, "historical_fill_proven": False,
        } for x in requests],
    }, "source_fingerprint")
    return handoff, timeline, needs, closes


def resign(report: dict, field: str) -> None:
    report[field] = _fingerprint({k: v for k, v in report.items() if k != field})


def test_full_right_population_join_is_source_only_and_replay_ready():
    output = build_verified_source_casebook(*fixture_reports(), expected_original_cases=1)
    assert output["original_case_denominator"] == 1
    assert output["original_right_memberships"] == 2
    assert output["two_later_option_source_rights"] == 1
    assert output["dated_option_and_stock_source_rights"] == 1
    assert output["by_status"] == {NO_PAIR: 1, SOURCE_PAIR: 1}
    assert output["by_year"]["2026"] == {}
    assert output["account_pnl_authority"] is False
    assert output["synchronized_clock_pairs_proven"] == 0
    assert output["rows"][0]["first_later_option_source"]["observed_ask_per_share"] == "2.2"
    assert output["rows"][0]["next_later_option_source"]["observed_bid_per_share"] == "2.7"
    assert output["rows"][0]["entry_session_native_source"]["raw_as_traded_close"] == "101.0"
    assert output["rows"][0]["executable_fill_or_account_pnl_authority"] is False


def test_exact_missing_native_bar_retained_as_gap_not_trade():
    h, t, n, c = fixture_reports()
    c["rows"][1]["status"] = "NO_RAW_NATIVE_DAILY_BAR_FOR_EXACT_SESSION"
    c["rows"][1]["raw_as_traded_open"] = None
    c["rows"][1]["raw_as_traded_close"] = None
    resign(c, "source_fingerprint")
    report = build_verified_source_casebook(h, t, n, c, expected_original_cases=1)
    assert report["by_status"][STOCK_GAP] == 1
    assert report["dated_option_and_stock_source_rights"] == 0


def test_changed_signed_source_rejected():
    h, t, n, c = fixture_reports()
    c["rows"][0]["raw_as_traded_close"] = "400"
    with pytest.raises(ValueError, match="fingerprint"):
        build_verified_source_casebook(h, t, n, c, expected_original_cases=1)


def test_re_signed_mismatched_session_rejected():
    h, t, n, c = fixture_reports()
    c["rows"][0]["session_et"] = "2022-01-06"
    resign(c, "source_fingerprint")
    with pytest.raises(SourceCasebookError, match="identity"):
        build_verified_source_casebook(h, t, n, c, expected_original_cases=1)


def test_missing_original_right_slot_rejected():
    h, t, n, c = fixture_reports()
    t["rows"].pop()
    resign(t, "timeline_fingerprint")
    n["accepted_option_timeline_fingerprint"] = t["timeline_fingerprint"]
    resign(n, "demand_fingerprint")
    c["original_stock_close_demand_fingerprint"] = n["demand_fingerprint"]
    resign(c, "source_fingerprint")
    with pytest.raises(SourceCasebookError, match="partition"):
        build_verified_source_casebook(h, t, n, c, expected_original_cases=1)


def test_crossed_quote_rejected_even_if_source_document_is_resigned():
    h, t, n, c = fixture_reports()
    t["rows"][0]["first_later_observed_quote"]["observed_ask_per_share"] = "1"
    resign(t, "timeline_fingerprint")
    n["accepted_option_timeline_fingerprint"] = t["timeline_fingerprint"]
    resign(n, "demand_fingerprint")
    c["original_stock_close_demand_fingerprint"] = n["demand_fingerprint"]
    resign(c, "source_fingerprint")
    with pytest.raises(SourceCasebookError, match="crossed"):
        build_verified_source_casebook(h, t, n, c, expected_original_cases=1)
